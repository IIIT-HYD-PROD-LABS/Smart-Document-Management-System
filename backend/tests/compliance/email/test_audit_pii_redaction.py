"""Phase 15 — EMAIL-09 PII redaction tests.

RED-state stub. Plan 04 lands the gmail_search_impl tool; D-36 mandates
that audit args contain only IDs + SHA-256 — body, subject, sender are all
PII-redacted via the existing INFRA-06 helper.
"""
from __future__ import annotations

import pytest


def test_audit_args_omit_body_subject_sender():
    """audit_log row args dict has no 'body', 'subject', or 'sender' keys (D-36)."""
    try:
        from app.email.mcp.tools import gmail_search_impl  # noqa: F401
    except ImportError:
        pytest.skip("Plan 04 — gmail_search_impl not yet implemented")
    pytest.skip("Plan 04 — PII redaction assertion lands then")


def test_audit_args_include_body_sha256_and_message_id():
    """audit_log args contain message_id + body_sha256 + attachment_sha256s for tamper detection (D-35)."""
    try:
        from app.email.mcp.tools import gmail_search_impl  # noqa: F401
    except ImportError:
        pytest.skip("Plan 04 — gmail_search_impl not yet implemented")
    pytest.skip("Plan 04 — body_sha256 audit row lands then")
