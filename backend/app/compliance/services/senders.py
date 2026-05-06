"""Phase 11 alert channel adapters — Email, SMS, WebSocket.

Each sender returns a SendResult with delivery_status + provider_message_id.
The dispatch_alert orchestrator persists this to notice_alert_log.

v2.0 implementation:
  - EmailSender    : reuses existing Resend SMTP via app/utils/email.send_email
                     User-controlled fields are HTML-escaped before
                     interpolation (hardening #7) — ``notice_number`` and
                     ``authority`` originate from user input and would otherwise
                     allow HTML/XSS into compliance_head's email client.
  - SmsSender      : Twilio adapter scaffolded but disabled by default.
                     v2.0 ships without `users.phone` column; live SMS lands
                     in v2.1 alongside DLT-registered template registration.
                     Every send returns 'failed' with a documented error code
                     until those gates are met.
  - WebSocketSender: publishes to Redis channel notifications:{client_id};
                     FastAPI websocket_manager subscribes and broadcasts to
                     connected clients

v2.1 path: drop-in SendGridSender swap; live SMS once DLT registered + phone
column added to User model.
"""
from __future__ import annotations

import html
import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class SendResult:
    delivery_status: str  # 'sent' | 'queued' | 'failed' | 'delivered'
    provider_message_id: Optional[str] = None
    error: Optional[str] = None


class EmailSender:
    """Reuses existing SMTP path. Phase 11 doesn't change deliverability;
    SendGrid swap is v2.1."""

    def send(self, *, recipient: dict, payload: dict) -> SendResult:
        email = recipient.get("email")
        if not email:
            return SendResult(delivery_status="failed", error="no_email_for_recipient")

        subject = self._subject_for(payload)
        body = self._body_for(payload)

        try:
            from app.utils.email import send_email as _send
            ok = _send(to_email=email, subject=subject, html_body=body)
            return SendResult(
                delivery_status="sent" if ok else "failed",
                error=None if ok else "smtp_returned_false",
            )
        except Exception as exc:
            return SendResult(delivery_status="failed", error=str(exc)[:1000])

    def _subject_for(self, payload: dict) -> str:
        # Subject is plain-text, no HTML rendering — but still strip line
        # breaks that could be used for header injection.
        alert_type = payload.get("alert_type", "alert")
        notice = (payload.get("notice_number") or "?").replace("\r", "").replace("\n", " ")
        authority = (payload.get("authority") or "").replace("\r", "").replace("\n", " ")
        labels = {
            "deadline_t7": f"[Compliance] {authority} {notice} due in 7 days",
            "deadline_t3": f"[Compliance] {authority} {notice} due in 3 days",
            "deadline_t1": f"[URGENT] {authority} {notice} due tomorrow",
            "overdue": f"[OVERDUE] {authority} {notice} past deadline",
            "status_change": f"[Compliance] {authority} {notice} status changed",
            "received": f"[Compliance] New {authority} notice received: {notice}",
            "escalation": f"[CRITICAL] {authority} {notice} escalated to you",
        }
        return labels.get(alert_type, f"[Compliance] Alert for notice {notice}")

    def _body_for(self, payload: dict) -> str:
        # Hardening (#7) — every user-controlled field passes through
        # html.escape() before interpolation. send_email attaches the body
        # as MIMEText(..., "html"); without escaping, a notice_number of
        # `"><script>...</script>` would execute in compliance_head's
        # email client.
        notice = html.escape(str(payload.get("notice_number") or "—"))
        authority = html.escape(str(payload.get("authority") or "—"))
        statuss = html.escape(str(payload.get("status") or "—"))
        risk = html.escape(str(payload.get("risk_tier") or "unscored"))
        deadline = html.escape(str(payload.get("response_deadline") or "not set"))
        return (
            "<p>A compliance notice requires your attention.</p>"
            "<ul>"
            f"<li><b>Notice:</b> {notice}</li>"
            f"<li><b>Authority:</b> {authority}</li>"
            f"<li><b>Status:</b> {statuss}</li>"
            f"<li><b>Risk:</b> {risk}</li>"
            f"<li><b>Deadline:</b> {deadline}</li>"
            "</ul>"
        )


