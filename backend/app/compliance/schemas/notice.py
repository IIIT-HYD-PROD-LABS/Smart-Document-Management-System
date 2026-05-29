"""Pydantic schemas for compliance notice.

Covers LIFE-01 (notice CRUD), LIFE-04 (status transitions),
LIFE-07 (filters), LIFE-08 (bulk update partial-failure semantics).
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.compliance.utils.indian_validators import validate_notice_number


AuthorityT = Literal["GST", "IT", "MCA", "RBI", "SEBI"]
StatusT = Literal[
    "received",
    "under_review",
    "response_drafted",
    "submitted",
    "resolved",
    "dismissed",
]


class NoticeCreate(BaseModel):
    """Input shape for POST /api/compliance/notices.

    `notice_number` format is checked against the per-authority regex
    (D-07) but a non-match is NOT rejected — many notices have non-standard
    formats. Phase 10 BERT classifier will harden this once enough
    empirical samples land.
    """

    client_id: int
    notice_number: str = Field(..., min_length=1, max_length=100)
    authority: AuthorityT
    notice_type_id: Optional[int] = None
    registration_id: Optional[int] = None
    parent_notice_id: Optional[int] = None
    document_id: Optional[int] = None
    received_date: date
    response_deadline: Optional[date] = None
    hearing_date: Optional[date] = None
    compliance_date: Optional[date] = None
    appeal_deadline: Optional[date] = None
    tax_demand: Optional[Decimal] = None
    interest: Optional[Decimal] = None
    penalty: Optional[Decimal] = None
    total_liability: Optional[Decimal] = None
    legal_sections: list[str] = Field(default_factory=list)
    assigned_user_id: Optional[int] = None
    tags: list[Annotated[str, StringConstraints(max_length=100)]] = Field(
        default_factory=list, max_length=50
    )

    @field_validator("notice_number")
    @classmethod
    def _validate_number_format(cls, v: str, info):
        authority = info.data.get("authority")
        if authority and not validate_notice_number(authority, v):
            # Non-standard format — log a warning at the router layer.
            # Do NOT reject because real-world notices vary in format.
            pass
        return v


class NoticeUpdate(BaseModel):
    """Partial update — every field optional. Status changes go through
    the dedicated NoticeStatusTransition endpoint (Pitfall 8 mitigation:
    direct ORM update path is closed at the API boundary).
    """

    notice_type_id: Optional[int] = None
    registration_id: Optional[int] = None
    response_deadline: Optional[date] = None
    hearing_date: Optional[date] = None
    compliance_date: Optional[date] = None
    appeal_deadline: Optional[date] = None
    tax_demand: Optional[Decimal] = None
    interest: Optional[Decimal] = None
    penalty: Optional[Decimal] = None
    total_liability: Optional[Decimal] = None
    legal_sections: Optional[list[str]] = None
    assigned_user_id: Optional[int] = None


class NoticeStatusTransition(BaseModel):
    """POST /api/compliance/notices/{id}/transition body."""

    new_status: StatusT
    reason: Optional[str] = Field(None, max_length=500)


class BulkUpdateRequest(BaseModel):
    """LIFE-08 bulk action: 1..200 notices in one call."""

    notice_ids: list[int] = Field(..., min_length=1, max_length=200)
    new_status: StatusT
    reason: Optional[str] = Field(None, max_length=500)


class BulkUpdateResultRow(BaseModel):
    id: int
    success: bool
    error: Optional[str] = None


class BulkUpdateResponse(BaseModel):
    """Per-row partial-failure response (Pattern 8 from RESEARCH).

    Frontend toast: "Updated {summary.ok} of {summary.ok+summary.failed}",
    plus per-row red error indicator on rows where success=False.
    """

    results: list[BulkUpdateResultRow]
    summary: dict[str, int]  # {"ok": int, "failed": int}


class NoticeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    notice_number: str
    authority: str
    status: str
    received_date: date
    response_deadline: Optional[date] = None
    hearing_date: Optional[date] = None
    compliance_date: Optional[date] = None
    appeal_deadline: Optional[date] = None
    tax_demand: Optional[Decimal] = None
    interest: Optional[Decimal] = None
    penalty: Optional[Decimal] = None
    total_liability: Optional[Decimal] = None
    legal_sections: list[str] = Field(default_factory=list)
    assigned_user_id: Optional[int] = None
    parent_notice_id: Optional[int] = None
    document_id: Optional[int] = None
    notice_type_id: Optional[int] = None
    registration_id: Optional[int] = None
    status_changed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Phase 10 ML fields. The DB columns + frontend types/compliance.ts
    # both declare these; this schema previously dropped them, so the
    # WhyThisRiskScore panel + risk-tier dot rendered empty even when
    # the classifier had populated rows. NULL is allowed for v2.0
    # rule-based output that didn't run the classifier (D-06).
    classifier_authority_confidence: Optional[Decimal] = None
    classifier_type_confidence: Optional[Decimal] = None
    risk_score: Optional[Decimal] = None
    risk_tier: Optional[str] = None
    ner_extracted_fields: Optional[dict] = None
    model_version: Optional[str] = None
    source: Optional[str] = None
    classified_at: Optional[datetime] = None
    risk_scored_at: Optional[datetime] = None

    # Phase 17 AI extraction provenance. These columns existed on the model
    # but NoticeOut dropped them, so the detail page's
    # ExtractionProvenanceDisclosure (gated on Boolean(extraction_status))
    # never rendered and AI-extracted notices looked manually entered. The
    # large extracted_fields JSONB stays out of this list+detail schema; the
    # disclosure fetches it via GET /{notice_id}/extraction.
    extraction_status: Optional[str] = None
    extraction_confidence: Optional[Decimal] = None
    extracted_by_provider: Optional[str] = None
    extracted_at: Optional[datetime] = None


class NoticeFilters(BaseModel):
    """Query-param shape for LIFE-07 list endpoint."""

    authority: Optional[AuthorityT] = None
    status: Optional[StatusT] = None
    notice_type_id: Optional[int] = None
    response_deadline_before: Optional[date] = None
    response_deadline_after: Optional[date] = None
    gstin_or_pan: Optional[str] = None
    assigned_user_id: Optional[int] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(50, ge=1, le=500)
