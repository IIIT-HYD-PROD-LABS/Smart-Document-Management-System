"""Phase 11 — alert dispatch + senders unit tests.

MagicMock-based; no DB access. Integration paths exercised by the smoke
test that triggers a Critical-tier escalation end-to-end.
"""
from unittest.mock import MagicMock, patch

import pytest

from app.compliance.services.senders import (
    EmailSender,
    SendResult,
    SmsSender,
    WebSocketSender,
)


# ────────────────────────────────────────────────────────────────────
# EmailSender
# ────────────────────────────────────────────────────────────────────

def test_email_sender_returns_failed_when_no_email():
    sender = EmailSender()
    result = sender.send(recipient={"email": None}, payload={})
    assert result.delivery_status == "failed"
    assert "no_email" in result.error


def test_email_sender_calls_send_email_with_subject_and_body():
    sender = EmailSender()
    with patch("app.utils.email.send_email", return_value=True) as mock_send:
        result = sender.send(
            recipient={"email": "u@example.com"},
            payload={
                "alert_type": "deadline_t1",
                "notice_number": "DRC-01/2026/A1",
                "authority": "GST",
                "status": "under_review",
                "response_deadline": "2026-05-10",
                "risk_tier": "high",
            },
        )
    assert result.delivery_status == "sent"
    args, kwargs = mock_send.call_args
    assert kwargs["to_email"] == "u@example.com"
    assert "URGENT" in kwargs["subject"]
    assert "DRC-01/2026/A1" in kwargs["html_body"]


def test_email_sender_propagates_provider_error_as_failed():
    sender = EmailSender()
    with patch("app.utils.email.send_email", side_effect=RuntimeError("smtp_down")):
        result = sender.send(recipient={"email": "u@example.com"}, payload={})
    assert result.delivery_status == "failed"
    assert "smtp_down" in result.error


# ────────────────────────────────────────────────────────────────────
# SmsSender (DLT-disabled by default in v2.0)
# ────────────────────────────────────────────────────────────────────

def test_sms_sender_returns_failed_when_no_phone():
    sender = SmsSender()
    result = sender.send(recipient={"phone": None}, payload={})
    assert result.delivery_status == "failed"
    assert "no_phone" in result.error


def test_sms_sender_returns_failed_when_credentials_missing(monkeypatch):
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_FROM_NUMBER", raising=False)
    sender = SmsSender()
    result = sender.send(recipient={"phone": "+919999999999"}, payload={})
    assert result.delivery_status == "failed"
    assert "twilio_credentials_missing" in result.error
    assert "DLT" in result.error  # documents the v2.1 prerequisite


# ────────────────────────────────────────────────────────────────────
# WebSocketSender
# ────────────────────────────────────────────────────────────────────

def test_websocket_sender_publishes_envelope_to_redis(monkeypatch):
    """Verify the (type='notice_alert', payload) envelope contract.

    Hardening (#11) — `subs` from r.publish() drives delivery_status; with a
    mock the default Magic value is non-zero so we expect 'sent'."""
    monkeypatch.setenv("REDIS_URL", "redis://test:6379/0")
    sender = WebSocketSender()

    fake_redis = MagicMock()
    fake_redis.publish.return_value = 1  # 1 subscriber received
    with patch("redis.from_url", return_value=fake_redis):
        result = sender.send(
            recipient={"user_id": 7},
            payload={"client_id": 42, "notice_id": 99},
        )
    assert result.delivery_status == "sent"
    assert result.provider_message_id == "redis_subs=1"
    args, _ = fake_redis.publish.call_args
    channel, message = args
    assert channel == "notifications:42"
    import json
    envelope = json.loads(message)
    assert envelope["type"] == "notice_alert"
    assert envelope["recipient_user_id"] == 7
    assert envelope["payload"]["notice_id"] == 99


def test_websocket_sender_marks_queued_when_no_subscribers(monkeypatch):
    """Hardening (#11) — Redis publish returning 0 subs means the message
    was correctly routed but no live WebSocket received it. delivery_status
    must reflect 'queued', not 'sent'."""
    monkeypatch.setenv("REDIS_URL", "redis://test:6379/0")
    sender = WebSocketSender()
    fake_redis = MagicMock()
    fake_redis.publish.return_value = 0
    with patch("redis.from_url", return_value=fake_redis):
        result = sender.send(
            recipient={"user_id": 7},
            payload={"client_id": 1, "notice_id": 2},
        )
    assert result.delivery_status == "queued"
    assert result.provider_message_id == "redis_subs=0"


def test_websocket_sender_returns_failed_when_client_id_missing(monkeypatch):
    """Hardening (#2) — payload without client_id must fail loudly rather
    than fall back to a 'default' channel."""
    monkeypatch.setenv("REDIS_URL", "redis://test:6379/0")
    sender = WebSocketSender()
    result = sender.send(recipient={"user_id": 7}, payload={})
    assert result.delivery_status == "failed"
    assert "missing_client_id" in result.error


def test_websocket_sender_returns_failed_when_redis_url_missing(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    sender = WebSocketSender()
    result = sender.send(recipient={"user_id": 7}, payload={"client_id": 1})
    assert result.delivery_status == "failed"


# ────────────────────────────────────────────────────────────────────
# resolve_recipients
# ────────────────────────────────────────────────────────────────────

def test_resolve_recipients_returns_empty_for_no_roles():
    from app.compliance.services.alert_service import resolve_recipients
    db = MagicMock()
    out = resolve_recipients(db, client_id=1, recipient_roles=[])
    assert out == []
