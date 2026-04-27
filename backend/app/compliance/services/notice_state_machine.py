"""Notice status state machine — Phase 9 LIFE-04 / D-03.

Hand-rolled dict (per RESEARCH recommendation — 5 states is below the
threshold where `transitions==0.9.3` library adds value). Workflow:

  Received -> Under Review -> Response Drafted -> Submitted -> Resolved
                                                              -> Dismissed (terminal)
                              -> Under Review (back-edit)
            -> Dismissed (terminal — can dismiss from Received or Under Review)
"""
from enum import Enum


class NoticeStatus(str, Enum):
    RECEIVED = "received"
    UNDER_REVIEW = "under_review"
    RESPONSE_DRAFTED = "response_drafted"
    SUBMITTED = "submitted"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


# CONTEXT D-03 transitions, with back-edit and dismiss-from-anywhere.
ALLOWED_TRANSITIONS: dict[NoticeStatus, frozenset[NoticeStatus]] = {
    NoticeStatus.RECEIVED: frozenset({
        NoticeStatus.UNDER_REVIEW,
        NoticeStatus.DISMISSED,
    }),
    NoticeStatus.UNDER_REVIEW: frozenset({
        NoticeStatus.RESPONSE_DRAFTED,
        NoticeStatus.DISMISSED,
    }),
    NoticeStatus.RESPONSE_DRAFTED: frozenset({
        NoticeStatus.SUBMITTED,
        NoticeStatus.UNDER_REVIEW,  # back-edit
    }),
    NoticeStatus.SUBMITTED: frozenset({
        NoticeStatus.RESOLVED,
        NoticeStatus.UNDER_REVIEW,  # authority requested clarification
    }),
    NoticeStatus.RESOLVED: frozenset(),   # terminal
    NoticeStatus.DISMISSED: frozenset(),  # terminal
}


class InvalidTransitionError(Exception):
    """Raised when a callsite requests a forbidden status transition."""
    pass


def validate_transition(current: NoticeStatus, target: NoticeStatus) -> None:
    """Raises InvalidTransitionError if (current -> target) is not allowed."""
    if target not in ALLOWED_TRANSITIONS[current]:
        allowed = sorted(s.value for s in ALLOWED_TRANSITIONS[current])
        raise InvalidTransitionError(
            f"Cannot transition from {current.value} to {target.value}. "
            f"Allowed: {allowed}"
        )


def is_terminal(status: NoticeStatus) -> bool:
    return len(ALLOWED_TRANSITIONS[status]) == 0
