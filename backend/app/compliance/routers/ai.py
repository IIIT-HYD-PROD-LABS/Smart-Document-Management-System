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
# NOTE: do NOT add `from __future__ import annotations` here. The combination
# of (a) future annotations, (b) `@limiter.limit(...)` wrapping route
# handlers, and (c) Pydantic body params breaks OpenAPI schema generation
# with `PydanticUserError: TypeAdapter[Annotated[ForwardRef(...), Body(...)]]
# is not fully defined`. The other compliance routers either rely on path
# parameters (no body resolution needed) or have no rate-limit decorator.

import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.dependencies import require_compliance_permission
from app.utils.rate_limiter import limiter
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
from app.database import get_async_db
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


async def _require_credential(db: AsyncSession, client_id: int):
    """Resolve the AI credential for this tenant: per-tenant BYOK first, then
    the server-default provider (settings.LLM_PROVIDER, e.g. Ollama). Only 412
    when neither is available — with a server default configured this rarely
    fires, so AI features work out of the box without a tenant key."""
    cred = await ai_service.resolve_credential_async(db, client_id)
    if not cred:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=(
                "No AI provider is available. Configure a server LLM provider "
                "(LLM_PROVIDER) or set a per-tenant key in Settings → AI."
            ),
        )
    return cred


async def _require_notice(
    db: AsyncSession, notice_id: int, client_id: int
) -> ComplianceNotice:
    result = await db.execute(
        select(ComplianceNotice).where(
            ComplianceNotice.id == notice_id,
            ComplianceNotice.client_id == client_id,
        )
    )
    notice = result.scalar_one_or_none()
    if not notice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Notice not found"
        )
    return notice


async def _require_bill(db: AsyncSession, bill_id: int, client_id: int) -> Bill:
    result = await db.execute(
        select(Bill).where(Bill.id == bill_id, Bill.client_id == client_id)
    )
    bill = result.scalar_one_or_none()
    if not bill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
        )
    return bill


# ─────────────────────────────────────────────────────────────────────
# Credential CRUD
# ─────────────────────────────────────────────────────────────────────


