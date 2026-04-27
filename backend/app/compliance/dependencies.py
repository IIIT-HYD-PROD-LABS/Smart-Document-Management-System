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
from app.database import get_db
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


def get_active_membership(
    current_user: User = Depends(get_current_user),
    client_id: Optional[int] = Depends(get_active_client_id),
    db: Session = Depends(get_db),
) -> ClientMembership:
    """Looks up (user, client) → ClientMembership. Rejects if missing or expired.

    For cross-client mode (client_id=None), returns ANY active membership for
    the user that is in the eligible-roles set (compliance_head/ca_consultant/cfo).
    Pitfall 5 mitigation: the user must have an actual eligible membership —
    sending X-Client-Id: * does not grant cross-client access by header alone.
    """
    if client_id is None:
        # Cross-client mode — accept the highest-privilege eligible membership
        now = datetime.now(timezone.utc)
        candidates = (
            db.query(ClientMembership)
            .filter(
                ClientMembership.user_id == current_user.id,
                ClientMembership.compliance_role.in_(_CROSS_CLIENT_ELIGIBLE_ROLES),
            )
            .all()
        )
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

    membership = (
        db.query(ClientMembership)
        .filter(
            ClientMembership.user_id == current_user.id,
            ClientMembership.client_id == client_id,
        )
        .first()
    )
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
                detail=f"Invalid compliance role: {membership.compliance_role}",
            )
        if not has_permission(role, perm):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role.value}' lacks permission '{perm.value}'",
            )
        return membership

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
