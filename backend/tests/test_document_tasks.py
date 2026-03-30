"""Unit tests for Celery document processing task.

All tests call the task function directly with mocked dependencies --
no Celery broker, database, or filesystem required.

For bound Celery tasks (bind=True), `task.run(document_id)` calls the
original function with `self=task_instance`. We patch the task object's
attributes (update_state, request, max_retries) directly.
"""

from unittest.mock import MagicMock, patch

import pytest

from app.models.document import DocumentStatus, DocumentCategory
from app.tasks.document_tasks import process_document_task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch_task_self(retries: int = 0, max_retries: int = 3):
    """Patch the task object's attributes to mimic bound-task `self`.

    For bound Celery tasks, `.run(arg)` passes the task instance as self.
    We mock properties on the actual task object rather than passing a
    separate mock_self.
    """
    process_document_task.update_state = MagicMock()
    process_document_task.request = MagicMock()
    process_document_task.request.retries = retries
    process_document_task.max_retries = max_retries
    process_document_task.retry = MagicMock(side_effect=Exception("retry called"))
    process_document_task.MaxRetriesExceededError = Exception


def _make_mock_document(**overrides):
    """Return a lightweight mock ``Document`` row."""
    doc = MagicMock()
    doc.id = overrides.get("id", 1)
    doc.file_path = overrides.get("file_path", "/uploads/test.pdf")
    doc.file_type = overrides.get("file_type", "pdf")
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


def _make_mock_db(doc):
    """Return a mock DB session wired to return *doc* from a query."""
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = doc
    return mock_db


# Module path constants for @patch targets.
_TASK = "app.tasks.document_tasks"
_STORAGE = "app.services.storage_service"
_LLM = "app.services.llm_service"


# ---------------------------------------------------------------------------
# 1. Invalid document_id
# ---------------------------------------------------------------------------

class TestInvalidDocumentId:
    """process_document_task should reject non-positive / non-integer IDs."""

    @pytest.mark.parametrize("bad_id", [0, -1, -999])
    def test_non_positive_integer(self, bad_id):
        _patch_task_self()
        result = process_document_task.run(bad_id)
        assert result == {"error": "Invalid document_id"}

    @pytest.mark.parametrize("bad_id", ["abc", None, 3.14, []])
    def test_non_integer_type(self, bad_id):
        _patch_task_self()
        result = process_document_task.run(bad_id)
        assert result == {"error": "Invalid document_id"}


# ---------------------------------------------------------------------------
# 2. Document not found in DB
# ---------------------------------------------------------------------------

class TestDocumentNotFound:

    @patch(f"{_TASK}.SessionLocal")
    def test_returns_error_when_missing(self, mock_session_cls):

        mock_db = _make_mock_db(doc=None)
        mock_session_cls.return_value = mock_db

        _patch_task_self()
        result = process_document_task.run(999)

        assert result == {"error": "Document not found"}
        mock_db.close.assert_called_once()


# ---------------------------------------------------------------------------
# 3. File not found on disk
# ---------------------------------------------------------------------------

class TestFileNotFound:

    @patch(f"{_TASK}.SessionLocal")
    @patch(f"{_STORAGE}._validate_path_inside_upload_dir", return_value="/uploads/test.pdf")
    @patch(f"{_TASK}.os.path.exists", return_value=False)
    def test_marks_document_failed(self, _mock_exists, _mock_validate, mock_session_cls):

        doc = _make_mock_document()
        mock_db = _make_mock_db(doc)
        mock_session_cls.return_value = mock_db

        _patch_task_self()
        result = process_document_task.run(1)

        assert result == {"error": "File not found"}
        assert doc.status == DocumentStatus.FAILED
        assert doc.extracted_text == "File not found in storage."
        mock_db.commit.assert_called()

    @patch(f"{_TASK}.SessionLocal")
    def test_no_file_path_marks_failed(self, mock_session_cls):

        doc = _make_mock_document(file_path=None)
        mock_db = _make_mock_db(doc)
        mock_session_cls.return_value = mock_db

        _patch_task_self()
        result = process_document_task.run(1)

        assert result == {"error": "File not found"}
        assert doc.status == DocumentStatus.FAILED


# ---------------------------------------------------------------------------
# 4. Successful processing (extract_and_classify)
# ---------------------------------------------------------------------------

