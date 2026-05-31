"""Notice CRUD + state transitions + bulk + chain + upload — Phase 9 LIFE-01..08.

Endpoint matrix (also documented in Plan 09-05 <interfaces>):

  GET    /notices                      NOTICE_VIEW         filter+paginate
  POST   /notices                      NOTICE_CREATE       manual metadata
  GET    /notices/{id}                 NOTICE_VIEW         detail
  PATCH  /notices/{id}                 NOTICE_CREATE       edit metadata
  PATCH  /notices/{id}/status          (target-dependent)  state transition
  POST   /notices/bulk                 NOTICE_BULK_UPDATE  partial-failure
  GET    /notices/{id}/chain           NOTICE_VIEW         recursive CTE
  POST   /notices/{id}/upload          NOTICE_CREATE       v1.0 storage reuse
  GET    /notices/{id}/activity        NOTICE_VIEW         timeline
  POST   /notices/{id}/activity/note   (drafter or creator) add note

Status transition permission mapping per Plan 04 contract:
  -> submitted              : NOTICE_SUBMIT
  -> resolved | dismissed   : NOTICE_APPROVE
  -> under_review | response_drafted : NOTICE_DRAFT_RESPONSE

Pitfall 8 mitigation: ALL status changes route through
notice_service.transition_notice_status — direct ORM `notice.status = ...`
is closed at the API boundary; PATCH /notices/{id} does NOT permit a
status field (NoticeUpdate omits it).
"""
from datetime import date as date_t
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.exc import (
    DataError,
    IntegrityError,
    OperationalError,
    StatementError,
)
from sqlalchemy.orm import Session

from app.compliance.dependencies import (
    get_active_membership,
    is_cross_client_mode,
    require_compliance_permission,
)
from app.compliance.models.membership import ClientMembership
from app.compliance.models.notice import (
    ComplianceNotice,
    NoticeActivity,
    NoticeTag,
)
from app.compliance.schemas.activity import ActivityOut, NoteAddRequest
from app.compliance.schemas.notice import (
    BulkUpdateRequest,
    BulkUpdateResponse,
    NoticeCreate,
    NoticeOut,
    NoticeStatusTransition,
    NoticeUpdate,
)
from app.compliance.services.activity_service import log_activity
from app.compliance.services.notice_service import (
    bulk_update_status,
    filter_notices,
    get_notice_chain,
    process_notice_intake,
    transition_notice_status,
)
from app.compliance.services.notice_state_machine import (
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
    NoticeStatus,
)
from app.compliance.services.permission_registry import (
    CompliancePermission,
    ComplianceRole,
    has_permission,
)
from app.compliance.schemas.extraction import (
    AcceptExtractionPayload,
    ExtractPreviewResponse,
    ExtractionResponse,
)
from app.compliance.services.extraction_coercion import (
    CoercionError,
    FIELD_COERCERS,
)
from app.database import get_db
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.config import settings
from app.services.storage_service import save_file, validate_magic_bytes
from app.utils.rate_limiter import limiter
from app.utils.security import get_current_user


router = APIRouter(prefix="/notices", tags=["compliance-notices"])


# Allowed upload content types for notice attachments. Matches D-10:
# reuse the v1.0 Document model + storage pipeline. content_type is
# client-spoofable, so `_read_validated_upload` ALSO magic-byte validates the
# bytes against the declared type (save_file itself does not).
_ALLOWED_UPLOAD_CONTENT_TYPES = (
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
)
_CONTENT_TYPE_TO_EXT = {
    "application/pdf": "pdf",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
}


def _read_validated_upload(file: UploadFile) -> tuple[bytes, str]:
    """Validate, size-cap, and magic-byte-check a notice upload.

    Returns (contents, ext). Raises:
      400 — content_type not allowed, or bytes do not match the declared type.
      413 — body exceeds settings.MAX_FILE_SIZE_MB.

    The size cap streams in 1 MB chunks BEFORE buffering the whole file, so an
    oversized upload cannot exhaust process memory (the global body-size
    middleware exempts multipart/form-data). These handlers are sync `def`, so
    we read the SpooledTemporaryFile directly rather than `await file.read()`.
    """
    if file.content_type not in _ALLOWED_UPLOAD_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, JPG, PNG accepted for notice uploads",
        )
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = file.file.read(1024 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Max size: {settings.MAX_FILE_SIZE_MB}MB",
            )
        chunks.append(chunk)
    contents = b"".join(chunks)
    ext = _CONTENT_TYPE_TO_EXT.get(file.content_type or "", "pdf")
    if not validate_magic_bytes(contents, ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match its declared type",
        )
    return contents, ext


