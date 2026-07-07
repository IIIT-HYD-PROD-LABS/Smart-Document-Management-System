"""Phase 12 response_service unit tests — AsyncMock for the AsyncSession."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.compliance.services.response_service import (
    SegregationOfDutiesError,
    apply_approval,
    submit_for_review,
    withdraw,
)
from app.compliance.services.response_state_machine import (
    ApprovalStage,
    InvalidResponseTransitionError,
)


def _make_response(status: str = "draft", created_by_user_id: int = 7):
    r = MagicMock()
    r.id = 1
    r.notice_id = 10
    r.client_id = 5
    r.status = status
    r.current_version_id = 100
    # Draft author distinct from the approver actors used below (42) so the
    # R1 segregation-of-duties guard does not trip on the happy path.
    r.created_by_user_id = created_by_user_id
    return r


def _async_db():
    db = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _db_returning(*values):
    """AsyncMock db.execute() yielding successive `.scalar_one_or_none()`
    results, one per call, in the order apply_approval issues them: R3
    FOR-UPDATE re-select, R1.1b version-author lookup, R1.2 prior-approval
    lookup."""
    results = []
    for v in values:
        result = MagicMock()
        result.scalar_one_or_none.return_value = v
        results.append(result)
    db = _async_db()
    db.execute = AsyncMock(side_effect=results)
    return db


def _approval_db(response):
    """AsyncMock DB wired for apply_approval's R3 re-select + R1 prior-approval
    lookups: the FOR UPDATE re-select returns the same response object; the
    version-author and prior-approval lookups return None (actor is clean)."""
    return _db_returning(response, None, None)


async def test_submit_for_review_from_draft_sets_reviewer_pending():
    r = _make_response("draft")
    db = _async_db()
    with patch("app.compliance.services.response_service.log_activity"), \
         patch("app.compliance.services.response_service.log_audit_event"):
        await submit_for_review(db, response=r, user_id=42)
    assert r.status == "reviewer_pending"


async def test_submit_for_review_from_pending_raises():
    r = _make_response("reviewer_pending")
    db = _async_db()
    with pytest.raises(InvalidResponseTransitionError):
        await submit_for_review(db, response=r, user_id=42)


async def test_withdraw_from_pending_works():
    r = _make_response("legal_pending")
    db = _async_db()
    with patch("app.compliance.services.response_service.log_activity"), \
         patch("app.compliance.services.response_service.log_audit_event"):
        await withdraw(db, response=r, user_id=42)
    assert r.status == "withdrawn"


async def test_withdraw_from_terminal_raises():
    r = _make_response("approved")
    db = _async_db()
    with pytest.raises(InvalidResponseTransitionError):
        await withdraw(db, response=r, user_id=42)


async def test_apply_approval_reviewer_advances_to_legal():
    r = _make_response("reviewer_pending")
    db = _approval_db(r)
    with patch("app.compliance.services.response_service.log_activity"), \
         patch("app.compliance.services.response_service.log_audit_event"):
        await apply_approval(
            db, response=r, stage=ApprovalStage.REVIEWER,
            decision="approved", user_id=42,
        )
    assert r.status == "legal_pending"


async def test_apply_approval_cfo_marks_approved():
    r = _make_response("cfo_pending")
    db = _approval_db(r)
    with patch("app.compliance.services.response_service.log_activity"), \
         patch("app.compliance.services.response_service.log_audit_event"):
        await apply_approval(
            db, response=r, stage=ApprovalStage.CFO,
            decision="approved", user_id=42,
        )
    assert r.status == "approved"


async def test_apply_approval_legal_reject_returns_to_reviewer():
    """Per RESEARCH-FINAL §2 — Legal rejection sends back ONE stage (to
    reviewer_pending), not all the way to draft."""
    r = _make_response("legal_pending")
    db = _approval_db(r)
    with patch("app.compliance.services.response_service.log_activity"), \
         patch("app.compliance.services.response_service.log_audit_event"):
        await apply_approval(
            db, response=r, stage=ApprovalStage.LEGAL,
            decision="rejected", user_id=42, reason="missing exhibit B",
        )
    assert r.status == "reviewer_pending"


async def test_apply_approval_stage_mismatch_raises():
    """Caller passes wrong stage for the response's current pending status."""
    r = _make_response("reviewer_pending")
    db = _approval_db(r)
    with pytest.raises(InvalidResponseTransitionError):
        await apply_approval(
            db, response=r, stage=ApprovalStage.LEGAL,
            decision="approved", user_id=42,
        )


async def test_apply_approval_from_terminal_raises():
    r = _make_response("approved")
    db = _approval_db(r)
    with pytest.raises(InvalidResponseTransitionError):
        await apply_approval(
            db, response=r, stage=ApprovalStage.CFO,
            decision="approved", user_id=42,
        )


async def test_apply_approval_invalid_decision_raises():
    r = _make_response("reviewer_pending")
    db = _approval_db(r)
    with pytest.raises(ValueError):
        await apply_approval(
            db, response=r, stage=ApprovalStage.REVIEWER,
            decision="maybe", user_id=42,
        )


async def test_apply_approval_author_cannot_approve_own_draft():
    """R1.1 — segregation of duties: the drafter may not approve their own
    response, even if their role holds the stage permission."""
    r = _make_response("reviewer_pending", created_by_user_id=42)
    db = _approval_db(r)
    with pytest.raises(SegregationOfDutiesError):
        await apply_approval(
            db, response=r, stage=ApprovalStage.REVIEWER,
            decision="approved", user_id=42,
        )


async def test_apply_approval_same_actor_cannot_approve_two_stages():
    """R1.2 — an actor who already approved a prior stage of this version
    cannot approve a later stage."""
    r = _make_response("legal_pending", created_by_user_id=7)
    # apply_approval issues three queries: the R3 FOR-UPDATE re-select, then
    # the R1.1b version-author lookup (no version authored by this actor ->
    # None), then the R1.2 prior-approval lookup (a row by user 42 -> SoD
    # violation).
    db = _db_returning(
        r, None, MagicMock(actor_user_id=42, version_id=r.current_version_id),
    )
    with pytest.raises(SegregationOfDutiesError):
        await apply_approval(
            db, response=r, stage=ApprovalStage.LEGAL,
            decision="approved", user_id=42,
        )


async def test_apply_approval_version_author_cannot_approve():
    """R1.1b — maker==checker bypass: a user who authored a draft VERSION (but
    is not the response-shell creator and has no prior approval row) must not be
    able to approve. created_by_user_id only records the shell creator, so this
    is the guard that closes the two-drafter collusion gap."""
    r = _make_response("reviewer_pending", created_by_user_id=7)
    # R3 FOR-UPDATE re-select returns the response; the R1.1b version-author
    # lookup finds a version authored by the approver (user 42).
    db = _db_returning(r, MagicMock(id=555))
    with pytest.raises(SegregationOfDutiesError):
        await apply_approval(
            db, response=r, stage=ApprovalStage.REVIEWER,
            decision="approved", user_id=42,
        )
