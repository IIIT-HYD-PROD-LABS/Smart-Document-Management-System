"""Tests for document upload, CRUD, batch-delete, and stats endpoints.

All tests run WITHOUT a real database, Celery broker, or storage backend.
Dependencies are overridden with mocks via FastAPI dependency_overrides.
"""

from datetime import datetime, timezone
from io import BytesIO
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from app.models.document import DocumentCategory, DocumentStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_PDF_BYTES = b"%PDF-1.4 test content"


def _make_mock_user(user_id=1, role="editor", email="test@example.com", username="testuser"):
    """Create a mock User object."""
    user = MagicMock()
    user.id = user_id
    user.email = email
    user.username = username
    user.role = role
    user.is_active = True
    return user


def _make_mock_document(**kwargs):
    """Create a mock Document ORM object with sensible defaults."""
    doc = MagicMock()
    doc.id = kwargs.get("id", 1)
    doc.user_id = kwargs.get("user_id", 1)
    doc.filename = kwargs.get("filename", "abc123_test.pdf")
    doc.original_filename = kwargs.get("original_filename", "test.pdf")
    doc.file_type = kwargs.get("file_type", "pdf")
    doc.file_size = kwargs.get("file_size", 1024)
    doc.file_path = kwargs.get("file_path", "/uploads/abc123_test.pdf")
    doc.s3_url = kwargs.get("s3_url", None)
    doc.extracted_text = kwargs.get("extracted_text", "sample extracted text")
    doc.extracted_metadata = kwargs.get("extracted_metadata", None)
    doc.ai_summary = kwargs.get("ai_summary", None)
    doc.ai_extracted_fields = kwargs.get("ai_extracted_fields", None)
    doc.ai_extraction_status = kwargs.get("ai_extraction_status", None)
    doc.ai_provider = kwargs.get("ai_provider", None)
    doc.highlighted_text = kwargs.get("highlighted_text", None)
    doc.celery_task_id = kwargs.get("celery_task_id", None)
    doc.search_vector = None
    doc.current_version = kwargs.get("current_version", 1)

    # Use real enum values so Pydantic from_attributes serialization works correctly
    status_val = kwargs.get("status", "completed")
    doc.status = DocumentStatus(status_val) if isinstance(status_val, str) else status_val

    category_val = kwargs.get("category", "bills")
    doc.category = DocumentCategory(category_val) if isinstance(category_val, str) else category_val

    doc.confidence_score = kwargs.get("confidence_score", 0.95)
    doc.created_at = kwargs.get("created_at", datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc))
    doc.updated_at = kwargs.get("updated_at", None)

    # versions relationship for DocumentResponse.compute_total_versions
    doc.versions = kwargs.get("versions", [])

    # __table__ for model_validate introspection
    table_mock = MagicMock()
    table_mock.columns.keys.return_value = [
        "id", "user_id", "filename", "original_filename", "file_type",
        "file_size", "file_path", "s3_url", "category", "confidence_score",
        "extracted_text", "extracted_metadata", "ai_summary",
        "ai_extracted_fields", "ai_extraction_status", "ai_provider",
        "highlighted_text", "status", "current_version", "celery_task_id",
        "search_vector", "created_at", "updated_at",
    ]
    doc.__table__ = table_mock

    return doc


def _make_mock_db():
    """Create a mock SQLAlchemy session."""
    db = MagicMock()
    return db


def _build_client(user=None, db=None):
    """Build a TestClient with overridden dependencies.

    Returns (client, app, user, db) so callers can configure the mock db
    before making requests.
    """
    from app.main import app
    from app.database import get_db
    from app.utils.security import get_current_user, require_editor
    from app.utils.rate_limiter import limiter

    if user is None:
        user = _make_mock_user()
    if db is None:
        db = _make_mock_db()

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[require_editor] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    limiter.enabled = False

    client = TestClient(app, raise_server_exceptions=False)
    return client, app, user, db


def _cleanup_overrides(app):
    """Remove all dependency overrides to avoid test pollution."""
    from app.database import get_db
    from app.utils.security import get_current_user, require_editor
    from app.utils.rate_limiter import limiter

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(require_editor, None)
    app.dependency_overrides.pop(get_db, None)
    limiter.enabled = True


# =========================================================================
# 1. Upload Validation
# =========================================================================