def _permissions_for_target_status(target: NoticeStatus) -> tuple[CompliancePermission, ...]:
    """Map target status -> permissions that authorize the transition.

    Returns a tuple of permissions; the caller accepts the transition if the
    user has ANY of them. The `under_review` state is entered both by:
      - compliance_head starting their own review (NOTICE_REVIEW)
      - legal/staff/ca_consultant beginning to draft (NOTICE_DRAFT_RESPONSE)

    Pre-2026-05-06: this function returned a single permission and used
    NOTICE_DRAFT_RESPONSE for `under_review`, locking compliance_head out of
    starting review on their own notices (received -> under_review).
    """
    if target == NoticeStatus.SUBMITTED:
        return (CompliancePermission.NOTICE_SUBMIT,)
    if target in (NoticeStatus.RESOLVED, NoticeStatus.DISMISSED):
        return (CompliancePermission.NOTICE_APPROVE,)
    if target == NoticeStatus.UNDER_REVIEW:
        # Entered by reviewers (compliance_head) OR drafters
        return (
            CompliancePermission.NOTICE_REVIEW,
            CompliancePermission.NOTICE_DRAFT_RESPONSE,
        )
    # response_drafted, back-edits to draft
    return (CompliancePermission.NOTICE_DRAFT_RESPONSE,)


@router.get("", response_model=dict)
def list_notices(
    authority: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    notice_type_id: Optional[int] = Query(None),
    response_deadline_before: Optional[str] = Query(None),
    response_deadline_after: Optional[str] = Query(None),
    gstin_or_pan: Optional[str] = Query(None),
    assigned_user_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    """List/filter notices for the active client — LIFE-07.

    The service layer scopes by membership.client_id; RLS enforces tenancy
    even if the service-layer filter is missing or wrong. Pagination uses
    1-indexed page so callers map directly from `?page=1`.
    """
    try:
        before = (
            date_t.fromisoformat(response_deadline_before)
            if response_deadline_before
            else None
        )
        after = (
            date_t.fromisoformat(response_deadline_after)
            if response_deadline_after
            else None
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="response_deadline_before/after must be ISO date YYYY-MM-DD",
        )

    # A NUL byte reaches psycopg2 and raises ValueError -> 500. Reject it at
    # the boundary so a malformed filter cannot DoS the endpoint.
    if gstin_or_pan and "\x00" in gstin_or_pan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid gstin_or_pan",
        )

    items = filter_notices(
        db=db,
        client_id=membership.client_id,
        authority=authority,
        status=status_filter,
        notice_type_id=notice_type_id,
        response_deadline_before=before,
        response_deadline_after=after,
        gstin_or_pan=gstin_or_pan,
        assigned_user_id=assigned_user_id,
        page=page,
        page_size=page_size,
    )
    # RLS-respecting count query for pagination metadata. Same client_id
    # filter so the count matches what the user can actually see.
    total = (
        db.query(ComplianceNotice)
        .filter(ComplianceNotice.client_id == membership.client_id)
        .count()
    )
    return {
        "items": [NoticeOut.model_validate(n).model_dump(mode="json") for n in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post(
    "",
    response_model=NoticeOut,
    status_code=status.HTTP_201_CREATED,
)
def create_notice(
    payload: NoticeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_CREATE)
    ),
):
    """Create a notice with manual metadata — LIFE-03.

    The payload's client_id MUST match the active membership's client_id.
    Mismatch returns 403 — frontend is expected to set X-Client-Id and pass
    the same id in the body. RLS would also filter the resulting INSERT
    via WITH CHECK, but a 403 is more debuggable than a silent failure.
    """
    if payload.client_id != membership.client_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot create notice for non-active client",
        )
    n = ComplianceNotice(
        client_id=payload.client_id,
        notice_type_id=payload.notice_type_id,
        registration_id=payload.registration_id,
        parent_notice_id=payload.parent_notice_id,
        document_id=payload.document_id,
        notice_number=payload.notice_number,
        authority=payload.authority,
        status="received",
        received_date=payload.received_date,
        response_deadline=payload.response_deadline,
        hearing_date=payload.hearing_date,
        compliance_date=payload.compliance_date,
        appeal_deadline=payload.appeal_deadline,
        tax_demand=payload.tax_demand,
        interest=payload.interest,
        penalty=payload.penalty,
        total_liability=payload.total_liability,
        legal_sections=payload.legal_sections,
        assigned_user_id=payload.assigned_user_id,
        created_by_user_id=current_user.id,
    )
    db.add(n)
    db.flush()  # need n.id for tag rows
    for tag in payload.tags:
        db.add(NoticeTag(notice_id=n.id, tag=tag))
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to create notice",
        )
    db.refresh(n)
    log_audit_event(
        user_id=current_user.id,
        action="notice_created",
        resource_type="ComplianceNotice",
        resource_id=n.id,
        details={
            "after_value": {
                "notice_number": n.notice_number,
                "authority": n.authority,
                "client_id": n.client_id,
            },
        },
    )
    # Phase 10/11 — classify + risk-score and schedule deadline alerts at
    # intake so a notice does not wait for a manual move to under_review.
    process_notice_intake(n.id, n.response_deadline)
    return n