class TestSuccessfulProcessing:

    @patch(f"{_TASK}.SessionLocal")
    @patch(f"{_STORAGE}._validate_path_inside_upload_dir", return_value="/uploads/test.pdf")
    @patch(f"{_TASK}.os.path.exists", return_value=True)
    @patch(f"{_TASK}.os.path.getsize", return_value=1024)
    @patch(f"{_TASK}.settings")
    @patch(f"{_TASK}.extract_and_classify", return_value=("Invoice text here", "invoices", 0.95))
    @patch(f"{_TASK}.extract_metadata", return_value={"dates": ["2024-01-01"], "amounts": ["100.00"], "vendor": "Acme"})
    @patch(f"{_LLM}.extract_with_llm", side_effect=ImportError("no llm"))
    def test_updates_document_fields(
        self, _mock_llm, _mock_metadata, _mock_classify,
        mock_settings, _mock_getsize, _mock_exists,
        _mock_validate, mock_session_cls,
    ):

        mock_settings.MAX_FILE_SIZE_MB = 50

        doc = _make_mock_document()
        mock_db = _make_mock_db(doc)
        mock_session_cls.return_value = mock_db

        with patch("builtins.open", MagicMock()):
            _patch_task_self()
            result = process_document_task.run(1)

        assert result["status"] == "completed"
        assert result["document_id"] == 1
        assert result["category"] == "invoices"
        assert result["confidence"] == 0.95

        # Document fields should be updated.
        assert doc.extracted_text == "Invoice text here"
        assert doc.category == DocumentCategory.INVOICES
        assert doc.confidence_score == 0.95
        assert doc.status == DocumentStatus.COMPLETED
        assert doc.extracted_metadata == {
            "dates": ["2024-01-01"], "amounts": ["100.00"], "vendor": "Acme",
        }

        mock_db.commit.assert_called()

    @patch(f"{_TASK}.SessionLocal")
    @patch(f"{_STORAGE}._validate_path_inside_upload_dir", return_value="/uploads/test.pdf")
    @patch(f"{_TASK}.os.path.exists", return_value=True)
    @patch(f"{_TASK}.os.path.getsize", return_value=512)
    @patch(f"{_TASK}.settings")
    @patch(f"{_TASK}.extract_and_classify", return_value=("Some text", "unknown", 0.2))
    @patch(f"{_TASK}.extract_metadata", return_value={"dates": [], "amounts": [], "vendor": None})
    def test_unknown_category_mapped_correctly(
        self, _mock_metadata, _mock_classify, mock_settings,
        _mock_getsize, _mock_exists, _mock_validate, mock_session_cls,
    ):

        mock_settings.MAX_FILE_SIZE_MB = 50

        doc = _make_mock_document()
        mock_db = _make_mock_db(doc)
        mock_session_cls.return_value = mock_db

        with patch("builtins.open", MagicMock()):
            _patch_task_self()
            result = process_document_task.run(1)

        assert doc.category == DocumentCategory.UNKNOWN
        assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# 5. AI extraction success
# ---------------------------------------------------------------------------

class TestAIExtractionSuccess:

    @patch(f"{_TASK}.SessionLocal")
    @patch(f"{_STORAGE}._validate_path_inside_upload_dir", return_value="/uploads/test.pdf")
    @patch(f"{_TASK}.os.path.exists", return_value=True)
    @patch(f"{_TASK}.os.path.getsize", return_value=2048)
    @patch(f"{_TASK}.settings")
    @patch(f"{_TASK}.extract_and_classify", return_value=(
        "Long enough extracted text for AI processing", "tax", 0.88,
    ))
    @patch(f"{_TASK}.extract_metadata", return_value={"dates": [], "amounts": [], "vendor": None})
    @patch(f"{_LLM}.extract_with_llm", return_value={
        "summary": "Tax document summary",
        "fields": {"tax_year": "2024", "amount_due": "5000"},
        "provider": "openai",
    })
    def test_ai_fields_set_on_success(
        self, _mock_llm, _mock_metadata, _mock_classify,
        mock_settings, _mock_getsize, _mock_exists,
        _mock_validate, mock_session_cls,
    ):

        mock_settings.MAX_FILE_SIZE_MB = 50

        doc = _make_mock_document()
        mock_db = _make_mock_db(doc)
        mock_session_cls.return_value = mock_db

        with patch("builtins.open", MagicMock()):
            _patch_task_self()
            result = process_document_task.run(1)

        assert doc.ai_summary == "Tax document summary"
        assert doc.ai_extracted_fields == {"tax_year": "2024", "amount_due": "5000"}
        assert doc.ai_provider == "openai"
        assert doc.ai_extraction_status == "completed"
        assert doc.status == DocumentStatus.COMPLETED
        assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# 6. AI extraction failure (processing continues)
# ---------------------------------------------------------------------------

