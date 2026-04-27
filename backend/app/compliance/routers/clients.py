"""Client management router — Phase 9 CLIENT-01..03, CLIENT-05, CLIENT-07.

Endpoints:
  GET  /me                          — list current user's memberships (no
                                       client gate; user has not selected one)
  POST /                            — atomic onboarding (CLIENT_CREATE, ca_consultant)
  GET  /{client_id}                 — single client detail (RLS-filtered)
  GET  /{client_id}/dashboard       — per-client KPI aggregates (CLIENT-03)

Per Plan 04: tenant context comes from X-Client-Id header via
TenantContextMiddleware. Routes that take {client_id} in the path are
gated by Depends(require_compliance_permission(...)) which validates the
user has an active membership for the active client (the membership
client_id MUST match the path client_id; the middleware sets the active
client from the header — frontends pass the same id in both).

GET /me is intentionally NOT gated by client context — the frontend
client-switcher needs to enumerate the user's memberships BEFORE selecting
one.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.compliance.dependencies import (
    get_active_membership,
    require_compliance_permission,
)
from app.compliance.models.client import Client
from app.compliance.models.membership import ClientMembership
from app.compliance.schemas.client import (
    ClientDetailOut,
    ClientOnboardRequest,
    DashboardAggregates,
    MembershipOut,
)
from app.compliance.services.client_service import (
    get_dashboard_aggregates,
    onboard_client,
)
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_db
from app.models.user import User
from app.utils.security import get_current_user


router = APIRouter(prefix="/clients", tags=["compliance-clients"])


@router.get("/me", response_model=List[MembershipOut])
def list_my_memberships(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the requesting user's compliance memberships across all clients.

    Used by the frontend client switcher (Plan 06). NOT gated by client_id
    because the user has not yet selected one — the switcher needs the full
    list to render its dropdown.

    The query bypasses the get_active_membership dep entirely so users can
    discover their tenancies before sending an X-Client-Id header.
    """
    rows = (
        db.query(ClientMembership)
        .filter(ClientMembership.user_id == current_user.id)
        .all()
    )
    return rows


@router.post(
    "",
    response_model=ClientDetailOut,
    status_code=status.HTTP_201_CREATED,
)
def onboard(
    payload: ClientOnboardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    # CLIENT_CREATE: only ca_consultant has it per registry. The dependency
    # also doubles as the active-membership gate so we know the calling
    # user is an active CA Consultant on SOME client (cross-client mode for
    # ca_consultant is allowed per is_cross_client_eligible()).
    _membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_CREATE)
    ),
):
    """Atomic client onboarding — CLIENT-05.

    Service-layer wrapper handles Client + N Registrations + M Memberships in
    a single transaction. Audit log emitted by the service after commit.
    """
    client = onboard_client(
        db=db,
        details=payload.details.model_dump(),
        registrations=[r.model_dump() for r in payload.registrations],
        team=[t.model_dump() for t in payload.team],
        actor=current_user,
    )
    # Eager-load relationships for the detail response.
    db.refresh(client)
    return client


@router.get("/{client_id}", response_model=ClientDetailOut)
def get_client(
    client_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    """Fetch a single client (RLS-filtered by membership)."""
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    return client


@router.get(
    "/{client_id}/dashboard",
    response_model=DashboardAggregates,
)
def client_dashboard(
    client_id: int,
    _membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    """Real-time per-client dashboard aggregates — CLIENT-03 / D-18."""
    return get_dashboard_aggregates(db, client_id=client_id)