@router.get("/{notice_id}", response_model=NoticeOut)
def get_notice(
    notice_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    # Defense-in-depth: explicit client_id filter on top of RLS so an
    # accidental policy regression cannot leak cross-tenant rows.
    q = db.query(ComplianceNotice).filter(ComplianceNotice.id == notice_id)
    if not is_cross_client_mode():
        q = q.filter(ComplianceNotice.client_id == membership.client_id)
    n = q.first()
    if not n:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    return n


@router.patch("/{notice_id}", response_model=NoticeOut)
def update_notice(
    notice_id: int,
    payload: NoticeUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_CREATE)
    ),
):
    """Edit notice metadata, LIFE-03. Status changes go through /status."""
    # Mutations are single-client. In cross-client mode get_active_membership
    # supplies an arbitrary eligible membership, so an edit would be scoped to
    # an unrelated client_id; cross-client mode is READ-only, refuse the write.
    if is_cross_client_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Metadata edits require a specific X-Client-Id",
        )
    q = db.query(ComplianceNotice).filter(
        ComplianceNotice.id == notice_id,
        ComplianceNotice.client_id == membership.client_id,
    )
    n = q.first()
    if not n:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    diff = payload.model_dump(exclude_unset=True)
    before = {k: getattr(n, k) for k in diff.keys()}
    deadline_changed = (
        "response_deadline" in diff
        and diff.get("response_deadline") != before.get("response_deadline")
    )
    for key, value in diff.items():
        setattr(n, key, value)
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to update notice",
        )
    db.refresh(n)

    # Phase 11 hardening — when response_deadline changes, cancel old
    # T-7/T-3/T-1/overdue jobs and reschedule against the new deadline so
    # alerts fire on the correct date.
    if deadline_changed:
        try:
            from app.compliance.services.scheduler import (
                cancel_deadline_alerts,
                schedule_deadline_alerts,
            )
            cancel_deadline_alerts(n.id)
            if n.response_deadline is not None and n.status in (
                "received", "under_review", "response_drafted"
            ):
                schedule_deadline_alerts(n.id, n.response_deadline)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "deadline-change reschedule failed for notice %d (non-fatal)",
                n.id,
            )

    log_audit_event(
        user_id=current_user.id,
        action="notice_updated",
        resource_type="ComplianceNotice",
        resource_id=n.id,
        details={
            "before_value": {k: str(v) for k, v in before.items()},
            "after_value": {k: str(v) for k, v in diff.items()},
        },
    )
    return n


def _notify_notice_assigned(
    *,
    client_id: int,
    notice: ComplianceNotice,
    assignee_user_id: int,
    inviter_user_id: int,
) -> None:
    """Publish a WebSocket notification to the assignee.

    Re-uses the `notifications:{client_id}` Redis pubsub channel that
    `NotificationBell` subscribes to via `/api/compliance/ws/notifications`,
    so the assignee gets a real-time toast without a page refresh. We
    intentionally bypass `dispatch_alert` because the
    `notice_alert_log.alert_type` column has a CHECK constraint and a
    new `notice_assigned` value would require a migration; the websocket
    envelope is enough for in-app surfacing and the standard audit row
    still records the assignment immutably.
    """
    try:
        import json
        import redis as redis_lib
        from app.config import settings

        r = redis_lib.from_url(settings.REDIS_URL)
        envelope = {
            "type": "notice_assigned",
            "recipient_user_id": assignee_user_id,
            "payload": {
                "client_id": client_id,
                "notice_id": notice.id,
                "notice_number": notice.notice_number,
                "authority": notice.authority,
                "response_deadline": (
                    notice.response_deadline.isoformat()
                    if notice.response_deadline else None
                ),
                "inviter_user_id": inviter_user_id,
            },
        }
        r.publish(f"notifications:{client_id}", json.dumps(envelope))
    except Exception:
        import logging
        logging.getLogger(__name__).warning(
            "notice_assigned_notify_failed notice_id=%d assignee=%d",
            int(notice.id), int(assignee_user_id),
        )


