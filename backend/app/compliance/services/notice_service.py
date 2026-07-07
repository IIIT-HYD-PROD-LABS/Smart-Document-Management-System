"""ComplianceNotice service — Phase 9 LIFE-04, LIFE-05, LIFE-07, LIFE-08, AUDIT-02.

This module is the SINGLE point of mutation for notice status transitions.
Per CONTEXT D-03 / Pitfall 8: routers MUST NOT update ComplianceNotice.status
directly — they must call transition_notice_status() which:

  1. Validates the (current -> new) transition against the state machine.
  2. Writes a NoticeActivity row to the user-facing timeline (D-09).
  3. Writes an immutable AuditLog row via log_audit_event (AUDIT-02).

The two writes are intentionally NOT in the same transaction:
  - NoticeActivity is committed alongside the status change so the timeline
    can never drift from the data the user sees.
  - AuditLog is written via log_audit_event's own short-lived session
    (audit_service pattern), so an audit failure can never roll back the
    business operation. log_audit_event swallows exceptions internally.

get_notice_chain uses a depth-bounded recursive CTE (RESEARCH Pattern 5).
The bound is necessary because the parent_notice_id graph is user-curated
and can contain cycles introduced by data correction.

bulk_update_status implements per-row partial-failure semantics
(RESEARCH Pattern 8): each notice is processed in its own transaction;
a failure on one notice does not block subsequent notices.
"""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.models.notice import ComplianceNotice
from app.compliance.services.activity_service import log_activity
from app.compliance.services.notice_state_machine import (
    InvalidTransitionError,
    NoticeStatus,
    validate_transition,
)
from app.models.user import User
from app.services.audit_service import log_audit_event_strict


def process_notice_intake(notice_id: int, response_deadline=None) -> None:
    """Kick off post-creation processing for a freshly created notice.

    Dispatches the Phase 10 classify + risk-score pipeline and, when a
    deadline is known, schedules the T-7/T-3/T-1/overdue alerts. Wired into
    every notice-creation path (manual create + Gmail ingestion) so a notice
    is risk-scored, review-queue-routed, and alert-scheduled at intake rather
    than only when a human first moves it to under_review. Both steps are
    best-effort: a broker or scheduler outage must never fail the create, and
    the daily recompute_all_risk_scores cron is the recovery path for a missed
    classification.
    """
    import logging

    try:
        from app.tasks.compliance_tasks import classify_and_score_notice
        classify_and_score_notice.delay(notice_id)
    except Exception:
        logging.getLogger(__name__).exception(
            "intake classify dispatch failed for notice %d (non-fatal)", notice_id
        )
    if response_deadline is not None:
        try:
            from app.compliance.services.scheduler import schedule_deadline_alerts
            schedule_deadline_alerts(notice_id, response_deadline)
        except Exception:
            logging.getLogger(__name__).exception(
                "intake alert scheduling failed for notice %d (non-fatal)", notice_id
            )


