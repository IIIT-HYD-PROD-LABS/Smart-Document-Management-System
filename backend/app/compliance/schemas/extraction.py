"""Pydantic schemas for Phase 17 — AI notice field extraction.

Three schema families:

  1. Wire shapes for the LLM envelope (`ExtractedField`, `ExtractionEnvelope`).
  2. Routing decision returned by `extraction_routing_service.route_or_apply`
     (`ExtractionRouteDecision`).
  3. Request/response for the three new endpoints (`AcceptExtractionItem`,
     `AcceptExtractionPayload`, `ExtractionResponse`).

The 14-field schema (D-04) is a soft contract here. We do not enumerate
the 14 keys as a Pydantic Literal because Anthropic and Gemini may return
a strict subset when fields are not present in the source text (D-05).
The extractor service is responsible for dropping unknown keys.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────
# LLM envelope
# ─────────────────────────────────────────────────────────────────────


class ExtractedField(BaseModel):
    """One field as returned by the extractor (D-03)."""

    value: Any
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_span: Optional[str] = None
    # Set by `notice_extraction_validator.validate_and_score` per D-33.
    # When non-None, `confidence` is the POST-validation score and
    # `original_confidence` is the model's raw self-report.
    original_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    validation_failure: Optional[str] = None


class ExtractionEnvelope(BaseModel):
    """Full extractor return shape (D-03)."""

    # Pydantic 2.x reserves the `model_*` namespace and would warn on the
    # `model` field. Opt out so we can use the natural name.
    model_config = ConfigDict(protected_namespaces=())

    fields: dict[str, ExtractedField]
    average_confidence: float = Field(..., ge=0.0, le=1.0)
    model: str
    tokens_in: int = Field(..., ge=0)
    tokens_out: int = Field(..., ge=0)
    latency_ms: int = Field(..., ge=0)


# ─────────────────────────────────────────────────────────────────────
# Routing decision
# ─────────────────────────────────────────────────────────────────────


RouteAction = Literal["apply", "review_queue", "failed"]


class ExtractionRouteDecision(BaseModel):
    """Output of `extraction_routing_service.route_or_apply` (D-06, D-25)."""

    action: RouteAction
    # Populated when `action='review_queue'` — human-readable rationale
    # for the review-queue card.
    reason: Optional[str] = None
    average_confidence: float = Field(..., ge=0.0, le=1.0)
    critical_field_confidence: dict[str, float]


# ─────────────────────────────────────────────────────────────────────
# Endpoint payloads / responses
# ─────────────────────────────────────────────────────────────────────


class AcceptExtractionItem(BaseModel):
    """One field the user chose to accept on POST /accept-extraction (D-21)."""

    field: str
    value: Any
    accept_as_is: bool = True


class AcceptExtractionPayload(BaseModel):
    """POST /api/compliance/notices/{id}/accept-extraction body."""

    items: List[AcceptExtractionItem] = Field(..., min_length=1, max_length=14)


class ExtractionResponse(BaseModel):
    """GET /api/compliance/notices/{id}/extraction response."""

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    notice_id: int
    extraction_status: Optional[
        Literal["pending", "completed", "failed", "accepted", "superseded"]
    ] = None
    extraction_confidence: Optional[Decimal] = None
    extracted_by_provider: Optional[str] = None
    extracted_at: Optional[datetime] = None
    envelope: Optional[ExtractionEnvelope] = None


class ExtractPreviewResponse(BaseModel):
    """POST /api/compliance/notices/extract-preview response (D-19)."""

    envelope: ExtractionEnvelope
    decision: ExtractionRouteDecision