@router.post("/{notice_id}/assign", response_model=NoticeOut)
def assign_notice(
    notice_id: int,
    payload: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_CREATE)
    ),
):
    """Assign (or reassign) a notice to a team member.

    Body: `{"assigned_user_id": <int> | null}`. Passing null clears the
    assignment. The assignee must hold an active ClientMembership on the
    notice's client; otherwise we refuse with 400 (the FK alone would
    accept any users.id, including someone from a different tenant who
    should never see this notice).

    Side effects: writes a `notice_assigned` NoticeActivity row, an
    immutable AuditLog entry, and pushes a real-time WebSocket
    notification to the new assignee.
    """
    # Defense-in-depth: explicit client_id filter on top of RLS so an
    # accidental policy regression cannot let tenant A reassign tenant B's
    # notice.
    n = (
        db.query(ComplianceNotice)
        .filter(
            ComplianceNotice.id == notice_id,
            ComplianceNotice.client_id == membership.client_id,
        )
        .first()
    )
    if not n:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    if "assigned_user_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="assigned_user_id is required (use null to clear)",
        )
    new_assignee_id = payload.get("assigned_user_id")

    if new_assignee_id is not None:
        member = (
            db.query(ClientMembership)
            .filter(
                ClientMembership.user_id == new_assignee_id,
                ClientMembership.client_id == n.client_id,
            )
            .first()
        )
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"User {new_assignee_id} has no membership on this client. "
                    "Invite them first via "
                    f"POST /api/compliance/clients/{n.client_id}/memberships."
                ),
            )

    before = n.assigned_user_id
    n.assigned_user_id = new_assignee_id
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to assign notice",
        )
    db.refresh(n)

    # log_activity's param is `type` and the only assignment value accepted by
    # VALID_ACTIVITY_TYPES + the DB CHECK is "assigned". The audit row below
    # keeps the richer "notice_assigned" action string.
    log_activity(
        db=db,
        notice_id=n.id,
        type="assigned",
        user_id=current_user.id,
        details={
            "before_assigned_user_id": before,
            "after_assigned_user_id": new_assignee_id,
        },
    )
    log_audit_event(
        user_id=current_user.id,
        action="notice_assigned",
        resource_type="ComplianceNotice",
        resource_id=n.id,
        details={
            "client_id": n.client_id,
            "before_value": {"assigned_user_id": before},
            "after_value": {"assigned_user_id": new_assignee_id},
        },
    )

    if new_assignee_id is not None and new_assignee_id != before:
        _notify_notice_assigned(
            client_id=n.client_id,
            notice=n,
            assignee_user_id=new_assignee_id,
            inviter_user_id=current_user.id,
        )

    return n