@router.get("/credentials", response_model=AICredentialOut | None)
async def get_credential(
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """Read-only — anyone in the tenant can see WHICH AI is connected;
    only admins can change it."""
    cred = await ai_service.get_credential_async(db, membership.client_id)
    if not cred:
        return None
    return cred


@router.post(
    "/credentials",
    response_model=AICredentialOut,
    status_code=status.HTTP_200_OK,
)
async def set_credential(
    payload: AICredentialCreate,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_MANAGE_TEAM)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    cred = await ai_service.set_credential(
        db,
        client_id=membership.client_id,
        provider=payload.provider,
        model=payload.model,
        api_key=payload.api_key,
    )
    return cred


@router.delete("/credentials", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.CLIENT_MANAGE_TEAM)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    await ai_service.delete_credential(db, client_id=membership.client_id)
    return None


@router.post(
    "/credentials/test",
    response_model=AICredentialTestResult,
)
@limiter.limit("10/minute")
def test_credential(
    request: Request,
    # slowapi's wrapper auto-injects rate-limit headers via this Response
    # arg when the handler returns a non-Response value (dict / Pydantic
    # model). Without it, `kwargs.get("response")` is None and slowapi
    # raises "parameter `response` must be an instance of
    # starlette.responses.Response". Pattern mirrors documents.py:286.
    response: Response,
    # Explicit Body() so the OpenAPI schema generator (which introspects
    # the signature after slowapi wraps it) keeps recognising the Pydantic
    # model as the request body rather than misclassifying it as a query.
    payload: AICredentialCreate = Body(...),
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
        # Never echo the provider exception string back to the client: the
        # Anthropic SDK / Google REST body can include the submitted key or
        # request headers in their error representation, and the test
        # endpoint accepts the plaintext key in the payload. Log the full
        # error server-side, return a fixed string.
        logger.warning("ai_test_credential_auth_failed", exc_info=e)
        return AICredentialTestResult(
            ok=False, detail="Auth failed: invalid or rejected key"
        )
    except AIRateLimitError as e:
        logger.warning("ai_test_credential_rate_limited", exc_info=e)
        return AICredentialTestResult(
            ok=False, detail="Rate limited by provider, try again shortly"
        )
    except AIProviderError as e:
        logger.warning("ai_test_credential_provider_error", exc_info=e)
        return AICredentialTestResult(
            ok=False,
            detail="Provider error, check the model name and provider status",
        )


# ─────────────────────────────────────────────────────────────────────
# Notice AI
# ─────────────────────────────────────────────────────────────────────


@router.post(
    "/notice-summary/{notice_id}", response_model=NoticeSummaryResponse
)
@limiter.limit("20/minute")
async def notice_summary(
    request: Request,
    response: Response,
    notice_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    cred = await _require_credential(db, membership.client_id)
    notice = await _require_notice(db, notice_id, membership.client_id)
    try:
        return await ai_service.summarize_notice(db, cred, notice)
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
@limiter.limit("20/minute")
async def notice_actions(
    request: Request,
    response: Response,
    notice_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    cred = await _require_credential(db, membership.client_id)
    notice = await _require_notice(db, notice_id, membership.client_id)
    try:
        return {"actions": await ai_service.recommend_notice_actions(db, cred, notice)}
    except (
        AIOutOfScopeError,
        AIAuthError,
        AIRateLimitError,
        AIProviderError,
    ) as e:
        raise _map_ai_error(e) from e


# ─────────────────────────────────────────────────────────────────────
# Notice response drafting (Phase 18)
# ─────────────────────────────────────────────────────────────────────


class NoticeResponseDraftRequest(BaseModel):
    """Body for POST /ai/notice-response-draft/{notice_id}.

    `user_guidance` is the only accepted field; `extra="forbid"` rejects
    oversized/unexpected payloads at the boundary (mirrors ChatRequest).
    The 800-char cap matches MAX_GUIDANCE_CHARS in
    services/response_drafter_prompt.py, where the service still truncates as
    defence-in-depth; rejecting here means an overlong payload fails at the
    boundary instead of being silently clipped.
    """

    model_config = ConfigDict(extra="forbid")

    user_guidance: str = Field(default="", max_length=800)


@router.post(
    "/notice-response-draft/{notice_id}",
)
@limiter.limit("12/minute")
async def notice_response_draft(
    request: Request,
    response: Response,
    notice_id: int,
    body: NoticeResponseDraftRequest = Body(default_factory=NoticeResponseDraftRequest),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_DRAFT_RESPONSE)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """Phase 18: generate an AI-assisted draft reply for the notice.

    Permission gate is NOTICE_DRAFT_RESPONSE (compliance_head, legal_team,
    ca_consultant, staff). Drafts ALWAYS return preview-only; the caller
    decides whether to persist as a NoticeResponseVersion via the existing
    POST /api/compliance/notices/{id}/responses endpoint.

    Rate limited to 12/minute per Phase 17 extract-preview parity since
    the cost profile is the same (one provider call per request).
    """
    from app.compliance.services.response_drafter_service import (
        ResponseDraftCredentialMissingError,
        draft_response_for_notice,
    )

    await _require_credential(db, membership.client_id)
    notice = await _require_notice(db, notice_id, membership.client_id)

    try:
        return await draft_response_for_notice(
            db,
            notice=notice,
            user_id=membership.user_id,
            user_guidance=body.user_guidance,
        )
    except ResponseDraftCredentialMissingError:
        raise HTTPException(
            status_code=status.HTTP_412_PRECONDITION_FAILED,
            detail=(
                "No AI credential configured for this tenant. "
                "Set one in Settings -> AI."
            ),
        )
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
@limiter.limit("20/minute")
async def invoice_summary(
    request: Request,
    response: Response,
    bill_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    cred = await _require_credential(db, membership.client_id)
    bill = await _require_bill(db, bill_id, membership.client_id)
    try:
        return await ai_service.summarize_invoice(db, cred, bill)
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
@limiter.limit("20/minute")
async def invoice_actions(
    request: Request,
    response: Response,
    bill_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    cred = await _require_credential(db, membership.client_id)
    bill = await _require_bill(db, bill_id, membership.client_id)
    try:
        return {"actions": await ai_service.recommend_invoice_actions(db, cred, bill)}
    except (
        AIOutOfScopeError,
        AIAuthError,
        AIRateLimitError,
        AIProviderError,
    ) as e:
        raise _map_ai_error(e) from e


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("15/minute")
async def chat(
    request: Request,
    response: Response,
    payload: ChatRequest = Body(...),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
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

    cred = await _require_credential(db, membership.client_id)
    # No substring scrubbing of history: dropping any message merely CONTAINING
    # "OUT_OF_SCOPE"/"ignore previous instructions" corrupted legitimate content
    # (e.g. a user asking ABOUT those phrases) and was trivially bypassed. The
    # scope-locked SYSTEM prompt in ai_service is the real defence and stays intact.
    msgs = [m.model_dump() for m in payload.messages]

    try:
        return await ai_service.chat_with_assistant(db, cred, msgs)
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
@limiter.limit("20/minute")
async def invoice_timing(
    request: Request,
    response: Response,
    bill_id: int,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    cred = await _require_credential(db, membership.client_id)
    bill = await _require_bill(db, bill_id, membership.client_id)
    try:
        return await ai_service.suggest_invoice_payment_timing(db, cred, bill)
    except (
        AIOutOfScopeError,
        AIAuthError,
        AIRateLimitError,
        AIProviderError,
    ) as e:
        raise _map_ai_error(e) from e
