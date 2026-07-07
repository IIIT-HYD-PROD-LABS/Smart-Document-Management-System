"""FastAPI dependency factories for compliance endpoints — Phase 9 RBAC + RLS bridge.

Three core dependencies:
  - get_active_client_id    → reads ContextVar set by TenantContextMiddleware
  - get_active_membership   → looks up the (user, client) membership; rejects
                              if missing/expired
  - require_compliance_permission(perm) → factory: requires `perm` on the
                                          active membership

Per CONTEXT D-28: pattern mirrors v1.0 require_admin / require_editor /
require_viewer in app/utils/security.py — composition via FastAPI Depends().

Per RESEARCH Pitfall 5: membership lookup is mandatory — frontend cannot
bypass via header tampering. Even if a malicious client sends X-Client-Id
for a tenant they don't belong to, get_active_membership returns 403.

Cross-client mode (X-Client-Id: *):
  - Allowed only for compliance_head, ca_consultant, cfo (per CONTEXT D-23 +
    is_cross_client_eligible() helper from migration 0018).
  - get_active_membership returns the highest-privilege eligible membership
    for the user; routes that need a specific client_id should reject when
    cross-client mode is active.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.compliance.middleware.auditor_expiry import (
    is_membership_active,
    reason_inactive,
)
from app.compliance.middleware.tenant_context import (
    cross_client_mode_var,
    current_client_id_var,
)
from app.compliance.models.membership import ClientMembership
from app.compliance.services.permission_registry import (
    CompliancePermission,
    ComplianceRole,
    has_permission,
)
from app.database import get_async_db, get_db
from app.models.user import User
from app.utils.security import get_current_user

# Roles eligible for cross-client mode. Mirrors is_cross_client_eligible()
# from migration 0018 — keep these two lists in sync.
_CROSS_CLIENT_ELIGIBLE_ROLES = ("compliance_head", "ca_consultant", "cfo")


def get_active_client_id(request: Request) -> Optional[int]:
    """Returns the active client_id from ContextVar (or None if cross-client mode).

    The TenantContextMiddleware sets the ContextVar from the X-Client-Id
    header before any route runs. Cross-client mode (X-Client-Id: *) returns
    None — callers must check is_cross_client_mode() to distinguish.

    Raises 400 if no client context is set on /api/compliance/* — fail-loud
    rather than silently rendering an empty list (RLS would also return
    nothing, but a 400 is more debuggable).
    """
    if cross_client_mode_var.get():
        return None
    cid = current_client_id_var.get()
    if cid is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Client-Id header is required for compliance endpoints",
        )
    return cid


def is_cross_client_mode() -> bool:
    """Returns True if the current request is in cross-client (All Clients) mode."""
    return cross_client_mode_var.get()


async def get_active_membership(
    current_user: User = Depends(get_current_user),
    client_id: Optional[int] = Depends(get_active_client_id),
    db: AsyncSession = Depends(get_async_db),
) -> ClientMembership:
    """Looks up (user, client) → ClientMembership. Rejects if missing or expired.

    For cross-client mode (client_id=None), returns ANY active membership for
    the user that is in the eligible-roles set (compliance_head/ca_consultant/cfo).
    Pitfall 5 mitigation: the user must have an actual eligible membership —
    sending X-Client-Id: * does not grant cross-client access by header alone.
    """
    if client_id is None:
        # Cross-client mode — defense in depth (Phase 4 / 2026-05-09).
        # Tenant-isolation contract for the multi-tenant SaaS: only the
        # platform admin (users.role == 'admin') is allowed to see across
        # organizations. The previous compliance_role-only gate let an
        # editor or viewer with a senior compliance_role (ca_consultant
        # often added in error) curl their way to cross-tenant data even
        # though the UI hid the toggle.
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-client mode requires platform admin role",
            )
        now = datetime.now(timezone.utc)
        result = await db.execute(
            select(ClientMembership).where(
                ClientMembership.user_id == current_user.id,
                ClientMembership.compliance_role.in_(_CROSS_CLIENT_ELIGIBLE_ROLES),
            )
        )
        candidates = result.scalars().all()
        active = [m for m in candidates if is_membership_active(m, now)]
        if not active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Cross-client mode requires an active compliance_head, "
                    "ca_consultant, or cfo membership"
                ),
            )
        return active[0]

    result = await db.execute(
        select(ClientMembership).where(
            ClientMembership.user_id == current_user.id,
            ClientMembership.client_id == client_id,
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No membership for client {client_id}",
        )
    if not is_membership_active(membership):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason_inactive(membership) or "Membership not active",
        )
    return membership


def require_compliance_permission(perm: CompliancePermission):
    """Factory: returns a Depends-compatible dependency that requires `perm`
    on the active membership.

    Usage:
        @router.post(
            "/notices",
            dependencies=[Depends(require_compliance_permission(
                CompliancePermission.NOTICE_CREATE))],
        )
        def create_notice(...): ...

    Or to access the membership in the handler:
        @router.post("/notices")
        def create_notice(
            membership: ClientMembership = Depends(
                require_compliance_permission(CompliancePermission.NOTICE_CREATE)
            ),
        ): ...
    """

    def _check(
        membership: ClientMembership = Depends(get_active_membership),
    ) -> ClientMembership:
        try:
            role = ComplianceRole(membership.compliance_role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "invalid_role",
                    "message": (
                        f"Invalid compliance role '{membership.compliance_role}'. "
                        "Ask your admin to re-issue your membership."
                    ),
                    "your_role": membership.compliance_role,
                },
            )
        if not has_permission(role, perm):
            # Identify which roles do hold this permission, so the frontend
            # can render an actionable "switch client" or "ask admin" CTA.
            from app.compliance.services.permission_registry import (
                ROLE_PERMISSIONS,
            )

            allowed_roles = sorted(
                r.value for r, perms in ROLE_PERMISSIONS.items() if perm in perms
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "role_lacks_permission",
                    "message": (
                        f"Your role '{role.value}' on this client cannot use this "
                        "action. Switch to a client where you hold one of: "
                        f"{', '.join(allowed_roles)}, or ask your admin to "
                        "upgrade your membership."
                    ),
                    "your_role": role.value,
                    "required_permission": perm.value,
                    "allowed_roles": allowed_roles,
                },
            )
        return membership

    return _check


def require_client_create_or_first_onboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Optional[ClientMembership]:
    """Onboarding gate for POST /compliance/clients, admin-only (2026-05-21).

    Earlier revisions allowed three paths into client creation:
      1. v1.0 admin override
      2. Bootstrap (user with zero memberships could self-create their first client)
      3. Existing compliance member with the `client:create` permission (ca_consultant)

    Paths 2 and 3 were removed in favour of a single rule: only system
    admins (`users.role = 'admin'`) provision new tenants, then the
    tenant admin invites the rest of the team via
    POST /clients/{id}/memberships (which now accepts email + sends an
    invite, see app/services/invitation_service.py).

    Reason: the bootstrap path let any newly-registered user spin up a
    client without supervision; combined with the BYOK key feature, that
    was a tenant-sprawl + cost-control risk. The CLIENT_CREATE
    permission stays in the registry for future flexibility but no role
    holds it by default any more (the new requirement is system-admin).
    """
    if (current_user.role or "").lower() == "admin":
        return None
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Only system administrators can create new client workspaces. "
            "Ask an administrator to provision the client; once it exists, "
            "they (or a compliance_head) can invite you via "
            "POST /api/compliance/clients/{id}/memberships."
        ),
    )


def require_any_compliance_permission(*perms: CompliancePermission):
    """Factory: returns a dependency that admits any user holding ANY of `perms`.

    H-A second hardening: used at the route layer for endpoints whose
    fine-grained permission is determined by request state (e.g. response
    approval where the required permission depends on the response's
    pending stage). The handler still enforces the precise stage match,
    but the route gate now refuses callers who lack ALL relevant approval
    permissions instead of admitting any NOTICE_VIEW holder.
    """
    perm_set = frozenset(perms)
    if not perm_set:
        raise ValueError("require_any_compliance_permission needs ≥1 permission")

    def _check(
        membership: ClientMembership = Depends(get_active_membership),
    ) -> ClientMembership:
        try:
            role = ComplianceRole(membership.compliance_role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Invalid compliance role: {membership.compliance_role}",
            )
        for p in perm_set:
            if has_permission(role, p):
                return membership
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role '{role.value}' lacks any of permissions: "
                f"{[p.value for p in perm_set]}"
            ),
        )

    return _check


def require_compliance_role(*allowed_roles: ComplianceRole):
    """Factory: requires the active membership to be in one of `allowed_roles`.

    Useful when an endpoint needs a coarse-grained role check rather than a
    specific permission (e.g. cross-client report endpoint that requires
    compliance_head OR cfo).
    """
    allowed = frozenset(allowed_roles)

    def _check(
        membership: ClientMembership = Depends(get_active_membership),
    ) -> ClientMembership:
        try:
            role = ComplianceRole(membership.compliance_role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid role",
            )
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{role.value}' is not in allowed set: "
                    f"{[r.value for r in allowed]}"
                ),
            )
        return membership

    return _check