@router.patch("/{notice_id}/status", response_model=NoticeOut)
def transition_status(
    notice_id: int,
    payload: NoticeStatusTransition,
    current_user: User = Depends(get_current_user),
    membership: ClientMembership = Depends(get_active_membership),
    db: Session = Depends(get_db),
):
    """Transition notice through state machine — LIFE-04.

    Permission gate is computed dynamically from the target status because
    different transitions require different permissions
    (NOTICE_SUBMIT vs NOTICE_APPROVE vs NOTICE_DRAFT_RESPONSE). Returns 422
    with valid_next_statuses when the requested transition is invalid.
    """
    # Mutations are single-client. In cross-client mode get_active_membership
    # returns an arbitrary eligible membership, so a transition would be
    # scoped to an unrelated client_id; refuse rather than guess.
    if is_cross_client_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Status transitions require a specific X-Client-Id (not '*')",
        )
    target = NoticeStatus(payload.new_status)
    try:
        role = ComplianceRole(membership.compliance_role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid compliance role: {membership.compliance_role}",
        )
    accepted_perms = _permissions_for_target_status(target)
    if not any(has_permission(role, p) for p in accepted_perms):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role '{role.value}' lacks any of permissions "
                f"{[p.value for p in accepted_perms]} "
                f"for transition to '{target.value}'"
            ),
        )
    try:
        n = transition_notice_status(
            db=db,
            notice_id=notice_id,
            new_status=target,
            user=current_user,
            reason=payload.reason,
            client_id=membership.client_id,
        )
    except InvalidTransitionError:
        # Reload current status for the helpful error payload — the service
        # rolled back so the row is unchanged. Use a fresh query so the
        # session is clean. Scope to the caller's client_id so a foreign
        # notice's status cannot be probed as an oracle via this path.
        status_q = db.query(ComplianceNotice.status).filter(
            ComplianceNotice.id == notice_id
        )
        if not is_cross_client_mode():
            status_q = status_q.filter(
                ComplianceNotice.client_id == membership.client_id
            )
        current = status_q.scalar()
        valid: List[str] = []
        if current:
            valid = sorted(
                s.value for s in ALLOWED_TRANSITIONS.get(NoticeStatus(current), frozenset())
            )
        # Log the full exception server-side; do not surface raw exception
        # text to the API caller (CodeQL py/stack-trace-exposure). The
        # message field gets a curated string built from the known
        # current+target pair, which is all the client needs to render
        # the "X cannot move to Y" toast.
        import logging
        logging.getLogger(__name__).warning(
            "notice_invalid_transition notice_id=%d current=%r target=%r",
            int(notice_id), current, payload.new_status,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": (
                    f"Cannot transition from {current!r} to {payload.new_status!r}."
                ),
                "valid_next_statuses": valid,
            },
        )
    return n


@router.post("/bulk", response_model=BulkUpdateResponse)
def bulk_update(
    payload: BulkUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_BULK_UPDATE)
    ),
):
    """Bulk status update with partial-failure semantics — LIFE-08.

    NOTICE_BULK_UPDATE alone is NOT sufficient: it authorizes the bulk
    *mechanism*, but the actual transition still requires the same
    target-status permission that the single-notice PATCH enforces via
    _permissions_for_target_status. Without this re-check a role holding
    NOTICE_BULK_UPDATE but lacking e.g. NOTICE_APPROVE could mass-resolve
    notices it could not resolve one-by-one.
    """
    target = NoticeStatus(payload.new_status)
    try:
        role = ComplianceRole(membership.compliance_role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid compliance role: {membership.compliance_role}",
        )
    accepted_perms = _permissions_for_target_status(target)
    if not any(has_permission(role, p) for p in accepted_perms):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role '{role.value}' lacks any of permissions "
                f"{[p.value for p in accepted_perms]} "
                f"for bulk transition to '{target.value}'"
            ),
        )
    return bulk_update_status(
        db=db,
        notice_ids=payload.notice_ids,
        new_status=target,
        user=current_user,
        reason=payload.reason,
        client_id=membership.client_id,
    )


@router.get("/{notice_id}/chain")
def notice_chain(
    notice_id: int,
    max_depth: int = Query(10, ge=1, le=20),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    """Recursive CTE notice chain (ancestors + descendants) — LIFE-05.

    The CTE is scoped to the caller's client_id so a chain cannot walk
    across tenants via parent_notice_id. Cross-client mode is refused
    explicitly: get_active_membership would supply an arbitrary eligible
    client_id, which would silently filter the chain to one unrelated
    tenant rather than honestly widening it.
    """
    if is_cross_client_mode():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Notice chain requires a specific X-Client-Id (not '*')",
        )
    return get_notice_chain(
        db,
        notice_id=notice_id,
        max_depth=max_depth,
        client_id=membership.client_id,
    )


