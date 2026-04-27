"""Client membership management router — Phase 9 CLIENT-05, RBAC-04.

POST   /clients/{client_id}/memberships                  — add team member
DELETE /clients/{client_id}/memberships/{membership_id}  — revoke membership

Both endpoints require CLIENT_MANAGE_TEAM. Per the registry that's
compliance_head + ca_consultant only.

Audit logging:
  - membership_added   on successful POST
  - membership_removed on successful DELETE

These are written to the immutable system audit_log via log_audit_event
(separate session — failures cannot roll back business operations).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.schemas.client import MembershipCreate, MembershipOut
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_db
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.utils.security import get_current_user


router = APIRouter(
    prefix="/clients/{client_id}/memberships",
    tags=["compliance-memberships"],
)


@router.post(
    "",
    response_model=MembershipOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    client_id: int,
    payload: MembershipCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gate: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_MANAGE_TEAM)
    ),
):
    """Add a team member to a client (CLIENT-05 team step)."""
    existing = (
        db.query(ClientMembership)
        .filter(
            ClientMembership.user_id == payload.user_id,
            ClientMembership.client_id == client_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has a membership for this client",
        )
    m = ClientMembership(
        user_id=payload.user_id,
        client_id=client_id,
        compliance_role=payload.compliance_role,
        access_start=payload.access_start,
        access_end=payload.access_end,
    )
    db.add(m)
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to create membership",
        )
    db.refresh(m)
    # Audit log — fire-and-forget; failures don't roll back the business op.
    log_audit_event(
        user_id=current_user.id,
        action="membership_added",
        resource_type="ClientMembership",
        resource_id=m.id,
        details={
            "client_id": client_id,
            "user_id": payload.user_id,
            "compliance_role": payload.compliance_role,
        },
    )
    return m


@router.delete(
    "/{membership_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_member(
    client_id: int,
    membership_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gate: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_MANAGE_TEAM)
    ),
):
    """Revoke a team member's access (CLIENT-05 / RBAC-04)."""
    m = (
        db.query(ClientMembership)
        .filter(
            ClientMembership.id == membership_id,
            ClientMembership.client_id == client_id,
        )
        .first()
    )
    if not m:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Membership not found",
        )
    revoked_user = m.user_id
    revoked_role = m.compliance_role
    db.delete(m)
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
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