async def transition_notice_status(
    db: AsyncSession,
    notice_id: int,
    new_status: NoticeStatus,
    user: User,
    reason: Optional[str] = None,
    client_id: Optional[int] = None,
) -> ComplianceNotice:
    """Atomic notice status transition. LIFE-04 / AUDIT-02.

    Loads the row with FOR UPDATE to serialize concurrent transitions on
    the same notice; validates against ALLOWED_TRANSITIONS; updates the
    status + status_changed_at columns; writes a NoticeActivity timeline
    row in the same DB transaction; and finally writes a system AuditLog
    row via log_audit_event (separate session — audit-of-record pattern).

    Phase 10: on Received -> Under Review transition, dispatches the
    classify_and_score_notice Celery task to the compliance queue so ML
    inference + rule-based risk scoring run async without blocking the
    status update. Per CONTEXT anti-pattern guidance, never auto-classify
    on Resolved/Dismissed transitions.

    Raises InvalidTransitionError if (current -> new_status) is not
    allowed by the state machine. The session is rolled back on failure
    so callers can recover; bulk_update_status relies on this contract.

    `client_id` (when supplied by the router) pins the FOR UPDATE load to
    the caller's tenant. Mutations are single-client; relying on RLS alone
    to scope the row meant an RLS regression could let a transition land on
    another tenant's notice. Defaults to None so existing service-layer
    callers/tests that run RLS-bypassed keep their behaviour.
    """
    q = select(ComplianceNotice).where(ComplianceNotice.id == notice_id)
    if client_id is not None:
        q = q.where(ComplianceNotice.client_id == client_id)
    notice = (await db.execute(q.with_for_update())).scalar_one()
    old_status_str = notice.status
    old_status = NoticeStatus(old_status_str)
    # Raises InvalidTransitionError if not allowed; caller catches in bulk path
    validate_transition(old_status, new_status)

    # Phase 12 RESEARCH-FINAL §1 #9 — gate `submitted` on response approval.
    # A notice cannot transition to `submitted` until its NoticeResponse
    # has reached `approved` status (Drafter → Reviewer → Legal → CFO).
    # H-D second hardening: lock_for_update=True closes the TOCTOU between
    # the response read and the notice UPDATE commit. The notice row is
    # already FOR UPDATE-locked above; locking the response row here means
    # a concurrent CFO approve/reject must wait until this transaction
    # commits or rolls back.
    if new_status == NoticeStatus.SUBMITTED and old_status != NoticeStatus.SUBMITTED:
        from app.compliance.services.response_service import is_response_approved
        if not await is_response_approved(db, notice_id=notice.id, lock_for_update=True):
            raise InvalidTransitionError(
                f"Cannot transition notice {notice.id} to 'submitted' — "
                "response is not approved. Complete the Drafter → Reviewer "
                "→ Legal → CFO workflow first."
            )

    notice.status = new_status.value
    notice.status_changed_at = datetime.now(timezone.utc)

    # User-facing activity timeline (D-09) — same transaction as status change
    # so the timeline cannot drift from the data.
    log_activity(
        db,
        notice_id=notice.id,
        user_id=user.id,
        type="status_change",
        details={
            "from": old_status_str,
            "to": new_status.value,
            "reason": reason,
        },
    )
    await db.commit()
    await db.refresh(notice)

    # Immutable system audit (AUDIT-02). Synchronous so the test contract
    # in test_audit_capture::test_status_change_captures_diff observes the
    # row immediately after the call returns.
    # Use the strict variant so that on dead-letter dispatch the
    # `regulatory_audit_write_failed` ERROR fires; ops dashboards alert on
    # it. notice status changes are regulatory events (received → under_review
    # → submitted → resolved) and silently losing them violates AUDIT-02.
    log_audit_event_strict(
        user_id=user.id,
        action="notice_status_changed",
        resource_type="ComplianceNotice",
        resource_id=notice.id,
        details={
            "before_value": old_status_str,
            "after_value": new_status.value,
            "reason": reason,
        },
    )

    # Phase 10 — auto-classify + risk score. Notices are now classified at
    # intake (process_notice_intake on create / Gmail ingest), so this
    # transition-time dispatch is only a fallback: it fires when a notice
    # reached under_review without an intake score yet (created before the
    # intake wiring, or a broker outage at create time). The
    # `risk_scored_at is None` guard prevents a redundant second
    # classification on the common path. Failure here is non-fatal — the daily
    # `recompute_all_risk_scores` cron (app/tasks/__init__.py) is the recovery.
    if (
        old_status == NoticeStatus.RECEIVED
        and new_status == NoticeStatus.UNDER_REVIEW
        and notice.risk_scored_at is None
    ):
        try:
            from app.tasks.compliance_tasks import classify_and_score_notice
            classify_and_score_notice.delay(notice.id)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to dispatch classify_and_score_notice for notice %d "
                "(non-fatal — daily recompute will pick this up)",
                notice.id,
            )

    # Phase 11 — schedule deadline-based alerts (T-7/T-3/T-1/overdue) on
    # entry into Under Review (when the deadline is firmest). Cancel all
    # scheduled alerts on transition to a terminal status.
    try:
        from app.compliance.services.scheduler import (
            cancel_deadline_alerts,
            schedule_deadline_alerts,
        )
        if new_status in (NoticeStatus.RESOLVED, NoticeStatus.DISMISSED, NoticeStatus.SUBMITTED):
            cancel_deadline_alerts(notice.id)
        elif new_status == NoticeStatus.UNDER_REVIEW and notice.response_deadline:
            schedule_deadline_alerts(notice.id, notice.response_deadline)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to (re)schedule deadline alerts for notice %d (non-fatal)",
            notice.id,
        )

    return notice


