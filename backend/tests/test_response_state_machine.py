"""Phase 12 response state machine — pure-Python tests.

Covers the 4-stage Drafter → Reviewer → Legal → CFO chain plus
withdraw/rollback contracts. No DB needed."""
import pytest

from app.compliance.services.response_state_machine import (
    APPROVE_TRANSITIONS,
    ApprovalStage,
    InvalidResponseTransitionError,
    PENDING_STAGE_FOR_STATUS,
    REJECT_TRANSITIONS,
    ResponseStatus,
    can_edit_draft,
    can_submit_for_review,
    can_withdraw,
    is_terminal,
    status_after_approve,
    status_after_reject,
)


def test_approve_chain_drafter_to_cfo():
    """Walk the full happy path through every stage."""
    assert status_after_approve(
        ResponseStatus.REVIEWER_PENDING, ApprovalStage.REVIEWER
    ) == ResponseStatus.LEGAL_PENDING
    assert status_after_approve(
        ResponseStatus.LEGAL_PENDING, ApprovalStage.LEGAL
    ) == ResponseStatus.CFO_PENDING
    assert status_after_approve(
        ResponseStatus.CFO_PENDING, ApprovalStage.CFO
    ) == ResponseStatus.APPROVED


def test_reject_at_reviewer_returns_to_draft():
    """Reviewer rejection is the only one that goes all the way back to draft."""
    assert status_after_reject(
        ResponseStatus.REVIEWER_PENDING, ApprovalStage.REVIEWER
    ) == ResponseStatus.DRAFT


def test_reject_at_legal_returns_one_stage():
    """Per RESEARCH-FINAL §2: reject at legal sends back to reviewer, not all the way."""
    assert status_after_reject(
        ResponseStatus.LEGAL_PENDING, ApprovalStage.LEGAL
    ) == ResponseStatus.REVIEWER_PENDING


def test_reject_at_cfo_returns_one_stage():
    assert status_after_reject(
        ResponseStatus.CFO_PENDING, ApprovalStage.CFO
    ) == ResponseStatus.LEGAL_PENDING


def test_approve_wrong_stage_raises():
    """Stage must match the pending status — Legal can't approve while
    response is reviewer_pending."""
    with pytest.raises(InvalidResponseTransitionError):
        status_after_approve(
            ResponseStatus.REVIEWER_PENDING, ApprovalStage.LEGAL
        )
    with pytest.raises(InvalidResponseTransitionError):
        status_after_approve(
            ResponseStatus.CFO_PENDING, ApprovalStage.LEGAL
        )


def test_approve_wrong_status_raises():
    """Can't approve from draft or terminal states."""
    with pytest.raises(InvalidResponseTransitionError):
        status_after_approve(
            ResponseStatus.DRAFT, ApprovalStage.REVIEWER
        )
    with pytest.raises(InvalidResponseTransitionError):
        status_after_approve(
            ResponseStatus.APPROVED, ApprovalStage.CFO
        )


def test_can_submit_only_from_draft():
    assert can_submit_for_review(ResponseStatus.DRAFT) is True
    assert can_submit_for_review(ResponseStatus.REVIEWER_PENDING) is False
    assert can_submit_for_review(ResponseStatus.APPROVED) is False


def test_can_withdraw_excludes_terminal():
    """Withdraw allowed from draft + any pending state, but not from
    approved/rejected/already-withdrawn."""
    assert can_withdraw(ResponseStatus.DRAFT) is True
    assert can_withdraw(ResponseStatus.REVIEWER_PENDING) is True
    assert can_withdraw(ResponseStatus.LEGAL_PENDING) is True
    assert can_withdraw(ResponseStatus.CFO_PENDING) is True
    assert can_withdraw(ResponseStatus.APPROVED) is False
    assert can_withdraw(ResponseStatus.REJECTED) is False
    assert can_withdraw(ResponseStatus.WITHDRAWN) is False


def test_can_edit_only_in_draft():
    """Once submitted, the draft is frozen — edits require reject-and-resubmit."""
    assert can_edit_draft(ResponseStatus.DRAFT) is True
    assert can_edit_draft(ResponseStatus.REVIEWER_PENDING) is False
    assert can_edit_draft(ResponseStatus.APPROVED) is False


def test_terminal_states():
    assert is_terminal(ResponseStatus.APPROVED) is True
    assert is_terminal(ResponseStatus.REJECTED) is True
    assert is_terminal(ResponseStatus.WITHDRAWN) is True
    assert is_terminal(ResponseStatus.DRAFT) is False
    assert is_terminal(ResponseStatus.REVIEWER_PENDING) is False


def test_transition_tables_complete():
    """Sanity guard: every pending status has both an approve and reject
    transition. PENDING_STAGE_FOR_STATUS must cover the same domain."""
    pending_statuses = {
        ResponseStatus.REVIEWER_PENDING,
        ResponseStatus.LEGAL_PENDING,
        ResponseStatus.CFO_PENDING,
    }
    approve_keys = {s for (s, _) in APPROVE_TRANSITIONS.keys()}
    reject_keys = {s for (s, _) in REJECT_TRANSITIONS.keys()}
    assert approve_keys == pending_statuses
    assert reject_keys == pending_statuses
    assert set(PENDING_STAGE_FOR_STATUS.keys()) == pending_statuses
