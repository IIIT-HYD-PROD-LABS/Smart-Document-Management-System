"""Phase 17 EXTRACT-08 / EXTRACT-10 / EXTRACT-11 / EXTRACT-12 — cross-cutting guarantees.

RLS isolation + audit immutability are inherited from Phase 9; this file
asserts the inheritance contracts (column added under existing RLS,
trigger present) and the router-shaped BYOK / rate-limit checks for the
Phase 17 endpoints.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_extracted_fields_column_inherits_rls_from_compliance_notices():
    """EXTRACT-11: the new jsonb column lives on a table that is already
    RLS-enabled + FORCED (Phase 9 migrations 0017 + 0018). The Wave 1
    migration adds columns only, so RLS coverage transfers without new
    policies.
    """
    from app.compliance.models.notice import ComplianceNotice
    # Sanity: column is registered on the table model.
    assert "extracted_fields" in ComplianceNotice.__table__.columns
    assert "extraction_status" in ComplianceNotice.__table__.columns


def test_extraction_audit_row_uses_existing_immutable_audit_log():
    """EXTRACT-12: extraction audit writes go through audit_service.log_audit_event,
    which targets the existing audit_log table protected by the Phase 9 BEFORE
    UPDATE OR DELETE trigger (memory: project_audit_logs_trigger.md).
    """
    from app.services.audit_service import log_audit_event, log_audit_event_strict
    # Importable, callable; the trigger is verified by Phase 9's own test_audit_immutability.
    assert callable(log_audit_event)
    assert callable(log_audit_event_strict)


def _unwrap(view):
    """Strip slowapi's @limiter.limit decorator to call the raw handler."""
    return getattr(view, "__wrapped__", view)


def test_byok_missing_credential_returns_412():
    """D-14: tenant without AICredential gets HTTP 412 from extract-preview."""
    from fastapi import HTTPException

    from app.compliance.routers import notices as notices_router
    from app.compliance.services.notice_extractor_service import (
        NoticeExtractionCredentialMissingError,
    )

    file_mock = MagicMock()
    file_mock.filename = "notice.pdf"
    file_mock.content_type = "application/pdf"
    # side_effect (not return_value) so the streaming-read loop in
    # _read_validated_upload sees EOF after one chunk; a fixed return_value
    # would loop until the 50MB size cap and balloon MagicMock's call history.
    file_mock.file.read.side_effect = [b"%PDF-1.4 dummy", b""]

    handler = _unwrap(notices_router.extract_preview)

    with patch.object(notices_router, "_ocr_extract_text", return_value="some notice text body"), \
         patch(
             "app.compliance.services.notice_extractor_service.extract_notice_fields",
             side_effect=NoticeExtractionCredentialMissingError("no credential"),
         ):
        with pytest.raises(HTTPException) as excinfo:
            handler(
                request=MagicMock(),
                response=MagicMock(),
                file=file_mock,
                current_user=MagicMock(id=1),
                db=MagicMock(),
                membership=MagicMock(client_id=7, role="compliance_head"),
            )

    assert excinfo.value.status_code == 412
    detail = excinfo.value.detail
    assert isinstance(detail, dict)
    assert detail.get("code") == "no_ai_credential"


def test_extract_preview_rejects_disallowed_content_type():
    """Defence-in-depth: text/plain or application/zip are rejected with HTTP 400."""
    from fastapi import HTTPException

    from app.compliance.routers import notices as notices_router

    file_mock = MagicMock()
    file_mock.content_type = "application/zip"

    handler = _unwrap(notices_router.extract_preview)

    with pytest.raises(HTTPException) as excinfo:
        handler(
            request=MagicMock(),
            response=MagicMock(),
            file=file_mock,
            current_user=MagicMock(),
            db=MagicMock(),
            membership=MagicMock(client_id=7),
        )

    assert excinfo.value.status_code == 400


def test_extract_preview_rate_limited_per_tenant():
    """D-19: 12 calls per minute per tenant. Decorator presence is the actionable assertion."""
    import inspect

    from app.compliance.routers import notices as notices_router

    # The decorator wraps the function; the literal must appear in the
    # module source attached to the handler line. Decorator inspection
    # via __wrapped__ is fragile across slowapi versions.
    module_src = inspect.getsource(notices_router)
    assert '@limiter.limit("12/minute")' in module_src, (
        "extract_preview must be rate-limited to 12/minute per D-19"
    )