async def get_notice_chain(
    db: AsyncSession,
    notice_id: int,
    max_depth: int = 10,
    client_id: Optional[int] = None,
) -> list[dict]:
    """Recursive CTE returning ancestors + descendants of `notice_id`.

    LIFE-05 / RESEARCH Pattern 5. Returns a list of dicts (id,
    parent_notice_id, notice_number, status, authority, depth) in
    depth-sorted order. depth < 0 = ancestor, depth = 0 = self,
    depth > 0 = descendant.

    Cycle protection is via depth bound, NOT PostgreSQL CYCLE clause:
    the bound is portable across PG versions and bounds memory in the
    worst case. max_depth defaults to 10 — well above the 5-link
    depth observed in real-world Indian compliance trees (SCN ->
    Assessment -> Demand -> Appeal -> Remand).

    `client_id` (supplied by the router for the single-client path) pins
    every CTE member to one tenant so the parent_notice_id graph cannot
    be walked across tenants if RLS regresses. The `:cid IS NULL` guard
    keeps the predicate inert for RLS-bypassed service/test callers that
    pass client_id=None.
    """
    sql = text(
        """
        WITH RECURSIVE
        ancestors AS (
            SELECT id, parent_notice_id, notice_number, status, authority,
                   0 AS depth
              FROM compliance_notices
             WHERE id = :nid
               AND (CAST(:cid AS integer) IS NULL OR client_id = CAST(:cid AS integer))
            UNION ALL
            SELECT n.id, n.parent_notice_id, n.notice_number, n.status,
                   n.authority, a.depth - 1
              FROM compliance_notices n
              JOIN ancestors a ON n.id = a.parent_notice_id
             WHERE a.depth > -CAST(:max_depth AS integer)
               AND (CAST(:cid AS integer) IS NULL OR n.client_id = CAST(:cid AS integer))
        ),
        descendants AS (
            SELECT id, parent_notice_id, notice_number, status, authority,
                   0 AS depth
              FROM compliance_notices
             WHERE id = :nid
               AND (CAST(:cid AS integer) IS NULL OR client_id = CAST(:cid AS integer))
            UNION ALL
            SELECT n.id, n.parent_notice_id, n.notice_number, n.status,
                   n.authority, d.depth + 1
              FROM compliance_notices n
              JOIN descendants d ON n.parent_notice_id = d.id
             WHERE d.depth < :max_depth
               AND (CAST(:cid AS integer) IS NULL OR n.client_id = CAST(:cid AS integer))
        )
        SELECT id, parent_notice_id, notice_number, status, authority, depth
          FROM ancestors WHERE depth < 0
        UNION
        SELECT id, parent_notice_id, notice_number, status, authority, depth
          FROM descendants
        ORDER BY depth;
        """
    )
    result = await db.execute(
        sql, {"nid": notice_id, "max_depth": max_depth, "cid": client_id}
    )
    return [dict(row._mapping) for row in result]


