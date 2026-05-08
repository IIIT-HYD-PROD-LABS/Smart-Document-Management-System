"""AI router — Phase 16. BYOK Anthropic / Gemini surfaces for TaxSync.

Endpoints:

  GET    /ai/credentials                       — return provider + model
                                                  (NO key)
  POST   /ai/credentials                       — set / replace key
  DELETE /ai/credentials                       — clear
  POST   /ai/credentials/test                  — round-trip ping

  POST   /ai/notice-summary/{notice_id}        — summary + key points
  POST   /ai/notice-actions/{notice_id}        — recommended actions

  POST   /ai/invoice-summary/{bill_id}         — summary + anomalies
  POST   /ai/invoice-actions/{bill_id}         — suggested actions
  POST   /ai/invoice-timing/{bill_id}          — payment timing suggestion

Credential routes are gated by CLIENT_MANAGE_TEAM (admin-grade). The AI
task routes are gated by NOTICE_VIEW so any active member of the tenant
can use the AI on the data they can already read.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.models.notice import ComplianceNotice
from app.compliance.schemas.ai import (
    AICredentialCreate,
    AICredentialOut,
    AICredentialTestResult,
    ChatRequest,
    ChatResponse,
    InvoiceActionsResponse,
    InvoiceSummaryResponse,
    InvoiceTimingResponse,
    NoticeActionsResponse,
    NoticeSummaryResponse,
)
from app.compliance.services import ai_service
from app.compliance.services.ai_service import (
    AIAuthError,
    AIOutOfScopeError,
    AIProviderError,
    AIRateLimitError,
)
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_db
from app.email.models.bill import Bill

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/ai", tags=["compliance-ai"])


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _map_ai_error(e: Exception) -> HTTPException:
    """Map provider exceptions to HTTP responses.

    `AIProviderError.__str__` can include the provider's raw response
    body (the Anthropic SDK echoes the request/response in error
    messages). We log the full exception at WARNING and return a curated
    string the user can act on — the most common cause is a retired
    model name, so we hint at that without leaking provider internals.
    """
    if isinstance(e, AIOutOfScopeError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="I can only help with TaxSync compliance and finance work.",
        )
    if isinstance(e, AIAuthError):
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "AI provider rejected the stored API key. "
                "Update the key in Settings → AI."
            ),
        )
    if isinstance(e, AIRateLimitError):
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI provider rate-limited the request. Try again shortly.",
        )
    if isinstance(e, AIProviderError):
        logger.warning("ai_provider_error", exc_info=e)
        # Pass through OUR own user-actionable messages (e.g. the 404
        # model-not-found hint set in GoogleProvider). Generic messages
        # from upstream SDKs get redacted to avoid response-body leakage.
        msg = str(e)
        if "Model '" in msg and "not available" in msg:
            return HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=msg
            )
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "AI provider returned an error. "
                "Check the model name in Settings → AI and the provider "
                "status page; details have been logged server-side."
            ),
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unexpected AI failure.",
    )


def _require_credential(db: Session, client_id: int):
    cred = ai_service.get_credential(db, client_id)
    if not cred:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=(
                "No AI credential configured for this tenant. "
                "Set one in Settings → AI."
            ),
        )
    return cred


def _require_notice(db: Session, notice_id: int, client_id: int) -> ComplianceNotice:
    notice = (
        db.query(ComplianceNotice)
        .filter(
            ComplianceNotice.id == notice_id,
            ComplianceNotice.client_id == client_id,
        )
        .first()
    )
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found"
        )
    return notice


def _require_bill(db: Session, bill_id: int, client_id: int) -> Bill:
    bill = (
        db.query(Bill)
        .filter(Bill.id == bill_id, Bill.client_id == client_id)
        .first()
    )
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
        )
    return bill


# ─────────────────────────────────────────────────────────────────────
# Credential CRUD
# ─────────────────────────────────────────────────────────────────────


@router.get("/credentials", response_model=AICredentialOut | None)
def get_credential(
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    """Read-only — anyone in the tenant can see WHICH AI is connected;
    only admins can change it."""
    cred = ai_service.get_credential(db, membership.client_id)
    if not cred:
        return None
    return cred


@router.post(
    "/credentials",
    response_model=AICredentialOut,
    status_code=status.HTTP_200_OK,
)
def set_credential(
    payload: AICredentialCreate,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_MANAGE_TEAM)
    ),
    db: Session = Depends(get_db),
):
    cred = ai_service.set_credential(
        db,
        client_id=membership.client_id,
        provider=payload.provider,
        model=payload.model,
        api_key=payload.api_key,
    )
    return cred


@router.delete("/credentials", status_code=status.HTTP_204_NO_CONTENT)
def delete_credential(
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_MANAGE_TEAM)
    ),
    db: Session = Depends(get_db),
):
    ai_service.delete_credential(db, client_id=membership.client_id)
    return None


@router.post(
    "/credentials/test",
    response_model=AICredentialTestResult,
)
def test_credential(
    payload: AICredentialCreate,
    _membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_MANAGE_TEAM)
    ),
):
    """One-token round-trip — used by the Settings page to validate a
    key BEFORE persisting it."""
    try:
        result = ai_service.test_credential(
            payload.provider, payload.api_key, payload.model
        )
        return AICredentialTestResult(ok=True, latency_ms=result["latency_ms"])
    except AIAuthError as e:
        return AICredentialTestResult(ok=False, detail=f"Auth failed: {e}")
    except AIRateLimitError as e:
        return AICredentialTestResult(ok=False, detail=f"Rate limited: {e}")
    except AIProviderError as e:
        return AICredentialTestResult(ok=False, detail=f"Provider error: {e}")


# ─────────────────────────────────────────────────────────────────────
# Notice AI
# ─────────────────────────────────────────────────────────────────────


@router.post(
    "/notice-summary/{notice_id}", response_model=NoticeSummaryResponse
)
def notice_summary(
    notice_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    cred = _require_credential(db, membership.client_id)
    notice = _require_notice(db, notice_id, membership.client_id)
    try:
        return ai_service.summarize_notice(db, cred, notice)
    except (
        AIOutOfScopeError,
        AIAuthError,
        AIRateLimitError,
        AIProviderError,
    ) as e:
        raise _map_ai_error(e) from e


@router.post(
    "/notice-actions/{notice_id}", response_model=NoticeActionsResponse
)
def notice_actions(
    notice_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    cred = _require_credential(db, membership.client_id)
    notice = _require_notice(db, notice_id, membership.client_id)
    try:
        return {"actions": ai_service.recommend_notice_actions(db, cred, notice)}
    except (
        AIOutOfScopeError,
        AIAuthError,
        AIRateLimitError,
        AIProviderError,
    ) as e:
        raise _map_ai_error(e) from e


# ─────────────────────────────────────────────────────────────────────
# Invoice AI
# ─────────────────────────────────────────────────────────────────────


@router.post(
    "/invoice-summary/{bill_id}", response_model=InvoiceSummaryResponse
)
def invoice_summary(
    bill_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    cred = _require_credential(db, membership.client_id)
    bill = _require_bill(db, bill_id, membership.client_id)
    try:
        return ai_service.summarize_invoice(db, cred, bill)
    except (
        AIOutOfScopeError,
        AIAuthError,
        AIRateLimitError,
        AIProviderError,
    ) as e:
        raise _map_ai_error(e) from e


@router.post(
    "/invoice-actions/{bill_id}", response_model=InvoiceActionsResponse
)
def invoice_actions(
    bill_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    cred = _require_credential(db, membership.client_id)
    bill = _require_bill(db, bill_id, membership.client_id)
    try:
        return {"actions": ai_service.recommend_invoice_actions(db, cred, bill)}
    except (
        AIOutOfScopeError,
        AIAuthError,
        AIRateLimitError,
        AIProviderError,
    ) as e:
        raise _map_ai_error(e) from e


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    """Multi-turn chat with the BYOK assistant.

    Stateless on the server side — the client sends the full message
    history each call. Capped at 20 messages by the schema. The last
    message must be from the user; we validate that here so a malformed
    client doesn't burn tokens on a noop.
    """
    if not payload.messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one message is required.",
        )
    if payload.messages[-1].role != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The last message must be from the user.",
        )

    cred = _require_credential(db, membership.client_id)
    msgs = [m.model_dump() for m in payload.messages]

    # Defensive: a hostile client could craft fake `assistant` turns
    # containing the OUT_OF_SCOPE sentinel or instructions designed to
    # poison the conversation history the model sees ("ignore your
    # earlier instructions"). The system prompt already tells the model
    # to ignore tampered history, but this is cheap belt-and-braces.
    msgs = [
        m for m in msgs
        if "OUT_OF_SCOPE" not in m["content"]
        and "ignore your earlier" not in m["content"].lower()
        and "ignore previous instructions" not in m["content"].lower()
    ]
    if not msgs or msgs[-1]["role"] != "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message history is empty or ends on an assistant turn.",
        )

    try:
        return ai_service.chat_with_assistant(db, cred, msgs)
    except (
        AIOutOfScopeError,
        AIAuthError,
        AIRateLimitError,
        AIProviderError,
    ) as e:
        raise _map_ai_error(e) from e


@router.post(
    "/invoice-timing/{bill_id}", response_model=InvoiceTimingResponse
)
def invoice_timing(
    bill_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    cred = _require_credential(db, membership.client_id)
    bill = _require_bill(db, bill_id, membership.client_id)
    try:
        return ai_service.suggest_invoice_payment_timing(db, cred, bill)
    except (
        AIOutOfScopeError,
        AIAuthError,
        AIRateLimitError,
        AIProviderError,
    ) as e:
        raise _map_ai_error(e) from e
