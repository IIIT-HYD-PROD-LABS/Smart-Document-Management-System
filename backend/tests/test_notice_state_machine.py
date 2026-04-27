"""LIFE-04: Notice status state machine — pure dict-level transitions."""

import pytest


def test_received_to_under_review_allowed():
    from app.compliance.services.notice_state_machine import (
        NoticeStatus,
        validate_transition,
    )
    # No exception when transition is allowed
    validate_transition(NoticeStatus.RECEIVED, NoticeStatus.UNDER_REVIEW)


def test_received_to_submitted_blocked():
    from app.compliance.services.notice_state_machine import (
        InvalidTransitionError,
        NoticeStatus,
        validate_transition,
    )
    with pytest.raises(InvalidTransitionError):
        validate_transition(NoticeStatus.RECEIVED, NoticeStatus.SUBMITTED)


def test_terminal_states_have_no_transitions():
    from app.compliance.services.notice_state_machine import (
        ALLOWED_TRANSITIONS,
        NoticeStatus,
    )
    assert ALLOWED_TRANSITIONS[NoticeStatus.RESOLVED] == frozenset()
    assert ALLOWED_TRANSITIONS[NoticeStatus.DISMISSED] == frozenset()
