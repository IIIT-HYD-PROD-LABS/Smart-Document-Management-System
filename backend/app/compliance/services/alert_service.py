"""Phase 11 alert dispatch — orchestrator for multi-channel notice alerts.

Public surface:
  - dispatch_alert(db, *, notice, alert_type, channels, recipients, payload)
    Idempotent fan-out to email / SMS / WebSocket. Each delivery becomes a
    notice_alert_log row (UNIQUE on notice_id + alert_type + recipient_user_id +
    channel ⇒ retries are no-ops).

  - resolve_recipients(db, notice, recipient_roles)
    Looks up active ClientMembership users matching the requested roles
    and returns (user_id, email, phone) tuples. Skips members with
    expired auditor windows.

Channel implementations live in `senders.py` so each can be tested in
isolation. The orchestrator only knows the AlertChannel interface.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.compliance.middleware.auditor_expiry import is_membership_active
from app.compliance.models.alert import NoticeAlertLog
from app.compliance.models.membership import ClientMembership
from app.compliance.models.notice import ComplianceNotice
from app.models.user import User

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────
# Recipient resolution
# ──────────────────────────────────────────────────────────────────────

def resolve_recipients(
    db: Session,
    *,
    client_id: int,
    recipient_roles: Iterable[str],
) -> list[dict]:
    """Return list of {user_id, email, phone} for active members matching roles."""
    if not recipient_roles:
        return []
    roles = list(recipient_roles)
    rows = (
        db.query(ClientMembership, User)
        .join(User, User.id == ClientMembership.user_id)
        .filter(
            ClientMembership.client_id == client_id,
            ClientMembership.compliance_role.in_(roles),
        )
        .all()
    )
    out: list[dict] = []
    for mem, user in rows:
        if not is_membership_active(mem):
            continue
        out.append({
            "user_id": int(user.id),
            "email": user.email,
            "phone": getattr(user, "phone", None),
            "compliance_role": mem.compliance_role,
        })
    # Stable order: priority by role rank when supplied as iterable
    role_order = {r: idx for idx, r in enumerate(roles)}
    out.sort(key=lambda r: role_order.get(r["compliance_role"], 999))
    return out


# ──────────────────────────────────────────────────────────────────────
# Dispatch orchestrator
# ──────────────────────────────────────────────────────────────────────

def dispatch_alert(
    db: Session,
    *,
    notice: ComplianceNotice,
    alert_type: str,
    channels: list[str],
    recipients: list[dict],
    payload: Optional[dict[str, Any]] = None,
) -> dict[str, int]:
    """Fan out an alert across channels for each recipient.

    Args:
        notice: the ComplianceNotice that's the subject of the alert.
        alert_type: one of model_alert.VALID_ALERT_TYPES.
        channels: subset of ('email', 'sms', 'websocket').
        recipients: from resolve_recipients().
        payload: optional dict baked into the alert body.

    Returns: {sent, queued, failed, skipped} counters.

    Idempotency: each (notice_id, alert_type, recipient_user_id, channel)
    triplet maps to at most one notice_alert_log row. Re-dispatch is a
    safe no-op (INSERT ... ON CONFLICT DO NOTHING).
    """
    from app.compliance.services.senders import (
        EmailSender,
        SmsSender,
        WebSocketSender,
    )

    counters = {"sent": 0, "queued": 0, "failed": 0, "skipped": 0}
    senders = {
        "email": EmailSender(),
        "sms": SmsSender(),
        "websocket": WebSocketSender(),
    }
    body = dict(payload or {})
    # CRITICAL hardening (#2) — override notice-derived fields with the
    # actual notice values. Never trust caller-supplied client_id (M2):
    # the notice is the source of truth for tenant boundary so
    # WebSocketSender's Redis channel never publishes to the wrong tenant.
    body["notice_id"] = notice.id
    body["client_id"] = notice.client_id
    body["notice_number"] = notice.notice_number
    body["authority"] = notice.authority
    body["status"] = notice.status
    body["response_deadline"] = (
        notice.response_deadline.isoformat() if notice.response_deadline else None
    )
    body["risk_tier"] = notice.risk_tier
    body["alert_type"] = alert_type

    for ch in channels:
        sender = senders.get(ch)
        if sender is None:
            logger.warning("dispatch_alert: unknown channel %r — skipping", ch)
            counters["skipped"] += len(recipients)
            continue

        for r in recipients:
            stmt = (
                pg_insert(NoticeAlertLog)
                .values(
                    notice_id=notice.id,
                    client_id=notice.client_id,
                    alert_type=alert_type,
                    recipient_user_id=r["user_id"],
                    recipient_email=r.get("email") if ch == "email" else None,
                    recipient_phone=r.get("phone") if ch == "sms" else None,
                    channel=ch,
                    delivery_status="queued",
                    payload=body,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        "notice_id",
                        "alert_type",
                        "recipient_user_id",
                        "channel",
                    ]
                )
                .returning(NoticeAlertLog.id)
            )
            row_id = db.execute(stmt).scalar_one_or_none()
            if row_id is None:
                # Already dispatched for this (notice, alert_type, user, channel)
                counters["skipped"] += 1
                continue

            try:
                result = sender.send(recipient=r, payload=body)
                row = db.get(NoticeAlertLog, row_id)
                row.delivery_status = result.delivery_status
                row.provider_message_id = result.provider_message_id
                row.error = result.error
                if result.delivery_status in ("sent", "delivered"):
                    row.delivered_at = datetime.now(timezone.utc)
                    counters["sent"] += 1
                elif result.delivery_status == "queued":
                    counters["queued"] += 1
                else:
                    counters["failed"] += 1
            except Exception as exc:
                logger.exception(
                    "dispatch_alert: %s sender raised for notice %d",
                    ch, notice.id,
                )
                row = db.get(NoticeAlertLog, row_id)
                row.delivery_status = "failed"
                row.error = str(exc)[:1000]
                counters["failed"] += 1

    db.commit()
    return counters


def dispatch_non_notice_alert(
    db: Session,
    *,
    client_id: int,
    alert_type: str,
    channels: list[str],
    recipients: list[dict],
    payload: dict[str, Any],
) -> dict[str, int]:
    """Fan-out for alerts that have no parent ComplianceNotice — bill reminders
    (BILL-04) and Gmail credential events (EMAIL-10).

    Skips NoticeAlertLog idempotency because the caller owns dedup:
      - bill_reminder_task enforces ``bill.reminder_count <= 3``
      - credential_vault enforces ``status=REVOKED`` once-only flip

    Returns the same {sent, queued, failed, skipped} counter shape as
    dispatch_alert so callers can branch uniformly.
    """
    from app.compliance.services.senders import (
        EmailSender,
        SmsSender,
        WebSocketSender,
    )

    counters = {"sent": 0, "queued": 0, "failed": 0, "skipped": 0}
    senders = {
        "email": EmailSender(),
        "sms": SmsSender(),
        "websocket": WebSocketSender(),
    }
    body = dict(payload or {})
    body["client_id"] = client_id
    body["alert_type"] = alert_type

    for ch in channels:
        sender = senders.get(ch)
        if sender is None:
            counters["skipped"] += len(recipients)
            continue
        for r in recipients:
            try:
                result = sender.send(recipient=r, payload=body)
                if result.delivery_status in ("sent", "delivered"):
                    counters["sent"] += 1
                elif result.delivery_status == "queued":
                    counters["queued"] += 1
                else:
                    counters["failed"] += 1
            except Exception:
                logger.exception(
                    "dispatch_non_notice_alert: %s sender raised for "
                    "client=%d alert_type=%s",
                    ch, client_id, alert_type,
                )
                counters["failed"] += 1
    return counters


def list_pending_alerts(
    db: Session, *, client_id: Optional[int], page: int = 1, page_size: int = 50
) -> tuple[list[NoticeAlertLog], int]:
    """List queued/failed alerts for retry surfaces. Auditor surface."""
    from sqlalchemy import func

    base = select(NoticeAlertLog).where(
        NoticeAlertLog.delivery_status.in_(("queued", "failed"))
    )
    count_q = select(func.count()).select_from(NoticeAlertLog).where(
        NoticeAlertLog.delivery_status.in_(("queued", "failed"))
    )
    if client_id is not None:
        base = base.where(NoticeAlertLog.client_id == client_id)
        count_q = count_q.where(NoticeAlertLog.client_id == client_id)

    base = (
        base.order_by(NoticeAlertLog.created_at.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    items = list(db.execute(base).scalars().all())
    total = int(db.execute(count_q).scalar_one())
    return items, total
