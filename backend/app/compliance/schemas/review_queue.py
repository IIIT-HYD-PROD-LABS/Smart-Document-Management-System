"""Pydantic schemas for the notice review queue — Phase 10 CLASS-04.

Schemas:
  - ReviewQueueOut          : GET /pending and GET /{id} response
  - ReviewQueueAssignRequest: PATCH /{id}/assign body
  - ReviewQueueAssignResponse: PATCH /{id}/assign success body
"""
from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

AuthorityT = Literal["GST", "IT", "MCA", "RBI", "SEBI"]


class ReviewQueueOut(BaseModel):
    """A pending or completed review queue row."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    notice_id: int
    client_id: int

    predicted_authority: Optional[str] = None
    predicted_authority_confidence: Optional[Decimal] = None
    predicted_type_id: Optional[int] = None
    predicted_type_confidence: Optional[Decimal] = None

    model_version: str
    reason: str

    reviewer_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None
    reviewer_assigned_authority: Optional[str] = None
    reviewer_assigned_type_id: Optional[int] = None

    created_at: datetime

    @property
    def is_pending(self) -> bool:
        return self.reviewed_at is None


class ReviewQueueAssignRequest(BaseModel):
    """Reviewer-supplied authoritative classification.

    Either field may be supplied. If `authority` is supplied, the parent
    ComplianceNotice's authority is updated; same for notice_type_id.
    """

    authority: Optional[AuthorityT] = None
    notice_type_id: Optional[int] = Field(None, ge=1)

    def model_post_init(self, __context):
        # Pydantic v2 validator: at least one of authority or notice_type_id must be set.
        if self.authority is None and self.notice_type_id is None:
            raise ValueError(
                "ReviewQueueAssignRequest must include at least one of "
                "'authority' or 'notice_type_id'"
            )


class ReviewQueueAssignResponse(BaseModel):
    """200 response from PATCH /api/compliance/review/{id}/assign."""

    review_id: int
    notice_id: int
    assigned_authority: Optional[str] = None
    assigned_notice_type_id: Optional[int] = None
    reviewed_at: datetime


class ReviewQueueListResponse(BaseModel):
    """GET /api/compliance/review/pending — paginated."""

    items: list[ReviewQueueOut]
    page: int
    page_size: int
    total: int
