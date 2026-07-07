"""Regression test for bulk_update_status idempotent handling.

Root cause: bulk_update_status called transition_notice_status for every
notice_id unconditionally. When a notice was already in the target state
(e.g. received->under_review via single-row PATCH, then bulk update with
same target), validate_transition raised InvalidTransitionError because
under_review->under_review is not in ALLOWED_TRANSITIONS. The fix adds a
pre-check: if current state == target, count as no-op success and skip.

async-migration: bulk_update_status is async now, and its idempotency
pre-check uses `(await db.execute(select(...))).scalar()` instead of
`db.query(...).filter(...).scalar()`.
"""
from unittest.mock import AsyncMock, MagicMock, patch


def _db_returning(*status_values):
    db = MagicMock()
    results = []
    for val in status_values:
        result = MagicMock()
        result.scalar.return_value = val
        results.append(result)
    db.execute = AsyncMock(side_effect=results)
    db.rollback = AsyncMock()
    return db


async def test_bulk_update_idempotent_same_state():
    """Bulk updating a notice to its current state must succeed (no-op)."""
    from app.compliance.services.notice_state_machine import NoticeStatus

    notice_id = 99
    user = MagicMock()
    user.id = 1

    db = _db_returning("under_review")

    with patch(
        "app.compliance.services.notice_service.transition_notice_status",
        new=AsyncMock(),
    ) as mock_transition:
        from app.compliance.services.notice_service import bulk_update_status
        result = await bulk_update_status(db, [notice_id], NoticeStatus.UNDER_REVIEW, user)

    # transition_notice_status must NOT be called — the idempotent check
    # should have short-circuited before reaching it.
    mock_transition.assert_not_called()
    assert result["summary"]["ok"] == 1
    assert result["summary"]["failed"] == 0
    assert result["results"][0]["success"] is True
    assert result["results"][0]["error"] is None


async def test_bulk_update_invalid_transition_still_fails():
    """Bulk updating a notice to an invalid target must still report failure."""
    from app.compliance.services.notice_state_machine import (
        InvalidTransitionError,
        NoticeStatus,
    )

    notice_id = 98
    user = MagicMock()
    user.id = 1

    # Notice is dismissed; target is under_review — different states
    db = _db_returning("dismissed")

    with patch(
        "app.compliance.services.notice_service.transition_notice_status",
        new=AsyncMock(
            side_effect=InvalidTransitionError(
                "Cannot transition from dismissed to under_review. Allowed: []"
            )
        ),
    ):
        from app.compliance.services.notice_service import bulk_update_status
        result = await bulk_update_status(db, [notice_id], NoticeStatus.UNDER_REVIEW, user)

    assert result["summary"]["ok"] == 0
    assert result["summary"]["failed"] == 1
    assert result["results"][0]["success"] is False
    assert "dismissed" in result["results"][0]["error"]


async def test_bulk_update_terminal_state_idempotent():
    """Bulk updating a dismissed notice to dismissed must succeed (no-op)."""
    from app.compliance.services.notice_state_machine import NoticeStatus

    notice_id = 97
    user = MagicMock()
    user.id = 1

    db = _db_returning("dismissed")

    with patch(
        "app.compliance.services.notice_service.transition_notice_status",
        new=AsyncMock(),
    ) as mock_transition:
        from app.compliance.services.notice_service import bulk_update_status
        result = await bulk_update_status(db, [notice_id], NoticeStatus.DISMISSED, user)

    mock_transition.assert_not_called()
    assert result["summary"]["ok"] == 1
    assert result["summary"]["failed"] == 0


async def test_bulk_update_mixed_idempotent_and_valid():
    """Mixed batch: already-in-target (idempotent) + valid transition."""
    from app.compliance.services.notice_state_machine import NoticeStatus

    id_already = 96
    id_pending = 95
    user = MagicMock()
    user.id = 1

    # First call returns "under_review" (idempotent), second "received" (valid)
    db = _db_returning("under_review", "received")

    transition_call_count = {"n": 0}

    async def _mock_transition(db_, nid, new_status, user_, reason=None, client_id=None):
        transition_call_count["n"] += 1

    with patch(
        "app.compliance.services.notice_service.transition_notice_status",
        new=AsyncMock(side_effect=_mock_transition),
    ):
        from app.compliance.services.notice_service import bulk_update_status
        result = await bulk_update_status(
            db, [id_already, id_pending], NoticeStatus.UNDER_REVIEW, user
        )

    # transition must only be called for the pending notice, not the already-in-target one
    assert transition_call_count["n"] == 1
    assert result["summary"]["ok"] == 2
    assert result["summary"]["failed"] == 0