class TestUploadValidation:
    """Tests for POST /api/documents/upload."""

    def test_upload_rejected_file_type_exe(self):
        """Uploading an .exe file is rejected with 400."""
        client, app, user, db = _build_client()
        try:
            file_data = BytesIO(b"MZ\x90\x00 fake exe content")
            resp = client.post(
                "/api/documents/upload",
                files={"file": ("malware.exe", file_data, "application/octet-stream")},
            )
            assert resp.status_code == 400
            assert "not allowed" in resp.json()["detail"].lower()
        finally:
            _cleanup_overrides(app)

    def test_upload_rejected_file_type_sh(self):
        """Uploading a .sh file is rejected with 400."""
        client, app, user, db = _build_client()
        try:
            file_data = BytesIO(b"#!/bin/bash\nrm -rf /")
            resp = client.post(
                "/api/documents/upload",
                files={"file": ("script.sh", file_data, "text/x-shellscript")},
            )
            assert resp.status_code == 400
            assert "not allowed" in resp.json()["detail"].lower()
        finally:
            _cleanup_overrides(app)

    @patch("app.routers.documents.settings")
    def test_upload_rejected_file_too_large(self, mock_settings):
        """File exceeding MAX_FILE_SIZE_MB is rejected with 400."""
        mock_settings.ALLOWED_EXTENSIONS = ["pdf"]
        mock_settings.MAX_FILE_SIZE_MB = 1  # 1 MB limit
        mock_settings.RATE_LIMIT_UPLOAD = "100/minute"

        client, app, user, db = _build_client()
        try:
            # Create content larger than 1 MB
            large_content = MOCK_PDF_BYTES + b"\x00" * (2 * 1024 * 1024)
            file_data = BytesIO(large_content)
            resp = client.post(
                "/api/documents/upload",
                files={"file": ("large.pdf", file_data, "application/pdf")},
            )
            assert resp.status_code == 400
            assert "too large" in resp.json()["detail"].lower()
        finally:
            _cleanup_overrides(app)

    @patch("app.routers.documents.save_file")
    @patch("app.services.storage_service.validate_magic_bytes", return_value=True)
    @patch("app.services.audit_service.log_audit_event")
    def test_upload_valid_pdf_returns_202(
        self, mock_audit, mock_magic, mock_save_file,
    ):
        """Valid PDF upload returns 202 with document info."""
        mock_save_file.return_value = ("/uploads/abc123_test.pdf", None)

        # Mock the Celery task that is imported locally inside the upload function.
        # We patch it on the tasks module so the local import picks up our mock.
        mock_celery_result = MagicMock()
        mock_celery_result.id = "task-abc-123"
        mock_task = MagicMock()
        mock_task.delay.return_value = mock_celery_result

        client, app, user, db = _build_client()

        # Configure mock DB: no existing doc, commit succeeds, refresh populates id
        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.with_for_update.return_value = mock_query
        mock_query.first.return_value = None  # no existing document
        db.query.return_value = mock_query

        def _set_doc_id(doc=None):
            """Simulate database assigning an id on commit."""
            if hasattr(db, '_added_docs') and db._added_docs:
                for d in db._added_docs:
                    if not hasattr(d, '_id_set') or not d._id_set:
                        d.id = 42
                        d._id_set = True

        db._added_docs = []

        def _track_add(obj):
            db._added_docs.append(obj)

        db.add = _track_add
        db.commit.side_effect = _set_doc_id

        def _refresh(obj):
            obj.id = 42
            obj.original_filename = "test.pdf"
            obj.current_version = 1
            obj.status = MagicMock()
            obj.status.value = "pending"

        db.refresh = _refresh

        try:
            with patch("app.tasks.document_tasks.process_document_task", mock_task):
                file_data = BytesIO(MOCK_PDF_BYTES)
                resp = client.post(
                    "/api/documents/upload",
                    files={"file": ("test.pdf", file_data, "application/pdf")},
                )
            assert resp.status_code == 202
            body = resp.json()
            assert body["filename"] == "test.pdf"
            assert body["status"] == "pending"
            assert body["task_id"] == "task-abc-123"
            mock_save_file.assert_called_once()
            mock_task.delay.assert_called_once()
        finally:
            _cleanup_overrides(app)

    def test_upload_missing_filename_returns_400(self):
        """Upload with empty filename is rejected."""
        client, app, user, db = _build_client()
        try:
            file_data = BytesIO(MOCK_PDF_BYTES)
            resp = client.post(
                "/api/documents/upload",
                files={"file": ("", file_data, "application/pdf")},
            )
            # FastAPI treats empty filename as missing - expect 400
            assert resp.status_code == 400
        finally:
            _cleanup_overrides(app)


