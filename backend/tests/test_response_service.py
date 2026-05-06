"""Phase 12 response_service unit tests — uses MagicMock for DB."""
from unittest.mock import MagicMock, patch

import pytest

from app.compliance.services.response_service import (
    apply_approval,
    submit_for_review,
    withdraw,
)
from app.compliance.services.response_state_machine import (
    ApprovalStage,
    InvalidResponseTransitionError,
)


def _make_response(status: str = "draft"):
    r = MagicMock()
    r.id = 1
    r.notice_id = 10
    r.client_id = 5
    r.status = status
    r.current_version_id = 100
    return r


def test_submit_for_review_from_draft_sets_reviewer_pending():
    r = _make_response("draft")
    db = MagicMock()
    with patch("app.compliance.services.response_service.log_activity"), \
         patch("app.compliance.services.response_service.log_audit_event"):
        result = submit_for_review(db, response=r, user_id=42)
    assert r.status == "reviewer_pending"


def test_submit_for_review_from_pending_raises():
    r = _make_response("reviewer_pending")
    db = MagicMock()
    with pytest.raises(InvalidResponseTransitionError):
        submit_for_review(db, response=r, user_id=42)


def test_withdraw_from_pending_works():
    r = _make_response("legal_pending")
    db = MagicMock()
    with patch("app.compliance.services.response_service.log_activity"), \
         patch("app.compliance.services.response_service.log_audit_event"):
        withdraw(db, response=r, user_id=42)
    assert r.status == "withdrawn"


def test_withdraw_from_terminal_raises():
    r = _make_response("approved")
    db = MagicMock()
    with pytest.raises(InvalidResponseTransitionError):
        withdraw(db, response=r, user_id=42)


def test_apply_approval_reviewer_advances_to_legal():
    r = _make_response("reviewer_pending")
    db = MagicMock()
    with patch("app.compliance.services.response_service.log_activity"), \
         patch("app.compliance.services.response_service.log_audit_event"):
        apply_approval(
            db, response=r, stage=ApprovalStage.REVIEWER,
            decision="approved", user_id=42,
        )
    assert r.status == "legal_pending"


def test_apply_approval_cfo_marks_approved():
    r = _make_response("cfo_pending")
    db = MagicMock()
    with patch("app.compliance.services.response_service.log_activity"), \
         patch("app.compliance.services.response_service.log_audit_event"):
        apply_approval(
            db, response=r, stage=ApprovalStage.CFO,
            decision="approved", user_id=42,
        )
    assert r.status == "approved"


def test_apply_approval_legal_reject_returns_to_reviewer():
    """Per RESEARCH-FINAL §2 — Legal rejection sends back ONE stage (to
    reviewer_pending), not all the way to draft."""
    r = _make_response("legal_pending")
    db = MagicMock()
    with patch("app.compliance.services.response_service.log_activity"), \
         patch("app.compliance.services.response_service.log_audit_event"):
        apply_approval(
            db, response=r, stage=ApprovalStage.LEGAL,
            decision="rejected", user_id=42, reason="missing exhibit B",
        )
    assert r.status == "reviewer_pending"


def test_apply_approval_stage_mismatch_raises():
    """Caller passes wrong stage for the response's current pending status."""
    r = _make_response("reviewer_pending")
    db = MagicMock()
    with pytest.raises(InvalidResponseTransitionError):
        apply_approval(
            db, response=r, stage=ApprovalStage.LEGAL,
            decision="approved", user_id=42,
        )


def test_apply_approval_from_terminal_raises():
    r = _make_response("approved")
    db = MagicMock()
    with pytest.raises(InvalidResponseTransitionError):
        apply_approval(
            db, response=r, stage=ApprovalStage.CFO,
            decision="approved", user_id=42,
        )


def test_apply_approval_invalid_decision_raises():
    r = _make_response("reviewer_pending")
    db = MagicMock()
    with pytest.raises(ValueError):
        apply_approval(
            db, response=r, stage=ApprovalStage.REVIEWER,
            decision="maybe", user_id=42,
        )
