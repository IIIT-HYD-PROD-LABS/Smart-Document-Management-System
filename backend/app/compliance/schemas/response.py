"""Pydantic schemas for Phase 12 response workflow."""
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

ResponseStatusT = Literal[
    "draft",
    "reviewer_pending",
    "legal_pending",
    "cfo_pending",
    "approved",
    "rejected",
    "withdrawn",
]

ApprovalStageT = Literal["reviewer", "legal", "cfo"]
ApprovalDecisionT = Literal["approved", "rejected"]


class ResponseVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    response_id: int
    version_no: int
    subject: Optional[str] = None
    body_markdown: str
    recipient: Optional[str] = None
    response_date: Optional[date] = None
    metadata_json: Optional[dict] = None
    rolled_back_from_version_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime


class ResponseApprovalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    response_id: int
    version_id: Optional[int] = None
    stage: ApprovalStageT
    decision: ApprovalDecisionT
    actor_user_id: Optional[int] = None
    reason: Optional[str] = None
    created_at: datetime


class ResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    notice_id: int
    client_id: int
    status: ResponseStatusT
    current_version_id: Optional[int] = None
    created_by_user_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    current_version: Optional[ResponseVersionOut] = None


class ResponseDetailOut(ResponseOut):
    versions: list[ResponseVersionOut] = Field(default_factory=list)
    approvals: list[ResponseApprovalOut] = Field(default_factory=list)


class ResponseDraftPayload(BaseModel):
    """Body of POST /responses or PATCH /responses/{id}.

    A new draft uses the same shape; PATCH-style update_response_draft
    creates a new version row from the supplied fields.
    """

    subject: Optional[str] = Field(None, max_length=500)
    body_markdown: str = Field(default="")
    recipient: Optional[str] = Field(None, max_length=500)
    response_date: Optional[date] = None
    metadata_json: Optional[dict] = None


class ResponseRollbackRequest(BaseModel):
    target_version_id: int


class ApprovalActionRequest(BaseModel):
    decision: ApprovalDecisionT
    reason: Optional[str] = Field(None, max_length=2000)


class EvidenceAttachOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    notice_id: int
    document_id: int
    display_order: int
    description: Optional[str] = None
    added_by_user_id: Optional[int] = None
    created_at: datetime


class EvidenceAttachRequest(BaseModel):
    document_id: int = Field(..., ge=1)
    description: Optional[str] = Field(None, max_length=500)
    display_order: int = Field(default=0, ge=0)
