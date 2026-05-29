"""Phase 12 response router — draft / version / approval / evidence.

Endpoints under /api/compliance/notices/{notice_id} (mounted in main.py):

  GET    /responses                   NOTICE_VIEW             current response + history
  POST   /responses                   NOTICE_DRAFT_RESPONSE   create or update draft (idempotent)
  PATCH  /responses                   NOTICE_DRAFT_RESPONSE   append a new version
  POST   /responses/submit            NOTICE_DRAFT_RESPONSE   draft → reviewer_pending
  POST   /responses/withdraw          NOTICE_DRAFT_RESPONSE   any non-terminal → withdrawn
  POST   /responses/rollback          NOTICE_DRAFT_RESPONSE   rollback to a prior version
  POST   /responses/approve           (per-stage permission)  approve current pending stage
  POST   /responses/reject            (per-stage permission)  reject current pending stage

  GET    /evidence                    NOTICE_VIEW             list attached documents
  POST   /evidence                    NOTICE_ATTACH_EVIDENCE  attach a Document
  DELETE /evidence/{document_id}      NOTICE_ATTACH_EVIDENCE  detach a Document

Per-stage approve/reject permission mapping:
  reviewer → NOTICE_APPROVE
  legal    → NOTICE_APPROVE_LEGAL
  cfo      → NOTICE_APPROVE_CFO
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.compliance.dependencies import (
    require_any_compliance_permission,
    require_compliance_permission,
)
from app.compliance.models.membership import ClientMembership
from app.compliance.models.notice import ComplianceNotice
from app.compliance.models.response import (
    NoticeResponse,
    NoticeResponseApproval,
    NoticeResponseVersion,
)
from app.compliance.schemas.response import (
    ApprovalActionRequest,
    EvidenceAttachOut,
    EvidenceAttachRequest,
    ResponseApprovalOut,
    ResponseDetailOut,
    ResponseDraftPayload,
    ResponseOut,
    ResponseRollbackRequest,
    ResponseVersionOut,
)
from app.compliance.services.evidence_service import (
    DocumentAccessDenied,
    attach_document,
    detach_document,
    list_attachments,
)
from app.compliance.services.permission_registry import (
    CompliancePermission,
    ComplianceRole,
    has_permission,
)
from app.compliance.services.response_service import (
    SegregationOfDutiesError,
    apply_approval,
    get_or_create_response,
    rollback_to_version,
    submit_for_review,
    update_draft,
    withdraw,
)
from app.compliance.services.response_state_machine import (
    ApprovalStage,
    InvalidResponseTransitionError,
    PENDING_STAGE_FOR_STATUS,
    ResponseStatus,
)
from app.database import get_db
from app.models.user import User
from app.services.audit_service import log_audit_event
from app.utils.security import get_current_user


router = APIRouter(prefix="/notices/{notice_id}", tags=["compliance-responses"])


def _get_notice(
    db: Session,
    notice_id: int,
    membership: Optional[ClientMembership] = None,
) -> ComplianceNotice:
    """Fetch a notice. Defense in depth: when `membership` is supplied,
    we filter by client_id at the application layer in addition to the
    DB-level RLS enforcement (Phase 9). If RLS is ever misconfigured the
    application filter is the second wall.

    H-B second hardening: prior code relied solely on RLS. Now mirrors
    the notices.py router pattern.
    """
    q = db.query(ComplianceNotice).filter(ComplianceNotice.id == notice_id)
    if membership is not None:
        q = q.filter(ComplianceNotice.client_id == membership.client_id)
    notice = q.first()
    if notice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notice {notice_id} not found",
        )
    return notice


def _build_detail(db: Session, response: NoticeResponse) -> ResponseDetailOut:
    versions = (
        db.query(NoticeResponseVersion)
        .filter(NoticeResponseVersion.response_id == response.id)
        .order_by(NoticeResponseVersion.version_no.desc())
        .all()
    )
    approvals = (
        db.query(NoticeResponseApproval)
        .filter(NoticeResponseApproval.response_id == response.id)
        .order_by(NoticeResponseApproval.created_at.asc())
        .all()
    )
    current_version = response.current_version
    return ResponseDetailOut(
        id=response.id,
        notice_id=response.notice_id,
        client_id=response.client_id,
        status=response.status,  # type: ignore[arg-type]
        current_version_id=response.current_version_id,
        created_by_user_id=response.created_by_user_id,
        created_at=response.created_at,
        updated_at=response.updated_at,
        current_version=(
            ResponseVersionOut.model_validate(current_version)
            if current_version is not None
            else None
        ),
        versions=[ResponseVersionOut.model_validate(v) for v in versions],
        approvals=[ResponseApprovalOut.model_validate(a) for a in approvals],
    )


# ──────────────────────────────────────────────────────────────────────
# Response GET / POST / PATCH
# ──────────────────────────────────────────────────────────────────────

@router.get("/responses", response_model=ResponseDetailOut)
def get_response(
    notice_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    notice = _get_notice(db, notice_id, membership=membership)
    response = (
        db.query(NoticeResponse)
        .filter(NoticeResponse.notice_id == notice.id)
        .filter(NoticeResponse.client_id == membership.client_id)
        .first()
    )
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No response draft yet — POST /responses to create one",
        )
    return _build_detail(db, response)


@router.post("/responses", response_model=ResponseDetailOut)
def create_or_update_draft(
    notice_id: int,
    payload: ResponseDraftPayload,
    current_user: User = Depends(get_current_user),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_DRAFT_RESPONSE)
    ),
    db: Session = Depends(get_db),
):
    """Create the response shell + first version on first call. On
    subsequent calls behaves like PATCH — appends a new version with the
    supplied fields."""
    notice = _get_notice(db, notice_id, membership=membership)
    response = get_or_create_response(db, notice=notice, user_id=current_user.id)

    payload_dict = payload.model_dump(exclude_unset=True)
    if payload_dict:
        try:
            update_draft(
                db,
                response=response,
                payload=payload_dict,
                user_id=current_user.id,
            )
            db.refresh(response)
        except InvalidResponseTransitionError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(e),
            )

    return _build_detail(db, response)


@router.patch("/responses", response_model=ResponseDetailOut)
def update_response_draft(
    notice_id: int,
    payload: ResponseDraftPayload,
    current_user: User = Depends(get_current_user),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_DRAFT_RESPONSE)
    ),
    db: Session = Depends(get_db),
):
    notice = _get_notice(db, notice_id, membership=membership)
    response = (
        db.query(NoticeResponse)
        .filter(NoticeResponse.notice_id == notice.id)
        .filter(NoticeResponse.client_id == membership.client_id)
        .first()
    )
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No response draft to update — POST /responses first",
        )
    try:
        update_draft(
            db,
            response=response,
            payload=payload.model_dump(exclude_unset=True),
            user_id=current_user.id,
        )
        db.refresh(response)
    except InvalidResponseTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        )
    return _build_detail(db, response)


# ──────────────────────────────────────────────────────────────────────
# Workflow actions
# ──────────────────────────────────────────────────────────────────────

@router.post("/responses/submit", response_model=ResponseOut)
def submit_response(
    notice_id: int,
    current_user: User = Depends(get_current_user),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_DRAFT_RESPONSE)
    ),
    db: Session = Depends(get_db),
):
    notice = _get_notice(db, notice_id, membership=membership)
    response = (
        db.query(NoticeResponse)
        .filter(NoticeResponse.notice_id == notice.id)
        .filter(NoticeResponse.client_id == membership.client_id)
        .first()
    )
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No response draft to submit",
        )
    try:
        submit_for_review(db, response=response, user_id=current_user.id)
    except InvalidResponseTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        )
    return ResponseOut.model_validate(response)


@router.post("/responses/withdraw", response_model=ResponseOut)
def withdraw_response(
    notice_id: int,
    current_user: User = Depends(get_current_user),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_DRAFT_RESPONSE)
    ),
    db: Session = Depends(get_db),
):
    notice = _get_notice(db, notice_id, membership=membership)
    response = (
        db.query(NoticeResponse)
        .filter(NoticeResponse.notice_id == notice.id)
        .filter(NoticeResponse.client_id == membership.client_id)
        .first()
    )
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No response to withdraw"
        )
    is_author = response.created_by_user_id == current_user.id
    is_supervisor = membership.compliance_role in (
        ComplianceRole.COMPLIANCE_HEAD.value,
        ComplianceRole.CA_CONSULTANT.value,
    )
    if not (is_author or is_supervisor):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the draft author or a supervisor may withdraw this response",
        )
    try:
        withdraw(db, response=response, user_id=current_user.id)
        if is_supervisor and not is_author:
            log_audit_event(
                user_id=current_user.id,
                action="notice_response_withdraw_override",
                resource_type="NoticeResponse",
                resource_id=response.id,
                details={
                    "override_by_role": membership.compliance_role,
                    "original_author_user_id": response.created_by_user_id,
                },
            )
    except InvalidResponseTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        )
    return ResponseOut.model_validate(response)


@router.post("/responses/rollback", response_model=ResponseDetailOut)
def rollback_response(
    notice_id: int,
    payload: ResponseRollbackRequest,
    current_user: User = Depends(get_current_user),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_DRAFT_RESPONSE)
    ),
    db: Session = Depends(get_db),
):
    notice = _get_notice(db, notice_id, membership=membership)
    response = (
        db.query(NoticeResponse)
        .filter(NoticeResponse.notice_id == notice.id)
        .filter(NoticeResponse.client_id == membership.client_id)
        .first()
    )
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No response to rollback"
        )
    try:
        rollback_to_version(
            db,
            response=response,
            target_version_id=payload.target_version_id,
            user_id=current_user.id,
        )
    except InvalidResponseTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    db.refresh(response)
    return _build_detail(db, response)


# ──────────────────────────────────────────────────────────────────────
# Approval gates
# ──────────────────────────────────────────────────────────────────────

_STAGE_TO_PERMISSION = {
    ApprovalStage.REVIEWER: CompliancePermission.NOTICE_APPROVE,
    ApprovalStage.LEGAL: CompliancePermission.NOTICE_APPROVE_LEGAL,
    ApprovalStage.CFO: CompliancePermission.NOTICE_APPROVE_CFO,
}


def _resolve_pending_stage(response: NoticeResponse) -> ApprovalStage:
    try:
        current = ResponseStatus(response.status)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        )
    stage = PENDING_STAGE_FOR_STATUS.get(current)
    if stage is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Response in status={response.status!r} is not awaiting approval",
        )
    return stage


def _decide(
    notice_id: int,
    decision: str,
    payload: ApprovalActionRequest,
    current_user: User,
    membership: ClientMembership,
    db: Session,
) -> ResponseApprovalOut:
    notice = _get_notice(db, notice_id, membership=membership)
    response = (
        db.query(NoticeResponse)
        .filter(NoticeResponse.notice_id == notice.id)
        .filter(NoticeResponse.client_id == membership.client_id)
        .first()
    )
    if response is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="No response to act on"
        )

    stage = _resolve_pending_stage(response)
    required = _STAGE_TO_PERMISSION[stage]
    try:
        role = ComplianceRole(membership.compliance_role)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid compliance role"
        )
    if not has_permission(role, required):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Role '{role.value}' lacks permission '{required.value}' "
                f"required for stage '{stage.value}'"
            ),
        )

    try:
        approval = apply_approval(
            db,
            response=response,
            stage=stage,
            decision=decision,
            user_id=current_user.id,
            reason=payload.reason,
        )
    except SegregationOfDutiesError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )
    except InvalidResponseTransitionError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(e)
        )
    return ResponseApprovalOut.model_validate(approval)


@router.post("/responses/approve", response_model=ResponseApprovalOut)
def approve_response(
    notice_id: int,
    payload: ApprovalActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_any_compliance_permission(
            CompliancePermission.NOTICE_APPROVE,
            CompliancePermission.NOTICE_APPROVE_LEGAL,
            CompliancePermission.NOTICE_APPROVE_CFO,
        )
    ),
):
    """Approve at whatever stage the response is currently awaiting.

    Per-stage permission is enforced inside `_decide` so the permissions
    matrix stays the source of truth (prevents a CFO from approving the
    Legal stage even with NOTICE_APPROVE_CFO granted).

    H-A second hardening: outer dependency now requires the caller to
    hold AT LEAST ONE of the three approval permissions. The previous
    NOTICE_VIEW gate admitted auditors and finance_team into the handler
    body, where _decide raised 403 — but the route declaration lied
    about the gate.
    """
    if payload.decision != "approved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="POST /approve must use decision='approved'",
        )
    return _decide(
        notice_id, "approved", payload, current_user, membership, db
    )


@router.post("/responses/reject", response_model=ResponseApprovalOut)
def reject_response(
    notice_id: int,
    payload: ApprovalActionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_any_compliance_permission(
            CompliancePermission.NOTICE_APPROVE,
            CompliancePermission.NOTICE_APPROVE_LEGAL,
            CompliancePermission.NOTICE_APPROVE_CFO,
        )
    ),
):
    if payload.decision != "rejected":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="POST /reject must use decision='rejected'",
        )
    return _decide(
        notice_id, "rejected", payload, current_user, membership, db
    )


# ──────────────────────────────────────────────────────────────────────
# Evidence attach / detach
# ──────────────────────────────────────────────────────────────────────

@router.get("/evidence", response_model=list[EvidenceAttachOut])
def list_evidence(
    notice_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    notice = _get_notice(db, notice_id, membership=membership)
    rows = list_attachments(db, notice_id=notice_id, client_id=notice.client_id)
    return [EvidenceAttachOut.model_validate(r) for r in rows]


@router.post("/evidence", response_model=EvidenceAttachOut)
def add_evidence(
    notice_id: int,
    payload: EvidenceAttachRequest,
    current_user: User = Depends(get_current_user),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_ATTACH_EVIDENCE)
    ),
    db: Session = Depends(get_db),
):
    notice = _get_notice(db, notice_id, membership=membership)
    try:
        row = attach_document(
            db,
            notice=notice,
            document_id=payload.document_id,
            user_id=current_user.id,
            description=payload.description,
            display_order=payload.display_order,
        )
    except DocumentAccessDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )
    return EvidenceAttachOut.model_validate(row)


@router.delete("/evidence/{document_id}")
def remove_evidence(
    notice_id: int,
    document_id: int,
    current_user: User = Depends(get_current_user),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_ATTACH_EVIDENCE)
    ),
    db: Session = Depends(get_db),
):
    notice = _get_notice(db, notice_id, membership=membership)
    try:
        removed = detach_document(
            db, notice=notice, document_id=document_id, user_id=current_user.id
        )
    except DocumentAccessDenied as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
        )
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evidence link not found for document {document_id}",
        )
    return {"ok": True, "notice_id": notice_id, "document_id": document_id}