# =========================================================================
# 2. Get All Documents
# =========================================================================

class TestGetAllDocuments:
    """Tests for GET /api/documents/all."""

    def test_get_all_returns_paginated_list(self):
        """Returns documents with pagination metadata."""
        doc1 = _make_mock_document(id=1, original_filename="doc1.pdf")
        doc2 = _make_mock_document(id=2, original_filename="doc2.pdf")

        client, app, user, db = _build_client()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 2
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [doc1, doc2]
        db.query.return_value = mock_query

        try:
            resp = client.get("/api/documents/all")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 2
            assert body["page"] == 1
            assert body["per_page"] == 20
            assert len(body["documents"]) == 2
        finally:
            _cleanup_overrides(app)

    def test_get_all_respects_per_page_limit(self):
        """Respects custom per_page query parameter."""
        doc1 = _make_mock_document(id=1)

        client, app, user, db = _build_client()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 50
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [doc1]
        db.query.return_value = mock_query

        try:
            resp = client.get("/api/documents/all?per_page=5&page=2")
            assert resp.status_code == 200
            body = resp.json()
            assert body["page"] == 2
            assert body["per_page"] == 5
        finally:
            _cleanup_overrides(app)

    def test_get_all_filters_by_current_user(self):
        """Only documents belonging to the current user are returned."""
        client, app, user, db = _build_client()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        db.query.return_value = mock_query

        try:
            resp = client.get("/api/documents/all")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 0
            assert body["documents"] == []
            # Verify the filter was called (user_id filtering)
            mock_query.filter.assert_called()
        finally:
            _cleanup_overrides(app)

    def test_get_all_empty_returns_empty_list(self):
        """User with no documents gets an empty list, not an error."""
        client, app, user, db = _build_client()

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.order_by.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = []
        db.query.return_value = mock_query

        try:
            resp = client.get("/api/documents/all")
            assert resp.status_code == 200
            body = resp.json()
            assert body["documents"] == []
            assert body["total"] == 0
        finally:
            _cleanup_overrides(app)


# =========================================================================
# 3. Get Document by ID
# =========================================================================

class TestGetDocumentById:
    """Tests for GET /api/documents/{document_id}."""

    def test_get_document_owned_by_user(self):
        """Returns document detail when user is the owner."""
        doc = _make_mock_document(id=10, user_id=1)

        client, app, user, db = _build_client()

        mock_query = MagicMock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = doc
        db.query.return_value = mock_query

        try:
            resp = client.get("/api/documents/10")
            assert resp.status_code == 200
            body = resp.json()
            assert body["id"] == 10
            assert body["original_filename"] == "test.pdf"
        finally:
            _cleanup_overrides(app)

    def test_get_document_not_found(self):
        """Returns 404 when document does not exist."""
        client, app, user, db = _build_client()

        mock_query = MagicMock()
        mock_query.options.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None  # document not found
        db.query.return_value = mock_query

        try:
            resp = client.get("/api/documents/9999")
            assert resp.status_code == 404
            assert "not found" in resp.json()["detail"].lower()
        finally:
            _cleanup_overrides(app)

    def test_get_document_not_accessible_returns_404(self):
        """Returns 404 when document belongs to another user and no shared access."""
        other_user_doc = _make_mock_document(id=5, user_id=999)

        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        # First query returns the doc (it exists), second returns None (no permission)
        mock_doc_query = MagicMock()
        mock_doc_query.filter.return_value = mock_doc_query
        mock_doc_query.first.return_value = other_user_doc

        mock_perm_query = MagicMock()
        mock_perm_query.filter.return_value = mock_perm_query
        mock_perm_query.first.return_value = None  # no shared permission

        # The function queries Document first, then DocumentPermission
        from app.models.document import Document
        from app.models.document_permission import DocumentPermission

        def query_side_effect(model):
            q = MagicMock()
            q.options.return_value = q
            q.filter.return_value = q
            if model is Document:
                q.first.return_value = other_user_doc
            elif model is DocumentPermission:
                q.first.return_value = None
            return q

        db.query.side_effect = query_side_effect

        try:
            resp = client.get("/api/documents/5")
            assert resp.status_code == 404
        finally:
            _cleanup_overrides(app)


# =========================================================================
# 4. Delete Document
# =========================================================================

