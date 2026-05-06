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
    UploadFile,
    status,
)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.compliance.dependencies import (
    get_active_membership,
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
from app.database import get_db
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.services.storage_service import save_file
from app.utils.security import get_current_user


router = APIRouter(prefix="/notices", tags=["compliance-notices"])


# Allowed upload content types for notice attachments. Matches D-10:
# reuse the v1.0 Document model + storage pipeline. Magic-byte validation
# happens inside save_file via the v1.0 helper.
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
    return n


@router.get("/{notice_id}", response_model=NoticeOut)
def get_notice(
    notice_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    n = (
        db.query(ComplianceNotice)
        .filter(ComplianceNotice.id == notice_id)
        .first()
    )
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
    """Edit notice metadata — LIFE-03. Status changes go through /status."""
    n = (
        db.query(ComplianceNotice)
        .filter(ComplianceNotice.id == notice_id)
        .first()
    )
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
        )
    except InvalidTransitionError as e:
        # Reload current status for the helpful error payload — the service
        # rolled back so the row is unchanged. Use a fresh query so the
        # session is clean.
        current = (
            db.query(ComplianceNotice.status)
            .filter(ComplianceNotice.id == notice_id)
            .scalar()
        )
        valid: List[str] = []
        if current:
            valid = sorted(
                s.value for s in ALLOWED_TRANSITIONS.get(NoticeStatus(current), frozenset())
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": str(e),
                "valid_next_statuses": valid,
            },
        )
    return n


@router.post("/bulk", response_model=BulkUpdateResponse)
def bulk_update(
    payload: BulkUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    _gate: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_BULK_UPDATE)
    ),
):
    """Bulk status update with partial-failure semantics — LIFE-08."""
    target = NoticeStatus(payload.new_status)
    return bulk_update_status(
        db=db,
        notice_ids=payload.notice_ids,
        new_status=target,
        user=current_user,
        reason=payload.reason,
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
    """Recursive CTE notice chain (ancestors + descendants) — LIFE-05."""
    return get_notice_chain(db, notice_id=notice_id, max_depth=max_depth)


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
    n = (
        db.query(ComplianceNotice)
        .filter(ComplianceNotice.id == notice_id)
        .first()
    )
    if not n:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notice not found",
        )
    if file.content_type not in _ALLOWED_UPLOAD_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF, JPG, PNG accepted for notice uploads",
        )
    contents = file.file.read()
    file_path, s3_url = save_file(
        file_bytes=contents,
        original_filename=file.filename or "notice",
    )
    ext = _CONTENT_TYPE_TO_EXT.get(file.content_type or "", "pdf")
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
    rows = (
        db.query(NoticeActivity)
        .filter(NoticeActivity.notice_id == notice_id)
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
