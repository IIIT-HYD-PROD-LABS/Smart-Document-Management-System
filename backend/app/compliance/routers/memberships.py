"""Client membership management router — Phase 9 CLIENT-05, RBAC-04.

POST   /clients/{client_id}/memberships              — add a team member
DELETE /clients/{client_id}/memberships/{membership_id} — revoke membership

Both endpoints require CLIENT_MANAGE_TEAM, which per the registry is
compliance_head + ca_consultant only.

Audit logging:
  - membership_added on successful POST
  - membership_removed on successful DELETE

Both are written to the immutable system audit_log via log_audit_event
(separate session so failures cannot roll back the business operation).
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.client import Client
from app.compliance.models.membership import ClientMembership
from app.compliance.schemas.client import MembershipCreate, MembershipOut
from app.compliance.services.permission_registry import CompliancePermission
from app.config import settings
from app.database import get_async_db
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.services.invitation_service import (
    InvitationError,
    resolve_or_invite_async,
)
from app.utils.security import get_current_user

logger = structlog.stdlib.get_logger()


router = APIRouter(
    prefix="/clients/{client_id}/memberships",
    tags=["compliance-memberships"],
)


@router.post(
    "",
    response_model=MembershipOut,
    status_code=status.HTTP_201_CREATED,
)
async def add_member(
    client_id: int,
    payload: MembershipCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    _gate: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_MANAGE_TEAM)
    ),
):
    """Add a team member to a client (CLIENT-05 team step).

    Resolution rule (see services/invitation_service.py):
      * payload.email + existing TaxSync account  -> attach membership
      * payload.email + no account                -> create pending User
                                                     + send accept-invite email
      * payload.user_id                           -> attach by ID (legacy)

    The pending-User path means an admin can add anyone by email without
    first asking them to self-register. The invitee completes signup via
    POST /api/auth/accept-invite (set password + auto-login).
    """
    client = await db.get(Client, client_id)
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client {client_id} not found",
        )

    try:
        resolved_user_id, invited, dev_token = await resolve_or_invite_async(
            db,
            client_id=client_id,
            client_name=client.name,
            inviter=current_user,
            email=payload.email,
            user_id=payload.user_id,
            full_name=payload.full_name,
        )
    except InvitationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )

    existing = (
        await db.execute(
            select(ClientMembership).where(
                ClientMembership.user_id == resolved_user_id,
                ClientMembership.client_id == client_id,
            )
        )
    ).scalar_one_or_none()
    if existing:
        # Roll back the pending-User write done by resolve_or_invite_async;
        # the caller asked to add an existing member, this is a no-op.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has a membership on this client",
        )
    m = ClientMembership(
        user_id=resolved_user_id,
        client_id=client_id,
        compliance_role=payload.compliance_role,
        access_start=payload.access_start,
        access_end=payload.access_end,
    )
    db.add(m)
    try:
        await db.commit()
    except (IntegrityError, OperationalError):
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to add membership",
        )
    await db.refresh(m)
    log_audit_event(
        user_id=current_user.id,
        action="membership_added",
        resource_type="ClientMembership",
        resource_id=m.id,
        details={
            "client_id": client_id,
            "user_id": resolved_user_id,
            "compliance_role": payload.compliance_role,
            "via_email": bool(payload.email),
            "invited": invited,
        },
    )
    # invited flag surfaces in the UI. dev_token MUST NOT travel
    # in the API response: it is a replayable JWT that grants tenant
    # access. We log it server-side instead so a developer running
    # DEBUG can still pluck it from structured logs.
    setattr(m, "invited", invited)
    setattr(m, "accept_invite_token", None)
    if dev_token and settings.DEBUG:
        logger.debug(
            "membership_invite_token_issued",
            client_id=client_id,
            user_id=resolved_user_id,
            token_preview=dev_token[:16] + "..." if len(dev_token) > 16 else dev_token,
        )
    return m


@router.delete(
    "/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    client_id: int,
    membership_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
    _gate: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_MANAGE_TEAM)
    ),
):
    """Revoke a team member's access (CLIENT-05 / RBAC-04)."""
    m = (
        await db.execute(
            select(ClientMembership).where(
                ClientMembership.id == membership_id,
                ClientMembership.client_id == client_id,
            )
        )
    ).scalar_one_or_none()
    if not m:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )
    revoked_user = m.user_id
    revoked_role = m.compliance_role
    await db.delete(m)
    try:
        await db.commit()
    except (IntegrityError, OperationalError):
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to revoke membership",
        )
    log_audit_event(
        user_id=current_user.id,
        action="membership_removed",
        resource_type="ClientMembership",
        resource_id=membership_id,
        details={
            "client_id": client_id,
            "user_id": revoked_user,
            "compliance_role": revoked_role,
        },
    )