class TestDeleteDocument:
    """Tests for DELETE /api/documents/{document_id}."""

    @patch("app.routers.documents.delete_file")
    @patch("app.services.audit_service.log_audit_event")
    def test_owner_can_delete_document(self, mock_audit, mock_delete_file):
        """Document owner can delete their document, returns 204."""
        doc = _make_mock_document(id=3, user_id=1)
        doc.versions = []

        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = doc
        db.query.return_value = mock_query

        try:
            resp = client.delete("/api/documents/3")
            assert resp.status_code == 204
            db.delete.assert_called_once_with(doc)
            db.commit.assert_called_once()
        finally:
            _cleanup_overrides(app)

    @patch("app.services.audit_service.log_audit_event")
    def test_non_owner_cannot_delete_document(self, mock_audit):
        """Non-owner non-admin cannot delete another user's document (404)."""
        doc = _make_mock_document(id=7, user_id=999)  # owned by user 999

        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = doc
        db.query.return_value = mock_query

        try:
            resp = client.delete("/api/documents/7")
            # The router returns 404 (not 403) to avoid leaking document existence
            assert resp.status_code == 404
            db.delete.assert_not_called()
        finally:
            _cleanup_overrides(app)

    @patch("app.routers.documents.delete_file")
    @patch("app.services.audit_service.log_audit_event")
    def test_admin_can_delete_any_document(self, mock_audit, mock_delete_file):
        """Admin user can delete any document regardless of ownership."""
        doc = _make_mock_document(id=15, user_id=999)
        doc.versions = []

        admin_user = _make_mock_user(user_id=2, role="admin")
        client, app, _, db = _build_client(user=admin_user)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = doc
        db.query.return_value = mock_query

        try:
            resp = client.delete("/api/documents/15")
            assert resp.status_code == 204
            db.delete.assert_called_once_with(doc)
        finally:
            _cleanup_overrides(app)

    def test_delete_nonexistent_document_returns_404(self):
        """Deleting a document that does not exist returns 404."""
        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.first.return_value = None
        db.query.return_value = mock_query

        try:
            resp = client.delete("/api/documents/9999")
            assert resp.status_code == 404
        finally:
            _cleanup_overrides(app)


# =========================================================================
# 5. Batch Delete
# =========================================================================

