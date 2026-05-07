"""Phase 15 — D-34 PII lifecycle tests.

RED-state stub. D-34 mandates fetch-once / classify+extract / discard:
the email body never lands on disk or in any persistent store. Body
lives in Python locals for ~seconds and is then GC'd.

Asserts:
  - GmailMessageLog has NO `body` column (only message_id, sender_domain,
    body_sha256, has_attachments, etc.)
  - The scanner task code path never calls redis.set / redis.setex with
    body content as the value (only IDs + hashes)
"""
from __future__ import annotations

import pytest


def test_body_never_written_to_database():
    """GmailMessageLog table has no `body` column (D-34: body never persisted)."""
    try:
        from app.email.models.message_log import GmailMessageLog  # noqa: F401
    except ImportError:
        pytest.skip("Plan 02 — GmailMessageLog ORM not yet implemented")
    pytest.skip("Plan 02 — schema column assertion (body never persisted) lands then")


def test_body_never_written_to_redis():
    """scanner_service.scan_credential never calls redis.set/setex with body content (D-34)."""
    try:
        from app.email.services.scanner_service import scan_credential  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — scanner_service not yet implemented")
    pytest.skip("Plan 03 — Redis call inspection assertion lands then")
