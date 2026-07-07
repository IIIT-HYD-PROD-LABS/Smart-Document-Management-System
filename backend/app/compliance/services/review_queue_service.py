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
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.compliance.models.notice import ComplianceNotice
from app.compliance.models.notice_type import NoticeType
from app.compliance.models.review_queue import NoticeReviewQueue
from app.compliance.services.activity_service import log_activity
from app.services.audit_service import log_audit_event


CONFIDENCE_THRESHOLD = Decimal("0.7500")

# Until the BERT classifier (v2.1) ships, the rule-based ingestion path emits
# heuristic confidences derived from how strongly the extracted entities
# corroborate the authority + whether a notice_type_id was assigned. Tagged
# with this model_version so the frontend can render the source explicitly
# ("Heuristic" pill) and downstream metrics distinguish heuristic from BERT.
HEURISTIC_MODEL_VERSION = "rule_based_heuristic_v1"
MANUAL_MODEL_VERSION = "manual"


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


def compute_heuristic_confidence(
    notice: ComplianceNotice,
) -> tuple[Decimal, Decimal]:
    """Synthesise (authority_confidence, type_confidence) from rule-based
    signals already present on the notice. Used until BERT confidences land.

    Authority confidence (anchors on the regex extractor's hit list):
      * 0.92 if the extracted entity matches the authority
        (GST + gstins, IT + pans, MCA + cins)
      * 0.85 if RBI/SEBI with any extracted financial identifier (regex
        extractor does not yet have authority-specific patterns for them)
      * 0.55 otherwise (manual entry only, nothing to corroborate)

    Type confidence:
      * 0.90 if notice_type_id is set
      * 0.40 if notice_type_id is None (will trip the threshold gate)

    The thresholds match `CONFIDENCE_THRESHOLD = 0.7500`, so any notice
    lacking corroborating entities OR a type assignment will enqueue.
    """
    ner = dict(notice.ner_extracted_fields or {})
    gstins = ner.get("gstins") or []
    pans = ner.get("pans") or []
    cins = ner.get("cins") or []
    auth = (notice.authority or "").upper()
    has_any_entity = bool(gstins or pans or cins)

    if auth == "GST" and gstins:
        auth_conf = Decimal("0.9200")
    elif auth == "IT" and pans:
        auth_conf = Decimal("0.9200")
    elif auth == "MCA" and cins:
        auth_conf = Decimal("0.9200")
    elif auth in {"RBI", "SEBI"} and has_any_entity:
        auth_conf = Decimal("0.8500")
    else:
        auth_conf = Decimal("0.5500")

    if notice.notice_type_id is not None:
        type_conf = Decimal("0.9000")
    else:
        type_conf = Decimal("0.4000")

    return auth_conf, type_conf


async def enqueue_manual(
    db: AsyncSession,
    *,
    notice: ComplianceNotice,
    flagged_by_user_id: int,
    reason_note: Optional[str] = None,
) -> NoticeReviewQueue:
    """Operator-driven enqueue: a team member flags a notice they think
    the classifier got wrong, even if confidence was above the threshold.

    Bypasses the threshold check (this is an explicit "please look again"
    signal). Idempotent on notice_id like enqueue_low_confidence.
    """
    reason = "manual_flag"
    if reason_note:
        # Persist a short prefix of the user-supplied note inside the
        # 50-char reason field so the UI can show context without a
        # second query. Format: "manual_flag:<first 36 chars>".
        reason = f"manual_flag:{reason_note[:36]}"

    stmt = (
        pg_insert(NoticeReviewQueue)
        .values(
            notice_id=notice.id,
            client_id=notice.client_id,
            predicted_authority=notice.authority,
            predicted_authority_confidence=None,
            predicted_type_id=notice.notice_type_id,
            predicted_type_confidence=None,
            model_version=MANUAL_MODEL_VERSION,
            reason=reason,
        )
        .on_conflict_do_update(
            index_elements=["notice_id"],
            set_={
                "predicted_authority": notice.authority,
                "predicted_type_id": notice.notice_type_id,
                "model_version": MANUAL_MODEL_VERSION,
                "reason": reason,
                "reviewer_id": None,
                "reviewed_at": None,
                "reviewer_assigned_authority": None,
                "reviewer_assigned_type_id": None,
            },
        )
        .returning(NoticeReviewQueue.id)
    )
    result = await db.execute(stmt)
    row_id = result.scalar_one()
    await db.commit()

    log_audit_event(
        user_id=flagged_by_user_id,
        action="review_queue_manual_flag",
        resource_type="ComplianceNotice",
        resource_id=notice.id,
        details={"reason_note": reason_note, "review_id": row_id},
    )
    return await db.get(NoticeReviewQueue, row_id)


# Stays synchronous: shared with the Celery ingestion pipeline
# (app/tasks/compliance_tasks.py, app/email/services/ingestion_service.py,
# app/compliance/services/extraction_routing_service.py), none of which are
# in scope for the async migration. Not called from the review_queue router.
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


async def list_pending(
    db: AsyncSession,
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

    result = await db.execute(base)
    items = list(result.scalars().all())
    total = await db.scalar(count_base)
    return items, int(total)


async def assign_reviewer_label(
    db: AsyncSession,
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

    review = await db.get(NoticeReviewQueue, review_id)
    if review is None:
        raise ValueError(f"Review queue row {review_id} not found")

    notice = await db.get(ComplianceNotice, review.notice_id)
    if notice is None:
        raise ValueError(
            f"Parent notice {review.notice_id} not found for review {review_id}"
        )

    # Validate notice_type_id belongs to the assigned authority if both supplied.
    if notice_type_id is not None:
        nt = await db.get(NoticeType, notice_type_id)
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

    await db.commit()
    await db.refresh(review)
    await db.refresh(notice)

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
