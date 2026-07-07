"""Phase 12 response service — single point of mutation for response drafts.

Per Phase 9 D-D pattern: routers must NOT update notice_responses or
notice_response_versions directly. All writes go through this module.

Public surface:
  - get_or_create_response(notice) → NoticeResponse
  - update_draft(response, payload, user_id) → NoticeResponseVersion
  - rollback_to_version(response, target_version_id, user_id) → NoticeResponseVersion
  - submit_for_review(response, user_id)
  - withdraw(response, user_id)
  - apply_approval(response, stage, decision, user_id, reason)

Each transition writes:
  1. Optional new version row (for draft updates and rollbacks)
  2. NoticeResponseApproval row (for approve/reject — append-only)
  3. NoticeActivity (mutable user timeline) row
  4. AuditLog (immutable system trail) row

Phase 9 audit immutability + Phase 12 append-only approvals together
ensure every state change is recoverable from the audit + approvals
tables alone, even if the response row is later mutated.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.models.notice import ComplianceNotice
from app.compliance.models.response import (
    NoticeResponse,
    NoticeResponseApproval,
    NoticeResponseVersion,
)
from app.compliance.services.activity_service import log_activity
from app.compliance.services.response_state_machine import (
    ApprovalStage,
    InvalidResponseTransitionError,
    PENDING_STAGE_FOR_STATUS,
    ResponseStatus,
    can_edit_draft,
    can_submit_for_review,
    can_withdraw,
    status_after_approve,
    status_after_reject,
)
from app.services.audit_service import log_audit_event_strict as log_audit_event


class SegregationOfDutiesError(PermissionError):
    """R1 — the actor is not permitted to approve this response because they
    authored the draft or already approved a prior stage of this version.
    Routers map this to HTTP 403."""


async def _next_version_no(db: AsyncSession, response_id: int) -> int:
    """Return the next sequential version_no for a response."""
    max_no = (
        await db.execute(
            select(func.max(NoticeResponseVersion.version_no)).where(
                NoticeResponseVersion.response_id == response_id
            )
        )
    ).scalar_one_or_none()
    return (max_no or 0) + 1


async def get_or_create_response(
    db: AsyncSession, *, notice: ComplianceNotice, user_id: Optional[int]
) -> NoticeResponse:
    """Return existing response for the notice or create an empty draft."""
    existing = (
        await db.execute(
            select(NoticeResponse).where(NoticeResponse.notice_id == notice.id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    resp = NoticeResponse(
        notice_id=notice.id,
        client_id=notice.client_id,
        status=ResponseStatus.DRAFT.value,
        created_by_user_id=user_id,
    )
    db.add(resp)
    await db.flush()  # need resp.id before creating version

    # Seed initial empty version so callers always have current_version
    v0 = NoticeResponseVersion(
        response_id=resp.id,
        client_id=notice.client_id,
        version_no=1,
        subject=None,
        body_markdown="",
        recipient=None,
        created_by_user_id=user_id,
    )
    db.add(v0)
    await db.flush()
    resp.current_version_id = v0.id
    await db.commit()
    await db.refresh(resp)

    log_activity(
        db,
        notice_id=notice.id,
        user_id=user_id,
        type="note_added",
        details={"source": "response_workflow", "event": "response_created"},
    )
    await db.commit()

    log_audit_event(
        user_id=user_id,
        action="notice_response_created",
        resource_type="NoticeResponse",
        resource_id=resp.id,
        details={"notice_id": notice.id},
    )
    return resp


async def update_draft(
    db: AsyncSession,
    *,
    response: NoticeResponse,
    payload: dict,
    user_id: Optional[int],
) -> NoticeResponseVersion:
    """Append a new version to the response draft.

    Raises InvalidResponseTransitionError if response is not in draft.
    """
    current_status = ResponseStatus(response.status)
    if not can_edit_draft(current_status):
        raise InvalidResponseTransitionError(
            f"Cannot edit response in status={response.status!r} — only 'draft' is editable"
        )

    version_no = await _next_version_no(db, response.id)
    new_version = NoticeResponseVersion(
        response_id=response.id,
        client_id=response.client_id,
        version_no=version_no,
        subject=payload.get("subject"),
        body_markdown=payload.get("body_markdown", ""),
        recipient=payload.get("recipient"),
        response_date=payload.get("response_date"),
        metadata_json=payload.get("metadata_json"),
        created_by_user_id=user_id,
    )
    db.add(new_version)
    await db.flush()
    response.current_version_id = new_version.id
    await db.commit()
    await db.refresh(new_version)

    log_activity(
        db,
        notice_id=response.notice_id,
        user_id=user_id,
        type="note_added",
        details={
            "source": "response_workflow",
            "event": "version_saved",
            "version_no": version_no,
        },
    )
    await db.commit()

    log_audit_event(
        user_id=user_id,
        action="notice_response_version_saved",
        resource_type="NoticeResponseVersion",
        resource_id=new_version.id,
        details={
            "response_id": response.id,
            "notice_id": response.notice_id,
            "version_no": version_no,
        },
    )
    return new_version


async def rollback_to_version(
    db: AsyncSession,
    *,
    response: NoticeResponse,
    target_version_id: int,
    user_id: Optional[int],
) -> NoticeResponseVersion:
    """Create a new version that copies content from `target_version_id`.

    Per RESEARCH-FINAL §3 — never mutate an existing version row.
    """
    # Re-read the row under a write lock so the can_edit_draft check below
    # cannot race with submit_for_review changing the status concurrently.
    locked = (
        await db.execute(
            select(NoticeResponse)
            .where(NoticeResponse.id == response.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if locked is not None:
        response = locked

    current_status = ResponseStatus(response.status)
    if not can_edit_draft(current_status):
        raise InvalidResponseTransitionError(
            f"Cannot rollback in status={response.status!r}; revert to draft via withdraw first"
        )

    target = await db.get(NoticeResponseVersion, target_version_id)
    if target is None or target.response_id != response.id:
        raise ValueError(f"Version {target_version_id} not found for response {response.id}")

    version_no = await _next_version_no(db, response.id)
    new_version = NoticeResponseVersion(
        response_id=response.id,
        client_id=response.client_id,
        version_no=version_no,
        subject=target.subject,
        body_markdown=target.body_markdown,
        recipient=target.recipient,
        response_date=target.response_date,
        metadata_json=target.metadata_json,
        rolled_back_from_version_id=target.id,
        created_by_user_id=user_id,
    )
    db.add(new_version)
    await db.flush()
    response.current_version_id = new_version.id
    await db.commit()
    await db.refresh(new_version)

    log_activity(
        db,
        notice_id=response.notice_id,
        user_id=user_id,
        type="note_added",
        details={
            "source": "response_workflow",
            "event": "rolled_back",
            "from_version_id": target.id,
            "from_version_no": target.version_no,
            "new_version_no": version_no,
        },
    )
    await db.commit()

    log_audit_event(
        user_id=user_id,
        action="notice_response_rolled_back",
        resource_type="NoticeResponseVersion",
        resource_id=new_version.id,
        details={
            "response_id": response.id,
            "from_version_id": target.id,
            "to_version_id": new_version.id,
        },
    )
    return new_version


async def submit_for_review(
    db: AsyncSession, *, response: NoticeResponse, user_id: Optional[int]
) -> NoticeResponse:
    current = ResponseStatus(response.status)
    if not can_submit_for_review(current):
        raise InvalidResponseTransitionError(
            f"Cannot submit response in status={response.status!r}; only 'draft' may be submitted"
        )
    response.status = ResponseStatus.REVIEWER_PENDING.value
    await db.commit()
    await db.refresh(response)

    log_activity(
        db,
        notice_id=response.notice_id,
        user_id=user_id,
        type="note_added",
        details={
            "source": "response_workflow",
            "event": "submitted_for_review",
        },
    )
    await db.commit()

    log_audit_event(
        user_id=user_id,
        action="notice_response_submitted",
        resource_type="NoticeResponse",
        resource_id=response.id,
        details={
            "before_value": "draft",
            "after_value": ResponseStatus.REVIEWER_PENDING.value,
        },
    )
    return response


async def withdraw(
    db: AsyncSession, *, response: NoticeResponse, user_id: Optional[int]
) -> NoticeResponse:
    current = ResponseStatus(response.status)
    if not can_withdraw(current):
        raise InvalidResponseTransitionError(
            f"Cannot withdraw response in status={response.status!r}"
        )
    before = response.status
    response.status = ResponseStatus.WITHDRAWN.value
    await db.commit()
    await db.refresh(response)

    log_activity(
        db,
        notice_id=response.notice_id,
        user_id=user_id,
        type="note_added",
        details={"source": "response_workflow", "event": "withdrawn"},
    )
    await db.commit()

    log_audit_event(
        user_id=user_id,
        action="notice_response_withdrawn",
        resource_type="NoticeResponse",
        resource_id=response.id,
        details={"before_value": before, "after_value": "withdrawn"},
    )
    return response


async def apply_approval(
    db: AsyncSession,
    *,
    response: NoticeResponse,
    stage: ApprovalStage,
    decision: str,
    user_id: Optional[int],
    reason: Optional[str] = None,
) -> NoticeResponseApproval:
    """Apply an approve/reject decision at the given stage.

    Enforces that the stage matches the response's current pending status —
    e.g., calling apply_approval(stage=LEGAL) when status='reviewer_pending'
    raises InvalidResponseTransitionError.

    R1 — segregation of duties: the draft author may not approve their own
    response, and no single actor may act on more than one stage of the
    same response version. Violations raise SegregationOfDutiesError (403).

    R3 — the response row is re-selected FOR UPDATE and its status
    re-validated against the value seen by the caller, so two concurrent
    approvers cannot both advance the same pending stage (compare-and-set).
    """
    if decision not in ("approved", "rejected"):
        raise ValueError(f"decision must be 'approved' or 'rejected', got {decision!r}")

    # R3 — re-read the row under a write lock so the status check below acts
    # as a compare-and-set: a racing approval on the same stage must wait,
    # then fail the stage/status validation instead of double-advancing.
    locked = (
        await db.execute(
            select(NoticeResponse)
            .where(NoticeResponse.id == response.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if locked is not None:
        response = locked

    # R1.1 — the drafter cannot approve/reject their own response.
    # Fail-closed on unknown author: block when the author is unknown OR is
    # the same actor, so a NULL created_by_user_id cannot bypass the guard.
    if user_id is not None and (
        response.created_by_user_id is None
        or user_id == response.created_by_user_id
    ):
        raise SegregationOfDutiesError(
            "The author of a response draft cannot approve or reject it "
            "(segregation of duties)."
        )

    # R1.1b — a user who AUTHORED any version of this response's draft cannot
    # approve it. response.created_by_user_id only records the response-shell
    # creator; the substantive reply text is authored on NoticeResponseVersion
    # (update_draft / rollback). Without this guard a second drafter who wrote
    # the body — but never created the shell and never approved a prior stage —
    # could approve their own content (maker == checker bypass).
    if user_id is not None:
        authored_version = (
            await db.execute(
                select(NoticeResponseVersion.id).where(
                    NoticeResponseVersion.response_id == response.id,
                    NoticeResponseVersion.created_by_user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if authored_version is not None:
            raise SegregationOfDutiesError(
                "A user who authored any version of this response draft "
                "cannot approve or reject it (segregation of duties)."
            )

    current = ResponseStatus(response.status)
    expected_stage = PENDING_STAGE_FOR_STATUS.get(current)
    if expected_stage is None:
        raise InvalidResponseTransitionError(
            f"Response in status={response.status!r} is not awaiting approval"
        )
    if expected_stage != stage:
        raise InvalidResponseTransitionError(
            f"Stage mismatch — response awaits {expected_stage.value!r}, "
            f"caller passed {stage.value!r}"
        )

    # R1.2 — this actor must not already have acted on a prior stage of the
    # current version. Approvals are append-only per version, so one prior
    # row by this actor is enough to disqualify them from a second stage.
    if user_id is not None:
        prior = (
            await db.execute(
                select(NoticeResponseApproval).where(
                    NoticeResponseApproval.response_id == response.id,
                    NoticeResponseApproval.version_id == response.current_version_id,
                    NoticeResponseApproval.actor_user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if prior is not None:
            raise SegregationOfDutiesError(
                "This user already approved a prior stage of this response "
                "version; a different approver is required for each stage "
                "(segregation of duties)."
            )

    if decision == "approved":
        next_status = status_after_approve(current, stage)
    else:
        next_status = status_after_reject(current, stage)

    before_status = response.status

    approval = NoticeResponseApproval(
        response_id=response.id,
        version_id=response.current_version_id,
        client_id=response.client_id,
        stage=stage.value,
        decision=decision,
        actor_user_id=user_id,
        reason=reason,
    )
    db.add(approval)
    response.status = next_status.value
    await db.commit()
    await db.refresh(approval)
    await db.refresh(response)

    log_activity(
        db,
        notice_id=response.notice_id,
        user_id=user_id,
        type="note_added",
        details={
            "source": "response_workflow",
            "event": "approval",
            "stage": stage.value,
            "decision": decision,
            "before_status": before_status,
            "after_status": next_status.value,
            "reason": reason,
        },
    )
    await db.commit()

    log_audit_event(
        user_id=user_id,
        action="notice_response_approval",
        resource_type="NoticeResponseApproval",
        resource_id=approval.id,
        details={
            "response_id": response.id,
            "notice_id": response.notice_id,
            "stage": stage.value,
            "decision": decision,
            "before_status": before_status,
            "after_status": next_status.value,
            "reason": reason,
        },
    )

    return approval


async def is_response_approved(
    db: AsyncSession, *, notice_id: int, lock_for_update: bool = False
) -> bool:
    """Returns True iff the notice has an approved response.

    Phase 9 transition_notice_status will gate `submitted` on this.

    H-D second hardening: callers running inside a notice-transition
    transaction (which holds FOR UPDATE on `compliance_notices`) MUST pass
    `lock_for_update=True`. That acquires FOR UPDATE on `notice_responses`
    too, closing the TOCTOU window where a CFO approval/rejection could
    race with the notice transition. Without the lock, the transition's
    SELECT can see `cfo_pending` while a concurrent approval flips the
    response to `approved` (causing spurious 422), or vice-versa
    (allowing a notice to transition to submitted with a since-rejected
    response).
    """
    q = select(NoticeResponse).where(NoticeResponse.notice_id == notice_id)
    if lock_for_update:
        q = q.with_for_update()
    resp = (await db.execute(q)).scalar_one_or_none()
    return resp is not None and resp.status == ResponseStatus.APPROVED.value
