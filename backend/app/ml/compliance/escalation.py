"""Auto-escalation for Critical-risk notices — CONTEXT D-18..D-20.

Critical risk → Phase 11 alert pipeline notifies the Compliance Head per
client's escalation chain. v2.0 ships the activity-timeline + audit-log
side; cross-channel delivery (email/SMS/WebSocket) is Phase 11.

Cool-down: 24 hours minimum between re-escalations on the same notice.
The check queries NoticeActivity for prior `assigned` rows tagged
`source="critical_escalation"` to enforce this without a dedicated table.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import desc
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

ESCALATION_COOLDOWN = timedelta(hours=24)
ACTIVITY_SOURCE = "critical_escalation"


def find_compliance_head_user_id(db: Session, client_id: int) -> Optional[int]:
    """Return the user_id of the first active compliance_head member of the client.

    Returns None if no compliance_head is configured — caller should log a
    warning and proceed with NULL assignee so the notice still surfaces in
    the dashboard as Critical/needs assignment.
    """
    from app.compliance.middleware.auditor_expiry import is_membership_active
    from app.compliance.models.membership import ClientMembership

    candidates = (
        db.query(ClientMembership)
        .filter(
            ClientMembership.client_id == client_id,
            ClientMembership.compliance_role == "compliance_head",
        )
        .order_by(ClientMembership.created_at)
        .all()
    )
    for m in candidates:
        if is_membership_active(m):
            return int(m.user_id)
    return None


def last_escalation_at(db: Session, notice_id: int) -> Optional[datetime]:
    """Return the created_at of the most recent escalation activity row,
    or None if the notice has never been escalated.

    Hardening (#17): the JSON filter is pushed to PostgreSQL via the
    `details->>'source'` operator so we don't materialize every `assigned`
    activity row for the notice (which would scale with reviewer/manual
    reassignment churn).
    """
    from app.compliance.models.notice import NoticeActivity

    row = (
        db.query(NoticeActivity)
        .filter(
            NoticeActivity.notice_id == notice_id,
            NoticeActivity.type == "assigned",
            NoticeActivity.details["source"].astext == ACTIVITY_SOURCE,
        )
        .order_by(desc(NoticeActivity.created_at))
        .first()
    )
    if row is None:
        return None
    ts = row.created_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def should_escalate(
    db: Session,
    *,
    notice,
    risk_tier: str,
    now: Optional[datetime] = None,
) -> bool:
    """Decide whether to escalate.

    Returns True iff:
      - risk_tier == 'critical', AND
      - (no prior critical_escalation NoticeActivity for this notice OR
         the most recent one is older than ESCALATION_COOLDOWN).

    Pure function aside from the DB query (no side effects). Caller is
    responsible for calling escalate() afterwards if True.
    """
    if risk_tier != "critical":
        return False
    last = last_escalation_at(db, notice.id)
    if last is None:
        return True
    now = now or datetime.now(timezone.utc)
    return (now - last) >= ESCALATION_COOLDOWN


def escalate(
    db: Session,
    *,
    notice,
    assessment,
    actor_user_id: Optional[int] = None,
) -> Optional[int]:
    """Perform the escalation side effects.

    Steps:
      1. Look up the active compliance_head user for this client.
      2. Reassign notice.assigned_user_id to that user (None if no head).
      3. Write a NoticeActivity row (type='assigned', details.source='critical_escalation').
      4. Write an immutable AuditLog row (action='notice_escalated').

    Returns the assigned user_id, or None if no compliance_head was available.

    Caller (compliance_tasks.classify_and_score_notice) wraps this in
    its try/except — escalation failure does NOT roll back the risk score
    that was already persisted.
    """
    from app.compliance.services.activity_service import log_activity
    from app.services.audit_service import log_audit_event_strict as log_audit_event

    head_user_id = find_compliance_head_user_id(db, notice.client_id)
    before_assigned = notice.assigned_user_id

    # Reassign even if head_user_id is None — this captures the
    # "needs assignment" UX state for downstream surfaces.
    if head_user_id is not None:
        notice.assigned_user_id = head_user_id
    else:
        logger.warning(
            "escalate: notice %d hit Critical tier but no compliance_head "
            "found for client %d — recording NULL-assigned activity",
            notice.id, notice.client_id,
        )

    log_activity(
        db,
        notice_id=notice.id,
        user_id=actor_user_id,
        type="assigned",
        details={
            "source": ACTIVITY_SOURCE,
            "before_assigned_user_id": before_assigned,
            "after_assigned_user_id": head_user_id,
            "risk_score": float(assessment.score),
            "risk_tier": assessment.tier,
            "model_version": assessment.model_version,
            "top_factors": [
                {
                    "feature": f.feature,
                    "contribution": round(f.contribution, 2),
                    "phrase": f.natural_language,
                }
                for f in assessment.top_factors
            ],
            "reason": "critical_risk",
            "automated": True,
        },
    )

    db.commit()
    db.refresh(notice)

    log_audit_event(
        user_id=actor_user_id,
        action="notice_escalated",
        resource_type="ComplianceNotice",
        resource_id=notice.id,
        details={
            "before_value": {"assigned_user_id": before_assigned},
            "after_value": {"assigned_user_id": head_user_id},
            "risk_score": float(assessment.score),
            "risk_tier": assessment.tier,
            "model_version": assessment.model_version,
            "reason": "critical_risk",
        },
    )

    # Phase 11 — fire alert dispatch on escalation. The alert task pulls
    # recipients (compliance_head + cfo by default) and fans out via email
    # + websocket. Failure to enqueue (broker down) is non-fatal — but
    # hardening (#4) requires we persist a notice_alert_log row marking
    # the dispatch as failed so /api/compliance/alerts/pending surfaces
    # the broken state. Without this, the escalation activity row + audit
    # log claim "escalated" while no alert ever queued.
    try:
        from app.tasks.alert_tasks import dispatch_notice_alert
        dispatch_notice_alert.delay(
            notice.id,
            "escalation",
            ["email", "websocket"],
            ["compliance_head", "cfo"],
        )
    except Exception as exc:
        logger.exception(
            "alert dispatch enqueue failed for escalated notice %d", notice.id,
        )
        try:
            from app.compliance.models.alert import NoticeAlertLog
            failed = NoticeAlertLog(
                notice_id=notice.id,
                client_id=notice.client_id,
                alert_type="escalation",
                recipient_user_id=head_user_id,
                channel="email",
                delivery_status="failed",
                error=f"broker_enqueue_failed: {type(exc).__name__}: {str(exc)[:500]}",
                payload={
                    "reason": "celery_broker_unavailable",
                    "risk_score": float(assessment.score),
                    "risk_tier": assessment.tier,
                },
            )
            db.add(failed)
            db.commit()
        except Exception:
            logger.exception(
                "failed to persist failed-dispatch row for notice %d", notice.id,
            )
            try:
                db.rollback()
            except Exception:
                pass

    return head_user_id
