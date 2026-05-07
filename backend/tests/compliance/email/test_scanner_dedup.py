"""Phase 15 — EMAIL-08 dedup tests.

RED-state stub. Plan 02 lands GmailMessageLog with composite UNIQUE on
(credential_id, gmail_message_id); Plan 04 lands per-attachment SHA-256
dedup in the ingestion service.
"""
from __future__ import annotations

import pytest


def test_composite_unique_credential_id_message_id():
    """INSERT duplicate (credential_id, gmail_message_id) raises IntegrityError (EMAIL-08)."""
    from app.email.models.message_log import GmailMessageLog

    # Schema-level assertion: the composite UNIQUE constraint exists on the table.
    constraint_names = {c.name for c in GmailMessageLog.__table__.constraints}
    assert "uq_gmail_message_log_dedup" in constraint_names, (
        "GmailMessageLog must declare composite UNIQUE on (credential_id, gmail_message_id)"
    )


def test_attachment_sha256_unique_within_credential():
    """Same SHA-256 attachment in two messages of one credential ingested only once (EMAIL-08)."""
    try:
        from app.email.services.ingestion_service import ingest_attachment  # noqa: F401
    except ImportError:
        pytest.skip("Plan 04 — ingestion_service not yet implemented")
    pytest.skip("Plan 04 — per-credential attachment dedup lands then")