@router.post("/{notice_id}/upload", response_model=NoticeOut)
def upload_notice_file(
    notice_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_CREATE)
    ),
):
    """Upload a notice PDF/JPG/PNG — LIFE-01, LIFE-02 (D-10 reuses Document).

    Uses the v1.0 storage_service.save_file helper which returns
    (file_path_or_filename, s3_url). The Document row gets a notice_id FK
    so the OCR pipeline (if it later runs) can find the source notice;
    Phase 10 will trigger ML classification on this same row.
    """
    # Defense-in-depth: explicit client_id filter on top of RLS so an
    # accidental policy regression cannot let tenant A attach a document to
    # tenant B's notice.
    n = (
        db.query(ComplianceNotice)
        .filter(
            ComplianceNotice.id == notice_id,
            ComplianceNotice.client_id == membership.client_id,
        )
        .first()
    )
    if not n:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    contents, ext = _read_validated_upload(file)
    file_path, s3_url = save_file(
        file_bytes=contents,
        original_filename=file.filename or "notice",
    )
    d = Document(
        user_id=current_user.id,
        filename=file_path.split("/")[-1] if file_path else (file.filename or "notice"),
        original_filename=file.filename or "notice",
        file_type=ext,
        file_size=len(contents),
        file_path=file_path,
        s3_url=s3_url,
        status=DocumentStatus.PENDING,
        notice_id=notice_id,
    )
    db.add(d)
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to record uploaded document",
        )
    db.refresh(d)
    # Dispatch async OCR + classification (mirrors v1.0 documents router).
    # Failure is non-fatal: the file is saved and re-processing can be
    # re-dispatched later; raising would lose the audit trail and force
    # the user to re-upload.
    try:
        from app.tasks.document_tasks import process_document_task
        task = process_document_task.delay(d.id)
        d.celery_task_id = task.id
        db.commit()
    except Exception as e:  # pragma: no cover - depends on broker availability
        import structlog
        structlog.get_logger().error(
            "notice_celery_dispatch_failed",
            notice_id=notice_id,
            document_id=d.id,
            error=str(e),
        )
        # The Document row is ALREADY committed (line 500 above); rolling back
        # here only undoes the in-memory celery_task_id assignment. Do not
        # call db.rollback() — it would leave the session in an unclear
        # state for the subsequent first-upload-wins commit.
    # First upload becomes the notice's primary file so the detail page
    # has somewhere to link the "View original" button.
    if n.document_id is None:
        n.document_id = d.id
        try:
            db.commit()
        except (IntegrityError, OperationalError):
            db.rollback()
        db.refresh(n)
    # User-facing activity timeline (D-09).
    log_activity(
        db=db,
        notice_id=notice_id,
        user_id=current_user.id,
        type="file_attached",
        details={
            "document_id": d.id,
            "filename": d.original_filename,
            "size": d.file_size,
        },
    )
    db.commit()
    return n


