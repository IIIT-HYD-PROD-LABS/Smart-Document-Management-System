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

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.compliance.models.notice import ComplianceNotice
from app.compliance.services.activity_service import log_activity
from app.compliance.services.notice_state_machine import (
    InvalidTransitionError,
    NoticeStatus,
    validate_transition,
)
from app.models.user import User
from app.services.audit_service import log_audit_event


def transition_notice_status(
    db: Session,
    notice_id: int,
    new_status: NoticeStatus,
    user: User,
    reason: Optional[str] = None,
) -> ComplianceNotice:
    """Atomic notice status transition. LIFE-04 / AUDIT-02.

    Loads the row with FOR UPDATE to serialize concurrent transitions on
    the same notice; validates against ALLOWED_TRANSITIONS; updates the
    status + status_changed_at columns; writes a NoticeActivity timeline
    row in the same DB transaction; and finally writes a system AuditLog
    row via log_audit_event (separate session — audit-of-record pattern).

    Raises InvalidTransitionError if (current -> new_status) is not
    allowed by the state machine. The session is rolled back on failure
    so callers can recover; bulk_update_status relies on this contract.
    """
    notice = (
        db.query(ComplianceNotice)
        .filter(ComplianceNotice.id == notice_id)
        .with_for_update()
        .one()
    )
    old_status_str = notice.status
    old_status = NoticeStatus(old_status_str)
    # Raises InvalidTransitionError if not allowed; caller catches in bulk path
    validate_transition(old_status, new_status)

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
    db.commit()
    db.refresh(notice)

    # Immutable system audit (AUDIT-02). Synchronous so the test contract
    # in test_audit_capture::test_status_change_captures_diff observes the
    # row immediately after the call returns.
    log_audit_event(
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
    return notice


def get_notice_chain(
    db: Session, notice_id: int, max_depth: int = 10
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
    """
    sql = text(
        """
        WITH RECURSIVE
        ancestors AS (
            SELECT id, parent_notice_id, notice_number, status, authority,
                   0 AS depth
              FROM compliance_notices
             WHERE id = :nid
            UNION ALL
            SELECT n.id, n.parent_notice_id, n.notice_number, n.status,
                   n.authority, a.depth - 1
              FROM compliance_notices n
              JOIN ancestors a ON n.id = a.parent_notice_id
             WHERE a.depth > -:max_depth
        ),
        descendants AS (
            SELECT id, parent_notice_id, notice_number, status, authority,
                   0 AS depth
              FROM compliance_notices
             WHERE id = :nid
            UNION ALL
            SELECT n.id, n.parent_notice_id, n.notice_number, n.status,
                   n.authority, d.depth + 1
              FROM compliance_notices n
              JOIN descendants d ON n.parent_notice_id = d.id
             WHERE d.depth < :max_depth
        )
        SELECT id, parent_notice_id, notice_number, status, authority, depth
          FROM ancestors WHERE depth < 0
        UNION
        SELECT id, parent_notice_id, notice_number, status, authority, depth
          FROM descendants
        ORDER BY depth;
        """
    )
    result = db.execute(sql, {"nid": notice_id, "max_depth": max_depth})
    return [dict(row._mapping) for row in result]


def bulk_update_status(
    db: Session,
    notice_ids: list[int],
    new_status: NoticeStatus,
    user: User,
    reason: Optional[str] = None,
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
        try:
            transition_notice_status(db, nid, new_status, user, reason)
        except InvalidTransitionError as exc:
            db.rollback()
            results.append({"id": nid, "success": False, "error": str(exc)})
            continue
        except Exception:  # pragma: no cover - defensive
            db.rollback()
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


def filter_notices(
    db: Session,
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
    q = db.query(ComplianceNotice).filter(
        ComplianceNotice.client_id == client_id
    )
    if authority:
        q = q.filter(ComplianceNotice.authority == authority)
    if status:
        q = q.filter(ComplianceNotice.status == status)
    if notice_type_id is not None:
        q = q.filter(ComplianceNotice.notice_type_id == notice_type_id)
    if response_deadline_before:
        q = q.filter(
            ComplianceNotice.response_deadline <= response_deadline_before
        )
    if response_deadline_after:
        q = q.filter(
            ComplianceNotice.response_deadline >= response_deadline_after
        )
    if assigned_user_id is not None:
        q = q.filter(ComplianceNotice.assigned_user_id == assigned_user_id)
    if gstin_or_pan:
        # Local import to avoid a cycle through models/__init__ at module load
        from app.compliance.models.client import ClientRegistration

        q = q.join(
            ClientRegistration,
            ComplianceNotice.registration_id == ClientRegistration.id,
        ).filter(
            ClientRegistration.value.ilike(f"%{gstin_or_pan}%")
        )
    offset = (page - 1) * page_size
    return (
        q.order_by(ComplianceNotice.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
