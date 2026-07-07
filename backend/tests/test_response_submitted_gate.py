"""Phase 12 cross-cutting test — `submitted` transition blocked until response approved.

Per RESEARCH-FINAL §1 #9: notice_state_machine permits Received → Under
Review → Response Drafted → Submitted, but Phase 12 adds a service-layer
gate so a notice cannot transition to `submitted` until its response has
reached `approved` status. This test exercises that gate using mocks
(no DB), since the service is the single point of mutation per Phase 9
D-D pattern.

async-migration: notice_service/response_service are async now, so the
mocked `db` is a MagicMock with `db.execute` as an AsyncMock whose
result's `.scalar_one()` returns the notice (mirrors the service's
`(await db.execute(...)).scalar_one()` call)."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _patched_db_returning(notice):
    db = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = notice
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.rollback = AsyncMock()
    return db


async def test_transition_to_submitted_without_response_blocked():
    """Notice → submitted with no response should raise InvalidTransitionError."""
    from app.compliance.services.notice_service import transition_notice_status
    from app.compliance.services.notice_state_machine import (
        InvalidTransitionError, NoticeStatus,
    )

    notice = MagicMock()
    notice.id = 42
    notice.client_id = 5
    notice.status = "response_drafted"
    db = _patched_db_returning(notice)

    user = MagicMock(id=1, role="admin")

    with patch(
        "app.compliance.services.response_service.is_response_approved",
        new=AsyncMock(return_value=False),
    ):
        with pytest.raises(InvalidTransitionError) as exc_info:
            await transition_notice_status(
                db, notice.id, NoticeStatus.SUBMITTED, user
            )
    assert "response is not approved" in str(exc_info.value).lower()


async def test_transition_to_submitted_with_approved_response_allowed():
    """Once is_response_approved returns True, the gate opens."""
    from app.compliance.services.notice_service import transition_notice_status
    from app.compliance.services.notice_state_machine import NoticeStatus

    notice = MagicMock()
    notice.id = 42
    notice.client_id = 5
    notice.status = "response_drafted"
    notice.assigned_user_id = None
    notice.response_deadline = None
    notice.parent_notice_id = None
    db = _patched_db_returning(notice)

    user = MagicMock(id=1, role="admin")

    with (
        patch(
            "app.compliance.services.response_service.is_response_approved",
            new=AsyncMock(return_value=True),
        ),
        patch("app.compliance.services.notice_service.log_activity"),
        patch("app.compliance.services.notice_service.log_audit_event_strict"),
    ):
        await transition_notice_status(
            db, notice.id, NoticeStatus.SUBMITTED, user
        )

    # Notice mutated to submitted (the service mutates in-place)
    assert notice.status == "submitted"


async def test_transition_to_resolved_does_not_check_response():
    """Only `submitted` triggers the gate — `resolved` and `dismissed`
    don't require response approval."""
    from app.compliance.services.notice_service import transition_notice_status
    from app.compliance.services.notice_state_machine import NoticeStatus

    notice = MagicMock()
    notice.id = 42
    notice.client_id = 5
    notice.status = "submitted"  # already submitted, transitioning to resolved
    notice.assigned_user_id = None
    notice.response_deadline = None
    notice.parent_notice_id = None
    db = _patched_db_returning(notice)
    user = MagicMock(id=1, role="admin")

    # is_response_approved should NOT be called for resolved transitions.
    with (
        patch(
            "app.compliance.services.response_service.is_response_approved",
            new=AsyncMock(),
        ) as mock_check,
        patch("app.compliance.services.notice_service.log_activity"),
        patch("app.compliance.services.notice_service.log_audit_event_strict"),
    ):
        await transition_notice_status(
            db, notice.id, NoticeStatus.RESOLVED, user
        )
        mock_check.assert_not_called()


async def test_idempotent_submitted_to_submitted_no_check():
    """A no-op transition (submitted → submitted) shouldn't re-check the
    approval gate. The early-return condition `old_status != SUBMITTED`
    handles this."""
    from app.compliance.services.notice_service import transition_notice_status
    from app.compliance.services.notice_state_machine import (
        InvalidTransitionError, NoticeStatus,
    )

    notice = MagicMock()
    notice.id = 42
    notice.client_id = 5
    notice.status = "submitted"
    db = _patched_db_returning(notice)
    user = MagicMock(id=1, role="admin")

    # ALLOWED_TRANSITIONS may not allow submitted → submitted, in which case
    # validate_transition raises before our gate. Either way, our gate
    # must not be the source of the error.
    with patch(
        "app.compliance.services.response_service.is_response_approved",
        new=AsyncMock(),
    ) as mock_check:
        try:
            await transition_notice_status(
                db, notice.id, NoticeStatus.SUBMITTED, user
            )
        except InvalidTransitionError as e:
            # Acceptable — but the error must come from validate_transition,
            # NOT from the response-not-approved gate.
            assert "response is not approved" not in str(e).lower()
        # is_response_approved should not have been called (early-skip).
        mock_check.assert_not_called()