async def bulk_update_status(
    db: AsyncSession,
    notice_ids: list[int],
    new_status: NoticeStatus,
    user: User,
    reason: Optional[str] = None,
    client_id: Optional[int] = None,
) -> dict:
    """Per-row bulk status update with partial-failure semantics.

    LIFE-08 / RESEARCH Pattern 8. Each notice is processed in its own
    sub-transaction inside the caller's session; on InvalidTransitionError
    or any exception, the failed notice is rolled back but the loop
    continues. Returns:

        {
          "results": [{"id": 1, "success": True, "error": None}, ...],
          "summary": {"ok": 5, "failed": 2}
        }

    Frontend renders the per-row error indicators from `results` and
    the "Updated 5 of 7" toast from `summary`.
    """
    results: list[dict] = []
    for nid in notice_ids:
        # Idempotent: if the notice is already in the target state, treat as
        # no-op success. This prevents spurious failures when the UI sends a
        # bulk request after a single-row transition already moved the notice
        # to the desired state (stale selection / concurrent edit).
        status_q = select(ComplianceNotice.status).where(
            ComplianceNotice.id == nid
        )
        if client_id is not None:
            status_q = status_q.where(ComplianceNotice.client_id == client_id)
        current_status = (await db.execute(status_q)).scalar()
        if current_status is not None and current_status == new_status.value:
            results.append({"id": nid, "success": True, "error": None})
            continue
        try:
            await transition_notice_status(
                db, nid, new_status, user, reason, client_id=client_id
            )
        except InvalidTransitionError as exc:
            await db.rollback()
            results.append({"id": nid, "success": False, "error": str(exc)})
            continue
        except Exception:  # pragma: no cover - defensive
            await db.rollback()
            results.append(
                {"id": nid, "success": False, "error": "Internal error"}
            )
            continue
        results.append({"id": nid, "success": True, "error": None})
    ok = sum(1 for r in results if r["success"])
    return {
        "results": results,
        "summary": {"ok": ok, "failed": len(results) - ok},
    }


async def filter_notices(
    db: AsyncSession,
    client_id: int,
    authority: Optional[str] = None,
    status: Optional[str] = None,
    notice_type_id: Optional[int] = None,
    response_deadline_before: Optional[date] = None,
    response_deadline_after: Optional[date] = None,
    gstin_or_pan: Optional[str] = None,
    assigned_user_id: Optional[int] = None,
    page: int = 1,
    page_size: int = 50,
) -> list[ComplianceNotice]:
    """Filter notices for a client with combinable predicates. LIFE-07.

    All filter parameters are optional and combine with AND semantics.
    Pagination uses 1-indexed `page` so callers can map directly from
    `?page=1` query strings. Result ordering is created_at DESC so the
    most recently captured notices land at the top of the list view.
    """
    q = select(ComplianceNotice).where(
        ComplianceNotice.client_id == client_id
    )
    if authority:
        q = q.where(ComplianceNotice.authority == authority)
    if status:
        q = q.where(ComplianceNotice.status == status)
    if notice_type_id is not None:
        q = q.where(ComplianceNotice.notice_type_id == notice_type_id)
    if response_deadline_before:
        q = q.where(
            ComplianceNotice.response_deadline <= response_deadline_before
        )
    if response_deadline_after:
        q = q.where(
            ComplianceNotice.response_deadline >= response_deadline_after
        )
    if assigned_user_id is not None:
        q = q.where(ComplianceNotice.assigned_user_id == assigned_user_id)
    if gstin_or_pan:
        # Local import to avoid a cycle through models/__init__ at module load
        from app.compliance.models.client import ClientRegistration

        q = q.join(
            ClientRegistration,
            ComplianceNotice.registration_id == ClientRegistration.id,
        ).where(
            ClientRegistration.value.ilike(f"%{gstin_or_pan}%")
        )
    offset = (page - 1) * page_size
    result = await db.execute(
        q.order_by(ComplianceNotice.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    return result.scalars().all()
