"""Phase 12 evidence_service unit tests — MagicMock-based."""
from unittest.mock import MagicMock, patch

import pytest

from app.compliance.services.evidence_service import (
    attach_document,
    detach_document,
)


def test_attach_returns_existing_when_already_attached():
    """Idempotency contract — re-attaching the same document is a no-op."""
    notice = MagicMock(id=10, client_id=5)
    existing = MagicMock(id=99, document_id=42)
    document = MagicMock(user_id=7)  # owned by attaching user

    db = MagicMock()
    db.get.return_value = document
    db.query.return_value.filter.return_value.first.return_value = existing

    result = attach_document(
        db, notice=notice, document_id=42, user_id=7
    )
    assert result is existing
    db.add.assert_not_called()


def test_attach_inserts_new_when_not_present():
    """User owns the document, no existing attachment → row inserted."""
    notice = MagicMock(id=10, client_id=5)
    document = MagicMock(user_id=7)  # owned by attaching user
    db = MagicMock()
    db.get.return_value = document
    db.query.return_value.filter.return_value.first.return_value = None

    with patch("app.compliance.services.evidence_service.log_activity"), \
         patch("app.compliance.services.evidence_service.log_audit_event"):
        attach_document(
            db, notice=notice, document_id=42, user_id=7,
            description="Invoice ledger",
        )
    db.add.assert_called()
    assert db.commit.called


def test_attach_raises_when_document_not_owned_and_not_shared():
    """H-C — non-owner without DocumentPermission row gets DocumentAccessDenied."""
    from app.compliance.services.evidence_service import DocumentAccessDenied

    notice = MagicMock(id=10, client_id=5)
    document = MagicMock(user_id=99)  # owned by SOMEONE ELSE
    db = MagicMock()
    db.get.return_value = document
    # The DocumentPermission lookup returns None (not shared)
    db.query.return_value.filter.return_value.first.return_value = None

    with pytest.raises(DocumentAccessDenied):
        attach_document(db, notice=notice, document_id=42, user_id=7)


def test_attach_succeeds_when_document_shared_via_permission():
    """H-C — non-owner WITH a DocumentPermission row can attach."""
    notice = MagicMock(id=10, client_id=5)
    document = MagicMock(user_id=99)  # owned by other user
    shared_perm = MagicMock(id=1, user_id=7, document_id=42)
    existing_attachment = None  # not attached yet

    db = MagicMock()
    db.get.return_value = document
    # First filter call → DocumentPermission lookup → returns the shared row
    # Second filter call → existing-attachment lookup → returns None
    db.query.return_value.filter.return_value.first.side_effect = [
        shared_perm, existing_attachment,
    ]

    with patch("app.compliance.services.evidence_service.log_activity"), \
         patch("app.compliance.services.evidence_service.log_audit_event"):
        attach_document(
            db, notice=notice, document_id=42, user_id=7,
        )
    db.add.assert_called()


def test_attach_raises_when_document_missing():
    notice = MagicMock(id=10, client_id=5)
    db = MagicMock()
    db.get.return_value = None  # Document not found

    with pytest.raises(ValueError):
        attach_document(db, notice=notice, document_id=999, user_id=7)


def test_detach_returns_false_when_not_attached():
    notice = MagicMock(id=10, client_id=5)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    assert detach_document(db, notice=notice, document_id=42, user_id=7) is False


def test_detach_returns_true_when_removed():
    notice = MagicMock(id=10, client_id=5)
    existing = MagicMock(id=99)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = existing

    with patch("app.compliance.services.evidence_service.log_audit_event"):
        result = detach_document(db, notice=notice, document_id=42, user_id=7)
    assert result is True
    db.delete.assert_called_with(existing)
