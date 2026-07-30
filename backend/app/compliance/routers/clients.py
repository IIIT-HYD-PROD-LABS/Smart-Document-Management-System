"""Client management router — Phase 9 CLIENT-01..03, CLIENT-05, CLIENT-07.

Endpoints:
  GET    /me                                  — list current user's memberships
                                                (no client gate; user has not
                                                selected one yet)
  POST   /                                    — atomic onboarding
                                                (CLIENT_CREATE, ca_consultant)
  GET    /{client_id}                         — single client detail
                                                (RLS-filtered)
  GET    /{client_id}/dashboard               — per-client KPI aggregates (CLIENT-03)
  PATCH  /{client_id}/branding                — update website + address
                                                (CLIENT_MANAGE_TEAM)
  POST   /{client_id}/logo                    — upload logo (multipart, ≤256KB,
                                                PNG/JPEG/WEBP only)
                                                (CLIENT_MANAGE_TEAM)
  DELETE /{client_id}/logo                    — clear logo
                                                (CLIENT_MANAGE_TEAM)

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
import base64
import logging
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.compliance.dependencies import (
    require_client_create_or_first_onboard,
    require_compliance_permission,
)
from app.compliance.models.client import Client
from app.compliance.models.membership import ClientMembership
from app.compliance.schemas.client import (
    ClientBrandingUpdate,
    ClientDetailOut,
    ClientOnboardRequest,
    ClientOut,
    DashboardAggregates,
    MembershipOut,
)
from app.compliance.services.client_service import (
    get_dashboard_aggregates,
    onboard_client,
)
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_async_db, get_bootstrap_async_db
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.utils.security import get_current_user


# Logo upload constraints. Cap at 256 KB pre-encode — keeps the resulting
# data URL under ~340 KB and well within typical Postgres TEXT column
# performance comfort. SVG is excluded on purpose (XSS risk via embedded
# scripts in <svg><script>).
LOGO_MAX_BYTES = 256 * 1024
LOGO_ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}

# First-bytes signatures (magic numbers) — second-line defence against
# clients that lie about Content-Type. We rely on the API gateway not
# being security-critical here, but a basic check is cheap.
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"
_WEBP_RIFF = b"RIFF"
_WEBP_FORMAT = b"WEBP"


def _validate_logo_magic(data: bytes, mime: str) -> bool:
    """Returns True if the first bytes of `data` match the declared `mime`."""
    if mime == "image/png":
        return data.startswith(_PNG_MAGIC)
    if mime == "image/jpeg":
        return data.startswith(_JPEG_MAGIC)
    if mime == "image/webp":
        return (
            len(data) >= 12
            and data[0:4] == _WEBP_RIFF
            and data[8:12] == _WEBP_FORMAT
        )
    return False


router = APIRouter(prefix="/clients", tags=["compliance-clients"])

_logger = logging.getLogger(__name__)


def _db_error_response(exc: SQLAlchemyError) -> None:
    """Log and re-raise a SQLAlchemyError with a safe message.

    One caller pattern for all unguarded client-routes so transient DB
    failures (connection timeout, RLS mismatch, stale pool state) produce
    503 instead of the global 500 catch-all.
    """
    _logger.warning("client_db_error", error=str(exc), exc_info=True)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Database temporarily unavailable. Please retry.",
    )


@router.get("/me", response_model=List[MembershipOut])
async def list_my_memberships(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db),
):
    """List the requesting user's compliance memberships across all clients.

    Used by the frontend client switcher (Plan 06). NOT gated by client_id
    because the user has not yet selected one — the switcher needs the full
    list to render its dropdown.

    The query bypasses the get_active_membership dep entirely so users can
    discover their tenancies before sending an X-Client-Id header.
    """
    from app.compliance.models.client import Client

    try:
        result = await db.execute(
            select(ClientMembership, Client.name)
            .outerjoin(Client, Client.id == ClientMembership.client_id)
            .where(ClientMembership.user_id == current_user.id)
            .order_by(ClientMembership.id.asc())
        )
    except SQLAlchemyError as exc:
        _db_error_response(exc)
    rows = result.all()
    out: list[MembershipOut] = []
    for membership, client_name in rows:
        out.append(
            MembershipOut(
                id=membership.id,
                user_id=membership.user_id,
                client_id=membership.client_id,
                compliance_role=membership.compliance_role,
                access_start=membership.access_start,
                access_end=membership.access_end,
                created_at=membership.created_at,
                client_name=client_name,
            )
        )
    return out


@router.post(
    "",
    response_model=ClientDetailOut,
    status_code=status.HTTP_201_CREATED,
)
async def onboard(
    payload: ClientOnboardRequest,
    current_user: User = Depends(get_current_user),
    # Onboarding inserts Client + Registrations + Memberships for a brand-new
    # client_id that no membership references yet, so under app_runtime the RLS
    # WITH CHECK on those tables is unsatisfiable. Run it under the owner
    # bootstrap session (RLS-bypassing); the require_client_create_or_first_onboard
    # gate above already authorizes the actor.
    db: AsyncSession = Depends(get_bootstrap_async_db),
    # CLIENT_CREATE gate with bootstrap exemption: a user with zero
    # memberships may self-service create their first client (the team
    # payload self-grants their role). After that, only ca_consultant
    # (the role with CLIENT_CREATE in the registry) can onboard new
    # clients via the API.
    _membership=Depends(require_client_create_or_first_onboard),
):
    """Atomic client onboarding — CLIENT-05.

    Service-layer wrapper handles Client + N Registrations + M Memberships in
    a single transaction. Audit log emitted by the service after commit.
    """
    client = await onboard_client(
        db=db,
        details=payload.details.model_dump(),
        registrations=[r.model_dump() for r in payload.registrations],
        team=[t.model_dump() for t in payload.team],
        actor=current_user,
    )
    # Eager-load relationships for the detail response.
    try:
        result = await db.execute(
            select(Client)
            .options(
                selectinload(Client.registrations),
                selectinload(Client.memberships),
            )
            .where(Client.id == client.id)
        )
    except SQLAlchemyError as exc:
        _db_error_response(exc)
    return result.scalar_one()


@router.get("/{client_id}", response_model=ClientDetailOut)
async def get_client(
    client_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """Fetch a single client (RLS-filtered by membership)."""
    try:
        result = await db.execute(
            select(Client)
            .options(
                selectinload(Client.registrations),
                selectinload(Client.memberships),
            )
            .where(Client.id == client_id)
        )
    except SQLAlchemyError as exc:
        _db_error_response(exc)
    client = result.scalar_one_or_none()
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
async def client_dashboard(
    client_id: int,
    _membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """Real-time per-client dashboard aggregates — CLIENT-03 / D-18."""
    return await get_dashboard_aggregates(db, client_id=client_id)


def _assert_path_matches_membership(
    client_id: int, membership: ClientMembership
) -> None:
    """Defence-in-depth tenant isolation. RLS on compliance_clients
    already filters cross-tenant writes (the row is invisible under
    `tenant_isolation` PERMISSIVE/ALL policy), so the SELECT below
    returns None and the handler 404s. This explicit check fails
    faster + makes the contract self-documenting + survives a future
    RLS regression."""
    if client_id != membership.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Path client_id does not match active tenant.",
        )


@router.patch("/{client_id}/branding", response_model=ClientOut)
async def update_branding(
    client_id: int,
    payload: ClientBrandingUpdate,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_MANAGE_TEAM)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """Update website + address for a client (logo has its own endpoint)."""
    _assert_path_matches_membership(client_id, membership)
    try:
        client = await db.get(Client, client_id)
    except SQLAlchemyError as exc:
        _db_error_response(exc)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    data = payload.model_dump(exclude_unset=True)
    if "website" in data:
        client.website = data["website"] or None
    if "address" in data:
        client.address = data["address"] or None

    try:
        await db.commit()
    except SQLAlchemyError as exc:
        _db_error_response(exc)
    await db.refresh(client)

    log_audit_event(
        user_id=membership.user_id,
        action="client_branding_updated",
        resource_type="Client",
        resource_id=client.id,
        details={"fields": sorted(data.keys())},
    )
    return client


@router.post("/{client_id}/logo", response_model=ClientOut)
async def upload_logo(
    client_id: int,
    file: UploadFile = File(...),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_MANAGE_TEAM)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """Upload (or replace) a client's logo. Stored as a base64 data URL
    in compliance_clients.logo_url. PNG/JPEG/WEBP only; SVG rejected
    (XSS risk). 256 KB pre-encode cap, enforced via streaming reads so
    a hostile caller can't burn memory by lying about Content-Length."""
    _assert_path_matches_membership(client_id, membership)
    mime = (file.content_type or "").lower()
    if mime not in LOGO_ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported logo type '{mime or 'unknown'}'. "
                f"Allowed: {sorted(LOGO_ALLOWED_MIME)}"
            ),
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > LOGO_MAX_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Logo too large (max {LOGO_MAX_BYTES // 1024} KB)"
                ),
            )
        chunks.append(chunk)
    blob = b"".join(chunks)

    if not _validate_logo_magic(blob, mime):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Logo content doesn't match declared type '{mime}'"
            ),
        )

    try:
        client = await db.get(Client, client_id)
    except SQLAlchemyError as exc:
        _db_error_response(exc)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )

    encoded = base64.b64encode(blob).decode("ascii")
    client.logo_url = f"data:{mime};base64,{encoded}"

    try:
        await db.commit()
    except SQLAlchemyError as exc:
        _db_error_response(exc)
    await db.refresh(client)

    log_audit_event(
        user_id=membership.user_id,
        action="client_logo_uploaded",
        resource_type="Client",
        resource_id=client.id,
        details={"mime": mime, "bytes": total},
    )
    return client


@router.delete("/{client_id}/logo", response_model=ClientOut)
async def delete_logo(
    client_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_MANAGE_TEAM)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """Clear the client's logo (sets logo_url to NULL)."""
    _assert_path_matches_membership(client_id, membership)
    try:
        client = await db.get(Client, client_id)
    except SQLAlchemyError as exc:
        _db_error_response(exc)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    if client.logo_url is None:
        return client

    client.logo_url = None
    try:
        await db.commit()
    except SQLAlchemyError as exc:
        _db_error_response(exc)
    await db.refresh(client)

    log_audit_event(
        user_id=membership.user_id,
        action="client_logo_deleted",
        resource_type="Client",
        resource_id=client.id,
        details={},
    )
    return client
