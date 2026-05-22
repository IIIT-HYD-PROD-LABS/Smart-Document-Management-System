"""Review queue router — Phase 10 CLASS-04.

Endpoints under /api/compliance/review (mounted in main.py):

  GET    /pending          NOTICE_REVIEW   list pending rows (paginated)
  GET    /{review_id}      NOTICE_REVIEW   single row detail
  PATCH  /{review_id}/assign NOTICE_REVIEW reviewer assigns authority/type

All routes RLS-scoped via X-Client-Id header (Phase 9 TenantContextMiddleware).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.compliance.dependencies import (
    is_cross_client_mode,
    require_compliance_permission,
)
from app.compliance.models.membership import ClientMembership
from app.compliance.schemas.review_queue import (
    ReviewQueueAssignRequest,
    ReviewQueueAssignResponse,
    ReviewQueueListResponse,
    ReviewQueueOut,
)
from app.compliance.services.permission_registry import CompliancePermission
from app.compliance.models.notice import ComplianceNotice
from app.compliance.services.review_queue_service import (
    assign_reviewer_label,
    enqueue_manual,
    list_pending,
)
from app.database import get_db

router = APIRouter(prefix="/review", tags=["compliance-review-queue"])


@router.get(
    "/pending",
    response_model=ReviewQueueListResponse,
    summary="List pending notice review queue items",
)
def list_pending_review(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    """List notices awaiting human review.

    NOTICE_VIEW grants read access; PATCH /assign separately requires
    NOTICE_REVIEW. Read-mostly clients (auditor, finance_team) can see what
    is queued without being able to assign labels.
    """
    client_id = None if is_cross_client_mode() else membership.client_id
    items, total = list_pending(
        db, client_id=client_id, page=page, page_size=page_size
    )
    return ReviewQueueListResponse(
        items=[ReviewQueueOut.model_validate(r) for r in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get(
    "/{review_id}",
    response_model=ReviewQueueOut,
    summary="Get a single review queue row",
)
def get_review(
    review_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    from app.compliance.models.review_queue import NoticeReviewQueue

    # Defense-in-depth: explicit client_id filter on top of RLS.
    q = db.query(NoticeReviewQueue).filter(NoticeReviewQueue.id == review_id)
    if not is_cross_client_mode():
        q = q.filter(NoticeReviewQueue.client_id == membership.client_id)
    row = q.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review queue row {review_id} not found",
        )
    return ReviewQueueOut.model_validate(row)


@router.post(
    "/manual-enqueue/{notice_id}",
    response_model=ReviewQueueOut,
    status_code=status.HTTP_201_CREATED,
    summary="Operator flags a notice for human review",
)
def manual_enqueue(
    notice_id: int,
    body: dict | None = None,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    """Flag a notice for human re-classification.

    Useful when the rule-based or BERT classifier was confident but the
    operator disagrees (the predicted authority or type looks wrong, or
    the ner extractor missed key entities). Bypasses the 0.75 confidence
    gate; the row lands with `reason="manual_flag"` and
    `model_version="manual"` so it sorts separately in the UI.

    Body (optional): `{"reason": "<= 36 char free-text note>"}`. The note
    is appended to the reason field as `manual_flag:<note>` so the
    reviewer sees the operator's hint without a second fetch.
    """
    notice = (
        db.query(ComplianceNotice)
        .filter(ComplianceNotice.id == notice_id)
        .first()
    )
    if notice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notice {notice_id} not found",
        )
    reason_note = (body or {}).get("reason") if isinstance(body, dict) else None
    row = enqueue_manual(
        db,
        notice=notice,
        flagged_by_user_id=membership.user_id,
        reason_note=str(reason_note) if reason_note else None,
    )
    return ReviewQueueOut.model_validate(row)


@router.patch(
    "/{review_id}/assign",
    response_model=ReviewQueueAssignResponse,
    summary="Reviewer assigns authoritative classification",
)
def assign_review(
    review_id: int,
    body: ReviewQueueAssignRequest,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_REVIEW)
    ),
    db: Session = Depends(get_db),
):
    try:
        row = assign_reviewer_label(
            db,
            review_id=review_id,
            user_id=membership.user_id,
            authority=body.authority,
            notice_type_id=body.notice_type_id,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )

    return ReviewQueueAssignResponse(
        review_id=row.id,
        notice_id=row.notice_id,
        assigned_authority=row.reviewer_assigned_authority,
        assigned_notice_type_id=row.reviewer_assigned_type_id,
        reviewed_at=row.reviewed_at,
    )
