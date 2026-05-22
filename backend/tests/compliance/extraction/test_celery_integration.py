"""Phase 17 EXTRACT-06 — Celery + first-upload-wins integration (D-23, D-12, D-09).

Plan 17-04 GREEN. `_run_phase17_extraction` helper inside
`app/tasks/document_tasks.py` is the integration surface; the Celery
task body just calls it when `document.notice_id` is set.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _make_notice(extraction_status: str | None = None) -> MagicMock:
    notice = MagicMock()
    notice.id = 42
    notice.client_id = 7
    notice.extraction_status = extraction_status
    return notice


def test_run_phase17_extraction_persists_envelope_when_decision_apply(
    extraction_envelope_fixture,
):
    """D-23: high-confidence extraction lands on the notice via apply_extraction_to_notice."""
    from app.tasks import document_tasks

    notice = _make_notice()
    db = MagicMock()
    db.get.return_value = notice

    with patch.object(
        document_tasks,
        "_run_phase17_extraction",
        wraps=document_tasks._run_phase17_extraction,
    ), \
        patch(
            "app.compliance.services.notice_extractor_service.extract_notice_fields",
            return_value=extraction_envelope_fixture,
        ) as ext_mock, \
        patch(
            "app.compliance.services.extraction_routing_service.apply_extraction_to_notice"
        ) as apply_mock:

        document_tasks._run_phase17_extraction(
            db,
            document_id=99,
            notice_id=42,
            user_id=1,
            extracted_text="sample notice text",
        )

    ext_mock.assert_called_once()
    apply_mock.assert_called_once()
    # decision passed to apply must have action='apply' for this envelope
    decision_kwarg = apply_mock.call_args[0][3]
    assert decision_kwarg["action"] == "apply"


def test_run_phase17_extraction_routes_low_confidence_to_review(
    low_confidence_envelope_fixture,
):
    """D-06 + D-23: low average confidence routes to review_queue when applied."""
    from app.tasks import document_tasks

    notice = _make_notice()
    db = MagicMock()
    db.get.return_value = notice

    with patch(
        "app.compliance.services.notice_extractor_service.extract_notice_fields",
        return_value=low_confidence_envelope_fixture,
    ), \
        patch(
            "app.compliance.services.extraction_routing_service.apply_extraction_to_notice"
        ) as apply_mock:

        document_tasks._run_phase17_extraction(
            db,
            document_id=99,
            notice_id=42,
            user_id=1,
            extracted_text="sample notice text",
        )

    decision_kwarg = apply_mock.call_args[0][3]
    assert decision_kwarg["action"] == "review_queue"


def test_first_upload_wins_skips_when_already_accepted(extraction_envelope_fixture):
    """D-12: notice with extraction_status='accepted' must not be re-extracted."""
    from app.tasks import document_tasks

    notice = _make_notice(extraction_status="accepted")
    db = MagicMock()
    db.get.return_value = notice

    with patch(
        "app.compliance.services.notice_extractor_service.extract_notice_fields"
    ) as ext_mock:
        document_tasks._run_phase17_extraction(
            db,
            document_id=99,
            notice_id=42,
            user_id=1,
            extracted_text="sample notice text",
        )

    ext_mock.assert_not_called()


def test_extraction_failure_marks_status_failed_and_does_not_raise():
    """D-09: extractor exception leaves the notice at extraction_status='failed' and returns cleanly."""
    from app.tasks import document_tasks

    notice = _make_notice()
    db = MagicMock()
    db.get.return_value = notice

    with patch(
        "app.compliance.services.notice_extractor_service.extract_notice_fields",
        side_effect=RuntimeError("provider timeout"),
    ):
        document_tasks._run_phase17_extraction(
            db,
            document_id=99,
            notice_id=42,
            user_id=1,
            extracted_text="sample notice text",
        )

    assert notice.extraction_status == "failed"


def test_missing_credential_marks_status_failed_silently():
    """D-14 in the Celery path: NoticeExtractionCredentialMissingError → status='failed', no raise."""
    from app.compliance.services.notice_extractor_service import (
        NoticeExtractionCredentialMissingError,
    )
    from app.tasks import document_tasks

    notice = _make_notice()
    db = MagicMock()
    db.get.return_value = notice

    with patch(
        "app.compliance.services.notice_extractor_service.extract_notice_fields",
        side_effect=NoticeExtractionCredentialMissingError("no credential"),
    ):
        document_tasks._run_phase17_extraction(
            db,
            document_id=99,
            notice_id=42,
            user_id=1,
            extracted_text="sample notice text",
        )

    assert notice.extraction_status == "failed"


def test_process_document_task_skips_extraction_when_notice_id_none():
    """When document.notice_id is None, _run_phase17_extraction is NOT called from the task body."""
    # This assertion is structural: a grep on the task body shows the
    # `if getattr(doc, "notice_id", None):` guard wrapping the helper
    # call. We assert the guard literal exists so a future refactor
    # cannot silently remove it.
    import inspect
    from app.tasks import document_tasks

    src = inspect.getsource(document_tasks)
    assert 'if getattr(doc, "notice_id", None):' in src or \
        "if getattr(doc, 'notice_id', None):" in src, (
            "process_document_task must gate Phase 17 extraction on doc.notice_id"
        )
