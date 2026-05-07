"""Phase 15 — EMAIL-05 attachment ingestion tests.

RED-state stub. Plan 04 lands `ingestion_service.ingest_attachment`,
which reuses the v1.0 storage_service + document_tasks pipeline (D-14).
Document.source_email_id (Plan 02 migration) records provenance.
"""
from __future__ import annotations

import pytest


def test_attachment_creates_document_with_source_email_id():
    """Ingesting a Gmail PDF attachment creates Document with source_email_id FK set (EMAIL-05)."""
    try:
        from app.email.services.ingestion_service import ingest_attachment  # noqa: F401
    except ImportError:
        pytest.skip("Plan 04 — ingestion_service not yet implemented")
    pytest.skip("Plan 04 — Document.source_email_id assertion lands then")


def test_attachment_invokes_process_document_task():
    """ingest_attachment calls process_document_task.delay(document_id) (D-14)."""
    try:
        from app.email.services.ingestion_service import ingest_attachment  # noqa: F401
    except ImportError:
        pytest.skip("Plan 04 — ingestion_service not yet implemented")
    pytest.skip("Plan 04 — Celery task invocation assertion lands then")
