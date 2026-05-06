"""Service layer for the notice review queue — Phase 10 CLASS-04.

Three operations exposed to routers:
  - enqueue_low_confidence : insert/update a row when a classifier confidence
                              < 0.75. Idempotent via PostgreSQL ON CONFLICT.
  - list_pending           : RLS-scoped pending rows for the active client.
  - assign_reviewer_label  : reviewer assigns final authority/type. Mutates
                              the parent ComplianceNotice and writes a
                              NoticeActivity (mutable timeline) + AuditLog
                              (immutable system trail) in the same transaction.

Per Phase 9 D-D pattern: the service is the SINGLE point of mutation for both
the review_queue row and the parent ComplianceNotice's classification. Routers
must NOT update review_queue or notice.authority/notice_type_id directly.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.compliance.models.notice import ComplianceNotice
from app.compliance.models.notice_type import NoticeType
from app.compliance.models.review_queue import NoticeReviewQueue
from app.compliance.services.activity_service import log_activity
from app.services.audit_service import log_audit_event


CONFIDENCE_THRESHOLD = Decimal("0.7500")


def derive_reason(
    authority_confidence: Optional[Decimal],
    type_confidence: Optional[Decimal],
) -> str:
    """Map a (authority_conf, type_conf) pair to a reason string.

    Returns one of:
      "low_authority_confidence"
      "low_type_confidence"
      "both"
    Caller guarantees at least one is < threshold.
    """
    auth_low = authority_confidence is not None and authority_confidence < CONFIDENCE_THRESHOLD
    type_low = type_confidence is not None and type_confidence < CONFIDENCE_THRESHOLD
    if auth_low and type_low:
        return "both"
    if auth_low:
        return "low_authority_confidence"
    return "low_type_confidence"


def enqueue_low_confidence(
    db: Session,
    *,
    notice: ComplianceNotice,
    predicted_authority: Optional[str],
    predicted_authority_confidence: Optional[Decimal],
    predicted_type_id: Optional[int],
    predicted_type_confidence: Optional[Decimal],
    model_version: str,
) -> Optional[NoticeReviewQueue]:
    """Insert/update a review queue row for a low-confidence prediction.

    Returns None if neither confidence is below the threshold (no enqueue needed).
    Otherwise returns the upserted row.

    Idempotent — relies on the UNIQUE constraint on notice_id; on conflict the
    new prediction overwrites the prior one (most recent classifier wins).
    """
    reason = None
    auth_low = (
        predicted_authority_confidence is not None
        and predicted_authority_confidence < CONFIDENCE_THRESHOLD
    )
    type_low = (
        predicted_type_confidence is not None
        and predicted_type_confidence < CONFIDENCE_THRESHOLD
    )
    if not (auth_low or type_low):
        return None
    reason = derive_reason(
        predicted_authority_confidence, predicted_type_confidence
    )

    stmt = (
        pg_insert(NoticeReviewQueue)
        .values(
            notice_id=notice.id,
            client_id=notice.client_id,
            predicted_authority=predicted_authority,
            predicted_authority_confidence=predicted_authority_confidence,
            predicted_type_id=predicted_type_id,
            predicted_type_confidence=predicted_type_confidence,
            model_version=model_version,
            reason=reason,
        )
        .on_conflict_do_update(
            index_elements=["notice_id"],
            set_={
                "predicted_authority": predicted_authority,
                "predicted_authority_confidence": predicted_authority_confidence,
                "predicted_type_id": predicted_type_id,
                "predicted_type_confidence": predicted_type_confidence,
                "model_version": model_version,
                "reason": reason,
                "reviewer_id": None,
                "reviewed_at": None,
                "reviewer_assigned_authority": None,
                "reviewer_assigned_type_id": None,
            },
        )
        .returning(NoticeReviewQueue.id)
    )
    result = db.execute(stmt)
    row_id = result.scalar_one()
    db.flush()
    return db.get(NoticeReviewQueue, row_id)


def list_pending(
    db: Session,
    *,
    client_id: Optional[int],
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[NoticeReviewQueue], int]:
    """Return pending rows + total count.

    Pending = reviewed_at IS NULL.

    If client_id is provided, filters in addition to RLS. RLS already scopes
    by current_setting('app.current_client_id'), but explicit filter provides
    a defense-in-depth boundary against context-var leaks.
    Cross-client mode (client_id=None) returns rows from all eligible clients
    (RLS handles the cross-client_view permission match).
    """
    base = select(NoticeReviewQueue).where(NoticeReviewQueue.reviewed_at.is_(None))
    count_base = select(func.count()).select_from(NoticeReviewQueue).where(
        NoticeReviewQueue.reviewed_at.is_(None)
    )
    if client_id is not None:
        base = base.where(NoticeReviewQueue.client_id == client_id)
        count_base = count_base.where(NoticeReviewQueue.client_id == client_id)

    base = (
        base.order_by(NoticeReviewQueue.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )

    items = list(db.execute(base).scalars().all())
    total = db.execute(count_base).scalar_one()
    return items, int(total)


def assign_reviewer_label(
    db: Session,
    *,
    review_id: int,
    user_id: int,
    authority: Optional[str],
    notice_type_id: Optional[int],
) -> NoticeReviewQueue:
    """Reviewer assigns final classification.

    Mutates:
      - review_queue: reviewer_id, reviewed_at, reviewer_assigned_*
      - parent ComplianceNotice: authority and/or notice_type_id (per request)
      - NoticeActivity (mutable timeline): type='assigned', details captures the
        reviewer override
      - AuditLog (immutable): action='review_queue_assigned', details captures
        before/after authority + notice_type_id

    Raises ValueError if review row not found.
    Raises ValueError if both authority and notice_type_id are None
    (caller should validate on the schema layer; defense in depth here).
    """
    if authority is None and notice_type_id is None:
        raise ValueError(
            "At least one of authority or notice_type_id must be supplied"
        )

    review = db.get(NoticeReviewQueue, review_id)
    if review is None:
        raise ValueError(f"Review queue row {review_id} not found")

    notice = db.get(ComplianceNotice, review.notice_id)
    if notice is None:
        raise ValueError(
            f"Parent notice {review.notice_id} not found for review {review_id}"
        )

    # Validate notice_type_id belongs to the assigned authority if both supplied.
    if notice_type_id is not None:
        nt = db.get(NoticeType, notice_type_id)
        if nt is None:
            raise ValueError(f"NoticeType {notice_type_id} not found")
        target_authority = authority or notice.authority
        if nt.authority != target_authority:
            raise ValueError(
                f"NoticeType {notice_type_id} (authority={nt.authority}) does "
                f"not match assigned authority {target_authority!r}"
            )

    before = {
        "authority": notice.authority,
        "notice_type_id": notice.notice_type_id,
    }

    now = datetime.now(timezone.utc)

    # 1. Update parent notice
    if authority is not None:
        notice.authority = authority
    if notice_type_id is not None:
        notice.notice_type_id = notice_type_id

    # 2. Mark review row reviewed
    review.reviewer_id = user_id
    review.reviewed_at = now
    review.reviewer_assigned_authority = authority
    review.reviewer_assigned_type_id = notice_type_id

    # 3. Activity row — using 'assigned' type since CHECK constraint only accepts
    #    the four canonical types from migration 0013. Reviewer-assignment is
    #    semantically an assignment of the correct classification.
    log_activity(
        db,
        notice_id=notice.id,
        user_id=user_id,
        type="assigned",
        details={
            "source": "review_queue",
            "review_id": review.id,
            "before_authority": before["authority"],
            "after_authority": notice.authority,
            "before_notice_type_id": before["notice_type_id"],
            "after_notice_type_id": notice.notice_type_id,
            "predicted_authority": review.predicted_authority,
            "predicted_authority_confidence": (
                float(review.predicted_authority_confidence)
                if review.predicted_authority_confidence is not None
                else None
            ),
            "predicted_type_id": review.predicted_type_id,
            "predicted_type_confidence": (
                float(review.predicted_type_confidence)
                if review.predicted_type_confidence is not None
                else None
            ),
            "model_version": review.model_version,
        },
    )

    db.commit()
    db.refresh(review)
    db.refresh(notice)

    # 4. Immutable audit (separate session)
    log_audit_event(
        user_id=user_id,
        action="review_queue_assigned",
        resource_type="ComplianceNotice",
        resource_id=notice.id,
        details={
            "review_id": review.id,
            "before_value": before,
            "after_value": {
                "authority": notice.authority,
                "notice_type_id": notice.notice_type_id,
            },
            "model_version": review.model_version,
        },
    )

    return review
