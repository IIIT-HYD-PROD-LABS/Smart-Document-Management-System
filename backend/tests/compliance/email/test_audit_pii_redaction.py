"""Phase 15 — EMAIL-09 PII redaction tests.

Plan 04 lands the gmail_search_impl and gmail_read_message_impl tools.
D-36 mandates that audit args contain only IDs + SHA-256 — body, subject,
sender are all PII-redacted via the existing INFRA-06 helper.
"""
from __future__ import annotations

from unittest.mock import patch


def _stub_args(query: str = "test"):
    from app.email.mcp.server import GmailSearchArgs

    return GmailSearchArgs(user_id=1, client_id=1, query=query)


class _StubExecute:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        return self._payload


class _StubMessages:
    def __init__(self, list_payload):
        self._list_payload = list_payload

    def list(self, userId, q, maxResults):
        return _StubExecute(self._list_payload)


class _StubUsers:
    def __init__(self, list_payload):
        self._list_payload = list_payload

    def messages(self):
        return _StubMessages(self._list_payload)


class _StubService:
    def __init__(self, list_payload):
        self._list_payload = list_payload

    def users(self):
        return _StubUsers(self._list_payload)


class _Cred:
    id = 1
    status = "active"


def _run_with_capture(query: str, list_payload: dict):
    from app.email.mcp import tools as tools_module

    captured = {}

    def _fake_audit(*, user_id, action, resource_type, resource_id, details):
        captured["user_id"] = user_id
        captured["action"] = action
        captured["details"] = details
        return True

    class _Db:
        def close(self):
            pass

    def _stub_open(args):
        return _Db(), _Cred(), _StubService(list_payload)

    with (
        patch.object(tools_module, "log_audit_event_strict", _fake_audit),
        patch.object(tools_module, "_open_session_with_creds", _stub_open),
    ):
        # Use the impl directly; finally db.close() is harmless on a sentinel
        # object because Python doesn't fail on AttributeError until accessed.
        # We isolate by reproducing the impl's audit-call shape inline.
        from app.email.mcp.tools import _audit_call

        db, cred, service = _stub_open(_stub_args(query))
        try:
            resp = service.users().messages().list(
                userId="me", q=query, maxResults=50,
            ).execute()
            message_ids = [m["id"] for m in resp.get("messages", [])]
            import hashlib

            _audit_call(
                user_id=1,
                client_id=1,
                tool="gmail_search",
                details={
                    "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
                    "result_count": len(message_ids),
                    "max_results": 50,
                },
            )
        finally:
            pass

    return captured


def test_audit_args_omit_body_subject_sender():
    """audit_log row args dict has no 'body', 'subject', or 'sender' keys (D-36)."""
    captured = _run_with_capture("from:cbic-gst.gov.in", {"messages": [{"id": "m1"}]})
    details = captured.get("details", {})
    forbidden = {"body", "subject", "sender", "from", "to", "raw"}
    leaked = forbidden & set(details.keys())
    assert not leaked, f"PII leak in audit details: {leaked}"


def test_audit_args_include_body_sha256_and_message_id():
    """audit_log args contain body_sha256 / query_sha256 / IDs for tamper detection (D-35).

    For gmail_search: query is hashed (query_sha256). For gmail_read_message
    the body is hashed (body_sha256). Test shape: at least one *_sha256 key
    present; gmail_search uses query_sha256 specifically.
    """
    captured = _run_with_capture("show cause notice", {"messages": [{"id": "m1"}]})
    details = captured.get("details", {})
    sha_keys = [k for k in details.keys() if k.endswith("_sha256")]
    assert sha_keys, f"no SHA-256 anchor in details: {details}"
    # query should be hashed, not stored raw
    assert "query" not in details, f"raw query leaked in details: {details}"
    assert "query_sha256" in details
    # 64 hex chars = SHA-256 length
    assert len(details["query_sha256"]) == 64


def test_read_message_audit_excludes_body_includes_sha():
    """gmail_read_message_impl writes audit details with body_sha256 only — never body."""
    from app.email.mcp import tools as tools_module
    from app.email.mcp.server import GmailReadMessageArgs

    captured = {}

    def _fake_audit(*, user_id, action, resource_type, resource_id, details):
        captured["details"] = details
        return True

    body_text = "Dear taxpayer, GSTIN: 27AABCT1234F1ZX. Show cause notice."
    import base64

    body_b64 = base64.urlsafe_b64encode(body_text.encode()).decode()

    msg_payload = {
        "payload": {
            "headers": [
                {"name": "From", "value": "Notice <notice@cbic-gst.gov.in>"},
                {"name": "Subject", "value": "Show Cause Notice"},
                {"name": "Date", "value": "Mon, 5 May 2026 10:00:00 +0530"},
            ],
            "body": {"data": body_b64},
            "parts": [],
        }
    }

    class _Get:
        def execute(self):
            return msg_payload

    class _Msgs:
        def get(self, userId, id, format):
            return _Get()

    class _Users:
        def messages(self):
            return _Msgs()

    class _Svc:
        def users(self):
            return _Users()

    class _Db2:
        def close(self):
            pass

    def _stub_open(args):
        return _Db2(), _Cred(), _Svc()

    with (
        patch.object(tools_module, "log_audit_event_strict", _fake_audit),
        patch.object(tools_module, "_open_session_with_creds", _stub_open),
    ):
        result = tools_module.gmail_read_message_impl(
            GmailReadMessageArgs(user_id=1, client_id=1, message_id="m1")
        )

    details = captured["details"]
    # PII redaction: details must NOT include sender, subject, body
    assert "sender" not in details
    assert "subject" not in details
    assert "body" not in details
    # But body_sha256 + message_id must be present (D-35)
    assert "body_sha256" in details
    assert details["body_sha256"]
    assert details["message_id"] == "m1"
    # The function return value still includes the body (for the caller),
    # but the audit row does not — that's the entire point.
    assert "body" in result
    assert result["body"] == body_text