@router.get("/{notice_id}/activity", response_model=List[ActivityOut])
def list_activity(
    notice_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    """List the user-facing activity timeline for a notice (D-09)."""
    # Defense-in-depth: join through ComplianceNotice and filter on the
    # caller's client_id so an RLS regression cannot leak cross-tenant
    # activity rows. NoticeActivity has no client_id of its own; the
    # parent notice is the canonical tenant anchor.
    rows = (
        db.query(NoticeActivity)
        .join(ComplianceNotice, NoticeActivity.notice_id == ComplianceNotice.id)
        .filter(
            NoticeActivity.notice_id == notice_id,
            ComplianceNotice.client_id == membership.client_id,
        )
        .order_by(NoticeActivity.created_at.desc())
        .all()
    )
    return rows


@router.post(
    "/{notice_id}/activity/note",
    response_model=ActivityOut,
    status_code=status.HTTP_201_CREATED,
)
def add_note(
    notice_id: int,
    payload: NoteAddRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(get_active_membership),
):
    """Add a note to the notice activity timeline (D-09).

    Permission: drafter or creator. Auditor (read-only) cannot add notes —
    note-adding is a write that would muddy the audit-only contract.
    """
    try:
        role = ComplianceRole(membership.compliance_role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid compliance role",
        )
    if not (
        has_permission(role, CompliancePermission.NOTICE_DRAFT_RESPONSE)
        or has_permission(role, CompliancePermission.NOTICE_CREATE)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role lacks permission to add notes",
        )
    # Defense-in-depth: explicit client_id filter on top of RLS so an
    # accidental policy regression cannot let one tenant write notes onto
    # another tenant's notice. log_activity takes no client_id of its own.
    q = db.query(ComplianceNotice).filter(ComplianceNotice.id == notice_id)
    if not is_cross_client_mode():
        q = q.filter(ComplianceNotice.client_id == membership.client_id)
    if q.first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    row = log_activity(
        db=db,
        notice_id=notice_id,
        user_id=current_user.id,
        type="note_added",
        details={"note": payload.note},
    )
    try:
        db.commit()
    except (IntegrityError, OperationalError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to save note",
        )
    db.refresh(row)
    return row


# ─────────────────────────────────────────────────────────────────────
# Phase 17 — AI extraction endpoints
# ─────────────────────────────────────────────────────────────────────


def _ocr_extract_text(file_bytes: bytes, file_ext: str) -> str:
    """Run v1.0 OCR / PDF / DOCX extraction on raw bytes. Returns extracted text."""
    from app.ml.classifier import extract_and_classify
    text, _category, _confidence = extract_and_classify(file_bytes, file_ext)
    return text or ""


@router.post(
    "/extract-preview",
    response_model=ExtractPreviewResponse,
    status_code=status.HTTP_200_OK,
)
@limiter.limit("12/minute")
def extract_preview(
    request: Request,
    response: Response,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_AI_EXTRACT)
    ),
):
    """Phase 17 D-19 — upload PDF/JPG/PNG, return extraction envelope + routing decision.

    No notice row or document row is persisted. The caller (frontend) shows
    the envelope alongside the manual create form so the user can review,
    accept, edit, or discard each field before saving.

    On HTTP 412 (PRECONDITION_FAILED) the tenant has no AICredential
    configured; user falls back to manual fill (D-14).
    """
    from app.compliance.services.extraction_routing_service import route_or_apply
    from app.compliance.services.notice_extractor_service import (
        NoticeExtractionCredentialMissingError,
        NoticeExtractionParseError,
        extract_notice_fields,
    )
    from app.compliance.services import ai_service

    contents, ext = _read_validated_upload(file)

    try:
        text = _ocr_extract_text(contents, ext)
    except Exception:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="OCR could not extract text from the uploaded file",
        )

    if not text.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No text could be extracted from the uploaded file",
        )

    try:
        envelope = extract_notice_fields(
            db,
            client_id=membership.client_id,
            user_id=current_user.id,
            text=text,
            notice_id=None,
        )
    except NoticeExtractionCredentialMissingError:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail={
                "code": "no_ai_credential",
                "message": (
                    "Connect an AI provider in settings to enable extraction. "
                    "You can still upload and fill the form manually."
                ),
                "settings_path": "/dashboard/settings/ai-credentials",
            },
        )
    except ai_service.AIOutOfScopeError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="AI provider declined this content as out of scope",
        )
    except NoticeExtractionParseError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider returned an unparseable response",
        )
    # AIAuthError / AIRateLimitError are subclasses of AIProviderError, so
    # they MUST be caught first. Never surface the provider response body
    # (the SDK echoes it into the exception string) to the API caller.
    except ai_service.AIAuthError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "AI provider rejected the configured credential. "
                "Check the key in Settings → AI."
            ),
        )
    except ai_service.AIRateLimitError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI provider rate-limited the request. Try again shortly.",
        )
    except ai_service.AIProviderError:
        import logging
        logging.getLogger(__name__).warning(
            "extract_preview_ai_provider_error", exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI provider returned an error; details have been logged.",
        )
    except Exception:  # noqa: BLE001
        import logging
        logging.getLogger(__name__).exception("extract_preview_unexpected_error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Extraction failed unexpectedly.",
        )

    decision = route_or_apply(envelope)
    return {"envelope": envelope, "decision": decision}


@router.get(
    "/{notice_id}/extraction",
    response_model=ExtractionResponse,
)
def get_extraction(
    notice_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
):
    """Phase 17 D-20 — return the persisted extraction artefact for a notice."""
    # Defense-in-depth: explicit client_id filter on top of RLS so an
    # accidental policy regression cannot leak cross-tenant rows.
    notice = (
        db.query(ComplianceNotice)
        .filter(
            ComplianceNotice.id == notice_id,
            ComplianceNotice.client_id == membership.client_id,
        )
        .first()
    )
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    return {
        "notice_id": notice.id,
        "extraction_status": notice.extraction_status,
        "extraction_confidence": notice.extraction_confidence,
        "extracted_by_provider": notice.extracted_by_provider,
        "extracted_at": notice.extracted_at,
        "envelope": notice.extracted_fields,
    }


