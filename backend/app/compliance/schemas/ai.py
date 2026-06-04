"""Pydantic schemas for the BYOK AI feature — Phase 16.

Two schema families live here:

  1. Credential CRUD       — the tenant's stored provider + key
  2. AI task responses     — typed shapes the frontend consumes

The plaintext API key is **only** ever in `AICredentialCreate`. Output
schemas expose `has_key: bool` plus the model + provider so the UI can
render "Connected to <provider> · <model>" without ever shipping the
secret over the wire.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ─────────────────────────────────────────────────────────────────────
# Credential CRUD
# ─────────────────────────────────────────────────────────────────────


class AICredentialCreate(BaseModel):
    """POST/PATCH payload — tenant submits a fresh provider + model + key."""

    # `model` is the LLM model name (e.g. "claude-3-5-sonnet"). Pydantic 2.x
    # reserves the `model_*` namespace and warns when user fields start with
    # `model`; we opt out of that protection here since `model` is the
    # canonical field name for both providers.
    model_config = ConfigDict(protected_namespaces=())

    # Enterprise BYOK: the client connects their own API. All three cloud
    # providers the adapter factory (ai_providers.build_provider) supports are
    # selectable; the per-tenant key is theirs. Ollama is server-side only (no
    # key, SSRF-locked base URL) so it is not a BYOK choice.
    provider: Literal["anthropic", "google", "openai"]
    model: str = Field(..., min_length=1, max_length=100)
    api_key: str = Field(..., min_length=8, max_length=500)


class AICredentialOut(BaseModel):
    """GET response — never returns the key. `has_key` is always True for
    rows that exist; the field is present so absence (404 → null) and
    existence read symmetrically on the client."""

    # See AICredentialCreate for why we opt out of the model_* namespace.
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    provider: str
    model: str
    has_key: bool = True
    created_at: datetime
    updated_at: datetime
    last_used_at: Optional[datetime] = None


class AICredentialTestResult(BaseModel):
    ok: bool
    detail: Optional[str] = None
    latency_ms: Optional[int] = None


# ─────────────────────────────────────────────────────────────────────
# AI task responses — common building blocks
# ─────────────────────────────────────────────────────────────────────


class AIActionItem(BaseModel):
    """One concrete suggested next step."""

    label: str
    rationale: str
    urgency: Literal["high", "medium", "low"]


class NoticeSummaryResponse(BaseModel):
    summary: str
    key_points: List[str] = Field(default_factory=list)
    deadline_iso: Optional[str] = None


class NoticeActionsResponse(BaseModel):
    actions: List[AIActionItem]


class InvoiceSummaryResponse(BaseModel):
    summary: str
    anomalies: List[str] = Field(default_factory=list)


class InvoiceActionsResponse(BaseModel):
    actions: List[AIActionItem]


class InvoiceTimingResponse(BaseModel):
    recommendation: str
    rationale: str
    suggested_payment_date: Optional[str] = None  # ISO date


class OutOfScopeError(BaseModel):
    """Returned to the frontend when the AI refused with the OUT_OF_SCOPE
    sentinel. The frontend renders this as a friendly explanation rather
    than a backend error so the user understands the boundary."""

    detail: str = "I can only help with TaxSync compliance and finance work."


# ─────────────────────────────────────────────────────────────────────
# Chat
# ─────────────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    """Stateless chat request — full message history each call.

    Capped at 20 messages and 8000 chars per message to keep cost +
    latency bounded. Last message MUST be from the user; the validator
    enforces that.
    """

    messages: List[ChatMessage] = Field(..., min_length=1, max_length=20)


class ChatResponse(BaseModel):
    reply: str
    out_of_scope: bool = False
