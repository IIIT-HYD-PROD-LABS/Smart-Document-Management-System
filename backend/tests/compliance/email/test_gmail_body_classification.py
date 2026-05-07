"""Phase 15 D-39 smoke test: Gmail body docs run through v1.0 ML.

Builds a Document with source='gmail_body' and a synthetic .txt
file_path, drives process_document_task synchronously with mocked
SessionLocal + filesystem, and asserts Phase 3 ML classification
populates Document.category.
"""
from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

from celery.app.task import Task as _CeleryBaseTask

from app.models.document import DocumentCategory, DocumentStatus
from app.tasks.document_tasks import process_document_task


_TASK = "app.tasks.document_tasks"
_STORAGE = "app.services.storage_service"
_LLM = "app.services.llm_service"


class _TaskSelfContext:
    """Patch bound Celery task internals — mirrors test_document_tasks helper."""

    def __init__(self, retries: int = 0, max_retries: int = 3):
        self.retries = retries
        self.max_retries = max_retries
        self._patches = []

    def __enter__(self):
        mock_request = MagicMock()
        mock_request.retries = self.retries
        self._patches = [
            patch.object(_CeleryBaseTask, "request", new_callable=PropertyMock, return_value=mock_request),
            patch.object(process_document_task, "update_state", MagicMock()),
            patch.object(process_document_task, "max_retries", self.max_retries),
            patch.object(process_document_task, "retry", MagicMock(side_effect=Exception("retry called"))),
            patch.object(process_document_task, "MaxRetriesExceededError", Exception),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *_):
        for p in reversed(self._patches):
            p.stop()


def _make_gmail_body_doc():
    doc = MagicMock()
    doc.id = 42
    doc.file_path = "/uploads/email_body_42.txt"
    doc.file_type = "txt"
    doc.source = "gmail_body"
    doc.status = DocumentStatus.PENDING
    doc.extracted_text = None
    doc.category = DocumentCategory.UNKNOWN
    doc.confidence_score = 0.0
    doc.extracted_metadata = None
    doc.ai_summary = None
    doc.ai_extracted_fields = None
    doc.ai_provider = None
    doc.ai_extraction_status = None
    return doc


@patch(f"{_TASK}.SessionLocal")
@patch(f"{_STORAGE}._validate_path_inside_upload_dir", return_value="/uploads/email_body_42.txt")
@patch(f"{_TASK}.os.path.exists", return_value=True)
@patch(f"{_TASK}.os.path.getsize", return_value=512)
@patch(f"{_TASK}.settings")
@patch(
    f"{_TASK}.extract_and_classify",
    return_value=(
        "Invoice for services rendered. Amount due 5000. Due 2026-06-01.",
        "invoices",
        0.91,
    ),
)
@patch(
    f"{_TASK}.extract_metadata",
    return_value={"dates": ["2026-06-01"], "amounts": ["5000"], "vendor": None},
)
@patch(f"{_LLM}.extract_with_llm", side_effect=ImportError("no llm"))
def test_gmail_body_doc_gets_classified(
    _mock_llm,
    _mock_metadata,
    _mock_classify,
    mock_settings,
    _mock_getsize,
    _mock_exists,
    _mock_validate,
    mock_session_cls,
):
    """source='gmail_body' Document runs through v1.0 ML and ends COMPLETED."""
    mock_settings.MAX_FILE_SIZE_MB = 50

    doc = _make_gmail_body_doc()
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = doc
    mock_session_cls.return_value = mock_db

    with patch("builtins.open", MagicMock()):
        with _TaskSelfContext():
            result = process_document_task.run(42)

    assert result["status"] == "completed"
    assert result["document_id"] == 42
    assert result["category"] == "invoices"
    # Phase 3 ML populated the category enum (D-39 acceptance criterion).
    assert doc.category == DocumentCategory.INVOICES
    assert doc.confidence_score == 0.91
    assert doc.status == DocumentStatus.COMPLETED


def test_extract_and_classify_handles_txt_input():
    """extract_and_classify decodes raw .txt bytes (D-39 plumbing)."""
    from app.ml.classifier import extract_and_classify

    body = (
        "Invoice number 12345. Total amount 7500 INR. Due date 2026-07-15. "
        "Please remit payment to the account on file. "
    ) * 5
    text, category, confidence = extract_and_classify(body.encode("utf-8"), "txt")

    assert "Invoice number" in text
    # Even if the trained model isn't loaded in CI, txt decode must succeed
    # and the category must be a string from the enum vocabulary.
    assert isinstance(category, str)
    assert isinstance(confidence, float)