class SmsSender:
    """Twilio adapter. v2.0 ships disabled-by-default; sends only when
    TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_FROM_NUMBER are set
    AND the per-client config_overrides.alert_channels includes 'sms'."""

    def send(self, *, recipient: dict, payload: dict) -> SendResult:
        phone = recipient.get("phone")
        if not phone:
            return SendResult(delivery_status="failed", error="no_phone_for_recipient")

        sid = os.environ.get("TWILIO_ACCOUNT_SID")
        tok = os.environ.get("TWILIO_AUTH_TOKEN")
        sender = os.environ.get("TWILIO_FROM_NUMBER")
        if not (sid and tok and sender):
            return SendResult(
                delivery_status="failed",
                error="twilio_credentials_missing — DLT registration + env vars required (v2.1)",
            )

        try:
            from twilio.rest import Client  # type: ignore[import-not-found]
            client = Client(sid, tok)
            msg = client.messages.create(
                body=self._body_for(payload),
                from_=sender,
                to=phone,
            )
            return SendResult(
                delivery_status="sent", provider_message_id=msg.sid
            )
        except ImportError:
            return SendResult(
                delivery_status="failed",
                error="twilio_sdk_not_installed",
            )
        except Exception as exc:
            return SendResult(
                delivery_status="failed", error=str(exc)[:1000]
            )

    def _body_for(self, payload: dict) -> str:
        # Indian DLT requires registered template — keep this short and
        # variable-substituted only.
        # H-H second hardening: strip CR/LF from interpolated user fields
        # to neutralize SMS message-splitting / spoofing. Same defensive
        # pattern as EmailSender._subject_for.
        def _clean(v) -> str:
            return str(v if v is not None else "").replace("\r", "").replace("\n", " ")

        notice = _clean(payload.get("notice_number", "?"))
        authority = _clean(payload.get("authority", ""))
        deadline = _clean(payload.get("response_deadline", ""))
        return f"Compliance: {authority} {notice} due {deadline}. Open dashboard."


class WebSocketSender:
    """Publish to Redis pub/sub channel notifications:{client_id}.

    The FastAPI WebSocket endpoint subscribes to this channel and forwards
    matching messages to authenticated client subscribers (RBAC parity).
    """

    def send(self, *, recipient: dict, payload: dict) -> SendResult:
        try:
            import redis  # type: ignore[import-untyped]
        except ImportError:
            return SendResult(
                delivery_status="failed",
                error="redis_sdk_not_installed",
            )

        url = os.environ.get("REDIS_URL")
        if not url:
            return SendResult(
                delivery_status="failed",
                error="REDIS_URL not configured",
            )

        client_id = payload.get("client_id")
        if client_id is None:
            # Defence in depth — dispatch_alert hardening (#2) ensures this
            # is always set; if a future caller bypasses the orchestrator
            # we'd rather fail loudly than publish to notifications:default.
            return SendResult(
                delivery_status="failed",
                error="missing_client_id_in_payload",
            )

        try:
            r = redis.from_url(url)
            channel = f"notifications:{client_id}"
            envelope = {
                "type": "notice_alert",
                "recipient_user_id": recipient.get("user_id"),
                "payload": payload,
            }
            subs = r.publish(channel, json.dumps(envelope))
            # subs is the number of subscribers that received the message.
            # 0 means no live WebSocket connection exists for this client —
            # the alert wasn't truly "delivered" but it was correctly routed.
            # Mark queued so an operator can see the delivery gap in
            # /api/compliance/alerts/pending.
            return SendResult(
                delivery_status="sent" if subs > 0 else "queued",
                provider_message_id=f"redis_subs={subs}",
            )
        except Exception as exc:
            return SendResult(
                delivery_status="failed", error=str(exc)[:1000]
            )