class TestBatchDelete:
    """Tests for POST /api/documents/batch-delete."""

    @patch("app.routers.documents.delete_file")
    @patch("app.services.audit_service.log_audit_event")
    def test_batch_delete_valid_ids(self, mock_audit, mock_delete_file):
        """Batch delete with valid IDs returns deleted list."""
        doc1 = _make_mock_document(id=1, user_id=1)
        doc1.versions = []
        doc2 = _make_mock_document(id=2, user_id=1)
        doc2.versions = []

        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        mock_query.all.return_value = [doc1, doc2]
        db.query.return_value = mock_query

        try:
            resp = client.post(
                "/api/documents/batch-delete",
                json=[1, 2],
            )
            assert resp.status_code == 200
            body = resp.json()
            assert set(body["deleted"]) == {1, 2}
            assert body["count"] == 2
        finally:
            _cleanup_overrides(app)

    def test_batch_delete_empty_list_rejected(self):
        """Empty list of IDs is rejected with 400."""
        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        try:
            resp = client.post(
                "/api/documents/batch-delete",
                json=[],
            )
            assert resp.status_code == 400
            assert "1-100" in resp.json()["detail"]
        finally:
            _cleanup_overrides(app)

    def test_batch_delete_too_many_ids_rejected(self):
        """More than 100 IDs is rejected with 400."""
        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        try:
            ids = list(range(1, 102))  # 101 IDs
            resp = client.post(
                "/api/documents/batch-delete",
                json=ids,
            )
            assert resp.status_code == 400
            assert "1-100" in resp.json()["detail"]
        finally:
            _cleanup_overrides(app)

    def test_batch_delete_negative_ids_rejected(self):
        """Negative document IDs are rejected with 400."""
        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        try:
            resp = client.post(
                "/api/documents/batch-delete",
                json=[-1, 5],
            )
            assert resp.status_code == 400
            assert "positive" in resp.json()["detail"].lower()
        finally:
            _cleanup_overrides(app)

    def test_batch_delete_zero_id_rejected(self):
        """Zero is not a valid document ID."""
        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        try:
            resp = client.post(
                "/api/documents/batch-delete",
                json=[0, 1],
            )
            assert resp.status_code == 400
            assert "positive" in resp.json()["detail"].lower()
        finally:
            _cleanup_overrides(app)

    @patch("app.routers.documents.delete_file")
    @patch("app.services.audit_service.log_audit_event")
    def test_batch_delete_only_deletes_owned_documents(self, mock_audit, mock_delete_file):
        """Batch delete silently ignores documents not owned by the user."""
        doc_owned = _make_mock_document(id=1, user_id=1)
        doc_owned.versions = []
        # doc with id=2 belongs to user_id=999, so it will not appear in the query result

        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        mock_query = MagicMock()
        mock_query.filter.return_value = mock_query
        # Query filters to user_id=1, so only doc_owned is returned
        mock_query.all.return_value = [doc_owned]
        db.query.return_value = mock_query

        try:
            resp = client.post(
                "/api/documents/batch-delete",
                json=[1, 2],
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["deleted"] == [1]
            assert body["count"] == 1
        finally:
            _cleanup_overrides(app)


# =========================================================================
# 6. Document Stats
# =========================================================================

class TestDocumentStats:
    """Tests for GET /api/documents/stats."""

    def test_stats_returns_category_counts(self):
        """Stats endpoint returns category counts and status counts."""
        from app.models.document import DocumentCategory, DocumentStatus

        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        # Mock category group-by result
        cat_rows = [
            (DocumentCategory.BILLS, 5),
            (DocumentCategory.TAX, 3),
            (DocumentCategory.INVOICES, 2),
        ]

        # Mock status group-by result
        status_rows = [
            (DocumentStatus.COMPLETED, 8),
            (DocumentStatus.PROCESSING, 1),
            (DocumentStatus.FAILED, 1),
        ]

        # Mock recent uploads
        recent_doc = _make_mock_document(id=1, user_id=1, category="bills")

        call_count = [0]

        def query_side_effect(model_or_cols, *args):
            """Route different db.query() calls to correct mocks."""
            call_count[0] += 1
            q = MagicMock()
            q.filter.return_value = q
            q.group_by.return_value = q
            q.order_by.return_value = q
            q.limit.return_value = q

            if call_count[0] == 1:
                # First call: category counts
                q.all.return_value = cat_rows
            elif call_count[0] == 2:
                # Second call: recent uploads
                q.all.return_value = [recent_doc]
            elif call_count[0] == 3:
                # Third call: status counts
                q.all.return_value = status_rows
            return q

        db.query.side_effect = query_side_effect

        try:
            resp = client.get("/api/documents/stats")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_documents"] == 10  # 5+3+2
            assert body["category_counts"]["bills"] == 5
            assert body["category_counts"]["tax"] == 3
            assert body["category_counts"]["invoices"] == 2
            assert body["completed_count"] == 8
            assert body["processing_count"] == 1
            assert body["failed_count"] == 1
            assert len(body["recent_uploads"]) == 1
        finally:
            _cleanup_overrides(app)

    def test_stats_empty_user_returns_zeros(self):
        """Stats for a user with no documents returns all zeros."""
        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        call_count = [0]

        def query_side_effect(model_or_cols, *args):
            call_count[0] += 1
            q = MagicMock()
            q.filter.return_value = q
            q.group_by.return_value = q
            q.order_by.return_value = q
            q.limit.return_value = q
            q.all.return_value = []
            return q

        db.query.side_effect = query_side_effect

        try:
            resp = client.get("/api/documents/stats")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_documents"] == 0
            assert body["category_counts"] == {}
            assert body["processing_count"] == 0
            assert body["completed_count"] == 0
            assert body["failed_count"] == 0
            assert body["recent_uploads"] == []
        finally:
            _cleanup_overrides(app)

    def test_stats_single_category(self):
        """Stats with documents in only one category."""
        from app.models.document import DocumentCategory, DocumentStatus

        user = _make_mock_user(user_id=1, role="editor")
        client, app, _, db = _build_client(user=user)

        cat_rows = [(DocumentCategory.UPI, 12)]
        status_rows = [(DocumentStatus.COMPLETED, 12)]

        call_count = [0]

        def query_side_effect(model_or_cols, *args):
            call_count[0] += 1
            q = MagicMock()
            q.filter.return_value = q
            q.group_by.return_value = q
            q.order_by.return_value = q
            q.limit.return_value = q
            if call_count[0] == 1:
                q.all.return_value = cat_rows
            elif call_count[0] == 2:
                q.all.return_value = []  # no recent docs needed
            elif call_count[0] == 3:
                q.all.return_value = status_rows
            return q

        db.query.side_effect = query_side_effect

        try:
            resp = client.get("/api/documents/stats")
            assert resp.status_code == 200
            body = resp.json()
            assert body["total_documents"] == 12
            assert body["category_counts"] == {"upi": 12}
        finally:
            _cleanup_overrides(app)
