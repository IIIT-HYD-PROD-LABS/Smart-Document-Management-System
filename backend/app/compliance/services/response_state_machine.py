"""Phase 12 response approval state machine — RESEARCH-FINAL §2.

The 4-stage chain Drafter → Reviewer → Legal → CFO is hardcoded for v2.0;
per-client overrides via config_overrides land in v2.1.

submit_for_review : draft           → reviewer_pending
approve(reviewer) : reviewer_pending → legal_pending
reject(reviewer)  : reviewer_pending → draft         (back to drafter)
approve(legal)    : legal_pending    → cfo_pending
reject(legal)     : legal_pending    → reviewer_pending  (one stage back)
approve(cfo)      : cfo_pending      → approved
reject(cfo)       : cfo_pending      → legal_pending     (one stage back)
withdraw          : any non-approved → withdrawn       (drafter only)

Reject semantics: rejection from Legal/CFO sends the response back ONE
stage (not all the way to draft) — matches CA-firm practice where a
rejection means "send back for rework at the previous gate" rather than
"start over."
"""
from enum import Enum


class ResponseStatus(str, Enum):
    DRAFT = "draft"
    REVIEWER_PENDING = "reviewer_pending"
    LEGAL_PENDING = "legal_pending"
    CFO_PENDING = "cfo_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ApprovalStage(str, Enum):
    REVIEWER = "reviewer"
    LEGAL = "legal"
    CFO = "cfo"


# Stage that gates each pending status (same shape but lets callers
# answer "which stage am I waiting on?" without parsing strings).
PENDING_STAGE_FOR_STATUS = {
    ResponseStatus.REVIEWER_PENDING: ApprovalStage.REVIEWER,
    ResponseStatus.LEGAL_PENDING: ApprovalStage.LEGAL,
    ResponseStatus.CFO_PENDING: ApprovalStage.CFO,
}


# Forward transition: status + stage approve → next status
APPROVE_TRANSITIONS = {
    (ResponseStatus.REVIEWER_PENDING, ApprovalStage.REVIEWER): ResponseStatus.LEGAL_PENDING,
    (ResponseStatus.LEGAL_PENDING, ApprovalStage.LEGAL): ResponseStatus.CFO_PENDING,
    (ResponseStatus.CFO_PENDING, ApprovalStage.CFO): ResponseStatus.APPROVED,
}


# Reject transition: status + stage reject → status sent back to
REJECT_TRANSITIONS = {
    (ResponseStatus.REVIEWER_PENDING, ApprovalStage.REVIEWER): ResponseStatus.DRAFT,
    (ResponseStatus.LEGAL_PENDING, ApprovalStage.LEGAL): ResponseStatus.REVIEWER_PENDING,
    (ResponseStatus.CFO_PENDING, ApprovalStage.CFO): ResponseStatus.LEGAL_PENDING,
}


class InvalidResponseTransitionError(ValueError):
    """Raised when caller attempts an illegal status/stage combination."""


def status_after_approve(
    current: ResponseStatus, stage: ApprovalStage
) -> ResponseStatus:
    """Returns the resulting status when `stage` approves a response in
    state `current`. Raises InvalidResponseTransitionError on a wrong-stage
    or wrong-status combination."""
    target = APPROVE_TRANSITIONS.get((current, stage))
    if target is None:
        raise InvalidResponseTransitionError(
            f"Cannot approve at stage={stage.value!r} when status={current.value!r}"
        )
    return target


def status_after_reject(
    current: ResponseStatus, stage: ApprovalStage
) -> ResponseStatus:
    """Returns the resulting status when `stage` rejects a response in
    state `current`. Raises on wrong-stage / wrong-status."""
    target = REJECT_TRANSITIONS.get((current, stage))
    if target is None:
        raise InvalidResponseTransitionError(
            f"Cannot reject at stage={stage.value!r} when status={current.value!r}"
        )
    return target


def can_submit_for_review(current: ResponseStatus) -> bool:
    """Drafter can submit only from draft."""
    return current == ResponseStatus.DRAFT


def can_withdraw(current: ResponseStatus) -> bool:
    """Drafter can withdraw any non-approved, non-rejected, non-already-withdrawn response."""
    return current not in (
        ResponseStatus.APPROVED,
        ResponseStatus.REJECTED,
        ResponseStatus.WITHDRAWN,
    )


def can_edit_draft(current: ResponseStatus) -> bool:
    """Drafter can edit only while in draft status (after submission, edits
    require a reject-and-resubmit cycle)."""
    return current == ResponseStatus.DRAFT


def is_terminal(current: ResponseStatus) -> bool:
    return current in (
        ResponseStatus.APPROVED,
        ResponseStatus.REJECTED,
        ResponseStatus.WITHDRAWN,
    )
