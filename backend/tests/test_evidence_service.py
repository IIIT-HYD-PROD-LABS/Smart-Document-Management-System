"""Phase 12 evidence_service unit tests — AsyncMock for the AsyncSession."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.compliance.services.evidence_service import (
    attach_document,
    detach_document,
)


def _mock_db(document=None, execute_results=None):
    """AsyncMock DB: `.get()` resolves to `document`; each `.execute()` call
    resolves in order to a MagicMock whose `.scalar_one_or_none()` returns
    the next value in `execute_results`."""
    db = MagicMock()
    db.get = AsyncMock(return_value=document)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    if execute_results is not None:
        results = []
        for v in execute_results:
            result = MagicMock()
            result.scalar_one_or_none.return_value = v
            results.append(result)
        db.execute = AsyncMock(side_effect=results)
    return db


async def test_attach_returns_existing_when_already_attached():
    """Idempotency contract — re-attaching the same document is a no-op."""
    notice = MagicMock(id=10, client_id=5)
    existing = MagicMock(id=99, document_id=42)
    document = MagicMock(user_id=7)  # owned by attaching user

    # Owner match skips the DocumentPermission lookup; only the
    # existing-attachment query runs.
    db = _mock_db(document=document, execute_results=[existing])

    result = await attach_document(
        db, notice=notice, document_id=42, user_id=7
    )
    assert result is existing
    db.add.assert_not_called()


async def test_attach_inserts_new_when_not_present():
    """User owns the document, no existing attachment → row inserted."""
    notice = MagicMock(id=10, client_id=5)
    document = MagicMock(user_id=7)  # owned by attaching user
    db = _mock_db(document=document, execute_results=[None])

    with patch("app.compliance.services.evidence_service.log_activity"), \
         patch("app.compliance.services.evidence_service.log_audit_event"):
        await attach_document(
            db, notice=notice, document_id=42, user_id=7,
            description="Invoice ledger",
        )
    db.add.assert_called()
    assert db.commit.called


async def test_attach_raises_when_document_not_owned_and_not_shared():
    """H-C — non-owner without DocumentPermission row gets DocumentAccessDenied."""
    from app.compliance.services.evidence_service import DocumentAccessDenied

    notice = MagicMock(id=10, client_id=5)
    document = MagicMock(user_id=99)  # owned by SOMEONE ELSE
    # The DocumentPermission lookup returns None (not shared)
    db = _mock_db(document=document, execute_results=[None])

    with pytest.raises(DocumentAccessDenied):
        await attach_document(db, notice=notice, document_id=42, user_id=7)


async def test_attach_succeeds_when_document_shared_via_permission():
    """H-C — non-owner WITH a DocumentPermission row can attach."""
    notice = MagicMock(id=10, client_id=5)
    document = MagicMock(user_id=99)  # owned by other user
    shared_perm = MagicMock(id=1, user_id=7, document_id=42)
    existing_attachment = None  # not attached yet

    # First execute → DocumentPermission lookup → returns the shared row
    # Second execute → existing-attachment lookup → returns None
    db = _mock_db(document=document, execute_results=[shared_perm, existing_attachment])

    with patch("app.compliance.services.evidence_service.log_activity"), \
         patch("app.compliance.services.evidence_service.log_audit_event"):
        await attach_document(
            db, notice=notice, document_id=42, user_id=7,
        )
    db.add.assert_called()


async def test_attach_raises_when_document_missing():
    notice = MagicMock(id=10, client_id=5)
    db = _mock_db(document=None)  # Document not found

    with pytest.raises(ValueError):
        await attach_document(db, notice=notice, document_id=999, user_id=7)


async def test_detach_returns_false_when_not_attached():
    notice = MagicMock(id=10, client_id=5)
    document = MagicMock(user_id=7)  # owned by the detaching user
    db = _mock_db(document=document, execute_results=[None])

    assert await detach_document(db, notice=notice, document_id=42, user_id=7) is False


async def test_detach_returns_true_when_removed():
    notice = MagicMock(id=10, client_id=5)
    document = MagicMock(user_id=7)  # owned by the detaching user
    existing = MagicMock(id=99)
    db = _mock_db(document=document, execute_results=[existing])

    with patch("app.compliance.services.evidence_service.log_audit_event"):
        result = await detach_document(db, notice=notice, document_id=42, user_id=7)
    assert result is True
    db.delete.assert_awaited_with(existing)


async def test_detach_raises_when_document_not_owned_and_not_shared():
    """R6 — symmetric with attach: a non-owner without a DocumentPermission
    row cannot detach another user's document from a notice."""
    from app.compliance.services.evidence_service import DocumentAccessDenied

    notice = MagicMock(id=10, client_id=5)
    document = MagicMock(user_id=99)  # owned by someone else
    # DocumentPermission lookup returns None (not shared with user 7).
    db = _mock_db(document=document, execute_results=[None])

    with pytest.raises(DocumentAccessDenied):
        await detach_document(db, notice=notice, document_id=42, user_id=7)