class TestAIExtractionFailure:

    @patch(f"{_TASK}.SessionLocal")
    @patch(f"{_STORAGE}._validate_path_inside_upload_dir", return_value="/uploads/test.pdf")
    @patch(f"{_TASK}.os.path.exists", return_value=True)
    @patch(f"{_TASK}.os.path.getsize", return_value=2048)
    @patch(f"{_TASK}.settings")
    @patch(f"{_TASK}.extract_and_classify", return_value=(
        "Long enough extracted text for AI processing", "bank", 0.75,
    ))
    @patch(f"{_TASK}.extract_metadata", return_value={"dates": [], "amounts": [], "vendor": None})
    @patch(f"{_LLM}.extract_with_llm", side_effect=RuntimeError("LLM service unavailable"))
    def test_ai_failure_sets_skipped_and_continues(
        self, _mock_llm, _mock_metadata, _mock_classify,
        mock_settings, _mock_getsize, _mock_exists,
        _mock_validate, mock_session_cls,
    ):

        mock_settings.MAX_FILE_SIZE_MB = 50

        doc = _make_mock_document()
        mock_db = _make_mock_db(doc)
        mock_session_cls.return_value = mock_db

        with patch("builtins.open", MagicMock()):
            _patch_task_self()
            result = process_document_task.run(1)

        # AI fields should reflect the failure gracefully.
        assert doc.ai_extraction_status == "skipped"
        assert doc.ai_summary is None
        assert doc.ai_extracted_fields is None
        assert doc.ai_provider is None

        # But overall processing still completes.
        assert doc.status == DocumentStatus.COMPLETED
        assert result["status"] == "completed"
        assert result["category"] == "bank"

    @patch(f"{_TASK}.SessionLocal")
    @patch(f"{_STORAGE}._validate_path_inside_upload_dir", return_value="/uploads/test.pdf")
    @patch(f"{_TASK}.os.path.exists", return_value=True)
    @patch(f"{_TASK}.os.path.getsize", return_value=512)
    @patch(f"{_TASK}.settings")
    @patch(f"{_TASK}.extract_and_classify", return_value=("Short", "bills", 0.6))
    @patch(f"{_TASK}.extract_metadata", return_value={"dates": [], "amounts": [], "vendor": None})
    def test_ai_skipped_when_text_too_short(
        self, _mock_metadata, _mock_classify, mock_settings,
        _mock_getsize, _mock_exists, _mock_validate, mock_session_cls,
    ):
        """AI extraction is skipped when extracted_text has <= 20 chars."""

        mock_settings.MAX_FILE_SIZE_MB = 50

        doc = _make_mock_document()
        mock_db = _make_mock_db(doc)
        mock_session_cls.return_value = mock_db

        with patch("builtins.open", MagicMock()):
            _patch_task_self()
            process_document_task.run(1)

        assert doc.ai_extraction_status == "skipped"
        assert doc.status == DocumentStatus.COMPLETED


# ---------------------------------------------------------------------------
# 7. Path traversal blocked
# ---------------------------------------------------------------------------

class TestPathTraversalBlocked:

    @patch(f"{_TASK}.SessionLocal")
    @patch(f"{_STORAGE}._validate_path_inside_upload_dir",
           side_effect=ValueError("Path traversal detected"))
    def test_path_traversal_marks_failed(self, _mock_validate, mock_session_cls):

        doc = _make_mock_document(file_path="/uploads/../../etc/passwd")
        mock_db = _make_mock_db(doc)
        mock_session_cls.return_value = mock_db

        _patch_task_self()
        result = process_document_task.run(1)

        assert result == {"error": "Invalid file path"}
        assert doc.status == DocumentStatus.FAILED
        assert doc.extracted_text == "File path validation failed."
        mock_db.commit.assert_called()


# ---------------------------------------------------------------------------
# 8. Progress reporting via update_state
# ---------------------------------------------------------------------------

class TestProgressReporting:

    @patch(f"{_TASK}.SessionLocal")
    @patch(f"{_STORAGE}._validate_path_inside_upload_dir", return_value="/uploads/test.pdf")
    @patch(f"{_TASK}.os.path.exists", return_value=True)
    @patch(f"{_TASK}.os.path.getsize", return_value=1024)
    @patch(f"{_TASK}.settings")
    @patch(f"{_TASK}.extract_and_classify", return_value=(
        "Enough text for full pipeline run!", "tickets", 0.99,
    ))
    @patch(f"{_TASK}.extract_metadata", return_value={"dates": [], "amounts": [], "vendor": None})
    def test_update_state_called_for_each_stage(
        self, _mock_metadata, _mock_classify, mock_settings,
        _mock_getsize, _mock_exists, _mock_validate, mock_session_cls,
    ):

        mock_settings.MAX_FILE_SIZE_MB = 50

        doc = _make_mock_document()
        mock_db = _make_mock_db(doc)
        mock_session_cls.return_value = mock_db

        with patch("builtins.open", MagicMock()):
            _patch_task_self()
            process_document_task.run(1)

        # Collect every stage name reported to update_state.
        actual_stages = []
        for call in process_document_task.update_state.call_args_list:
            meta = call.kwargs.get("meta")
            if meta and "stage" in meta:
                actual_stages.append(meta["stage"])

        assert "reading_file" in actual_stages
        assert "extracting_text" in actual_stages
        assert "extracting_metadata" in actual_stages
        assert "ai_extraction" in actual_stages
        assert "saving_results" in actual_stages