@router.post(
    "/{notice_id}/accept-extraction",
    response_model=NoticeOut,
)
def accept_extraction(
    notice_id: int,
    payload: AcceptExtractionPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_AI_EXTRACT)
    ),
):
    """Phase 17 D-21 — copy accepted fields onto the canonical notice columns.

    Writes one audit row per accepted field carrying SHA-256 hashes of the
    original-extracted value and the actually-accepted value, plus a
    `was_edited` boolean. The notice's `extraction_status` flips to 'accepted'.

    Requires NOTICE_AI_EXTRACT AND NOTICE_UPDATE per D-21. We check
    NOTICE_AI_EXTRACT in the dependency and NOTICE_UPDATE inline here so
    the error message can distinguish the two failure modes.
    """
    import hashlib

    # NOTE: ClientMembership stores the role on `compliance_role`, not `role`.
    # Hitting `.role` raised AttributeError -> 500 for every accept-extraction
    # call regardless of permission. Confirmed by the agent that ran the
    # 4x2 RBAC matrix during Plan 18 prep.
    role = ComplianceRole(membership.compliance_role)
    if not has_permission(role, CompliancePermission.NOTICE_CREATE):
        # NOTICE_UPDATE is implemented via NOTICE_CREATE in the existing
        # permission registry (Phase 9 RBAC-01). PATCH /notices/{id} also
        # gates on NOTICE_CREATE so acceptance and manual edit share the
        # same gate.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Role lacks permission to update notice fields",
        )

    # Defense-in-depth: explicit client_id filter on top of RLS so an
    # accidental policy regression cannot let one tenant accept extracted
    # fields onto another tenant's notice.
    notice = (
        db.query(ComplianceNotice)
        .filter(
            ComplianceNotice.id == notice_id,
            ComplianceNotice.client_id == membership.client_id,
        )
        .first()
    )
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )

    # Upload-first flow (D-19): extract-preview is stateless, so a notice
    # created from that flow is still 'pending' with no envelope. When the
    # client replays the reviewed envelope, persist it now (status ->
    # 'completed') so acceptance has provenance to record and the detail
    # page's provenance disclosure renders. action='apply' skips the
    # review-queue enqueue: the user accepting here IS the human reviewer.
    if (
        notice.extraction_status not in ("completed", "accepted")
        and payload.envelope is not None
    ):
        from app.compliance.services.extraction_routing_service import (
            apply_extraction_to_notice,
        )

        # Persist the replayed envelope for provenance only; the reviewed
        # `items` below are the sole authority on which columns get written,
        # so do NOT auto-fill (it would resurrect fields the user discarded).
        apply_extraction_to_notice(
            db,
            notice,
            payload.envelope.model_dump(),
            {"action": "apply"},
            fill_columns=False,
        )

    if notice.extraction_status not in ("completed", "accepted"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Notice extraction_status is '{notice.extraction_status}'; "
                "must be 'completed' before fields can be accepted"
            ),
        )

    envelope = notice.extracted_fields or {}
    extracted_fields = envelope.get("fields") or {}

    # FIELD_COERCERS maps each model-owned schema field to its canonical
    # column AND a coercer. Only fields in this map back-populate a column;
    # the rest live on extracted_fields for reference. Coercing here (rather
    # than writing item.value raw via setattr) keeps a currency-formatted
    # amount or DD-MM-YYYY date from reaching the Numeric/Date column as a
    # raw string — which would surface as an uncaught StatementError/DataError
    # 500 instead of a user-actionable 422.
    accepted_count = 0
    for item in payload.items:
        if item.field not in FIELD_COERCERS:
            continue
        column, coerce = FIELD_COERCERS[item.field]
        original_payload = extracted_fields.get(item.field) or {}
        original_value = original_payload.get("value")
        raw_accepted = item.value
        try:
            coerced_value = coerce(raw_accepted)
        except CoercionError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Field '{item.field}' has an invalid value: {exc}",
            )
        was_edited = (str(original_value) != str(raw_accepted))

        setattr(notice, column, coerced_value)
        accepted_count += 1

        log_audit_event(
            user_id=current_user.id,
            action="notice_ai_extract_accepted",
            resource_type="compliance_notice",
            resource_id=notice.id,
            details={
                "field": item.field,
                "original_value_sha256": hashlib.sha256(
                    str(original_value or "").encode("utf-8", errors="ignore")
                ).hexdigest(),
                "accepted_value_sha256": hashlib.sha256(
                    str(raw_accepted or "").encode("utf-8", errors="ignore")
                ).hexdigest(),
                "was_edited": was_edited,
            },
        )

    notice.extraction_status = "accepted"
    try:
        db.commit()
    except (IntegrityError, OperationalError, DataError, StatementError):
        # DataError/StatementError are the defense-in-depth backstop: coercion
        # above should already have rejected bad values with a 422, so a DB
        # type error here means an unforeseen edge — fail clean, never 500.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to apply accepted extraction fields",
        )
    db.refresh(notice)
    return notice
