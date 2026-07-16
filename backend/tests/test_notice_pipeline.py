"""Unit tests for the unified notice pipeline helper."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.compliance.services.notice_pipeline import after_document_intelligence


def test_pipeline_skips_when_no_notice():
    db = MagicMock()
    out = after_document_intelligence(
        db,
        document_id=9,
        notice_id=None,
        user_id=1,
        extracted_text="DRC-01 notice body",
    )
    assert out["extraction"] == "skipped"
    assert out["intake"] == "skipped"


def test_pipeline_skips_extraction_when_no_text():
    db = MagicMock()
    out = after_document_intelligence(
        db,
        document_id=9,
        notice_id=3,
        user_id=1,
        extracted_text="   ",
    )
    assert out["extraction"] == "no_text"
    assert out["intake"] == "skipped"


def test_pipeline_runs_extraction_then_intake():
    db = MagicMock()
    notice = SimpleNamespace(id=3, response_deadline="2026-08-01")
    db.get.return_value = notice

    with patch(
        "app.tasks.document_tasks._run_phase17_extraction"
    ) as extract, patch(
        "app.compliance.services.notice_service.process_notice_intake"
    ) as intake:
        out = after_document_intelligence(
            db,
            document_id=9,
            notice_id=3,
            user_id=1,
            extracted_text="Show cause DRC-01 tax demand Rs. 1000",
        )

    extract.assert_called_once()
    intake.assert_called_once_with(3, "2026-08-01")
    assert out["extraction"] == "ran"
    assert out["intake"] == "dispatched"
    assert out["response_deadline"] == "2026-08-01"
