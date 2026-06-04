"""Phase 18: AI-assisted notice response drafting (BYOK).

`draft_response_for_notice(db, notice_id, client_id, user_id, user_guidance)`
calls the tenant's Phase 16 BYOK provider with the notice context + any
Phase 17 extracted fields and returns a markdown draft body the reviewer
can edit before submitting through Phase 12's 4-stage approval workflow.

Design choices:
  * The service does NOT persist a NoticeResponseVersion row. The router is
    the persistence boundary, so unit tests can exercise the drafting path
    against a MagicMock notice without touching the DB.
  * Drafts always land at version 0 (pre-Drafter stage). They never bypass
    the existing approval state machine.
  * Audit row `action='notice_ai_draft'` is written per call with provider,
    model, latency, token counts, body SHA-256 of the GENERATED draft, and
    the SHA-256 of the user_guidance. No raw draft text and no guidance
    text in audit args.
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from sqlalchemy.orm import Session

from app.compliance.models.notice import ComplianceNotice
from app.compliance.services import ai_service
from app.compliance.services.ai_providers import (
    AIAuthError,
    AIProviderError,
    AIRateLimitError,
)
from app.compliance.services.response_drafter_prompt import (
    MAX_GUIDANCE_CHARS,
    MAX_RESPONSE_TOKENS,
    build_user_prompt,
)
from app.services.audit_service import log_audit_event_strict


logger = logging.getLogger(__name__)


__all__ = [
    "AIAuthError",
    "AIProviderError",
    "AIRateLimitError",
    "ResponseDraftCredentialMissingError",
    "draft_response_for_notice",
]


class ResponseDraftCredentialMissingError(Exception):
    """Tenant has no AICredential row. Router maps to HTTP 412 (matches Phase 17)."""


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _write_audit(
    *,
    user_id: int | None,
    notice_id: int | None,
    provider_name: str,
    model: str,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    body_sha256: str,
    guidance_sha256: str,
    extracted_fields_used: list[str],
    failure: str | None = None,
) -> None:
    """One audit row per draft call. PII-redacted: no raw guidance text,
    no raw draft text. Phase 9 immutability trigger applies."""
    details: dict[str, Any] = {
        "provider": provider_name,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": latency_ms,
        "body_sha256": body_sha256,
        "guidance_sha256": guidance_sha256,
        "extracted_fields_used": extracted_fields_used,
    }
    if failure:
        details["failure"] = failure
    log_audit_event_strict(
        user_id=user_id,
        action="notice_ai_draft",
        resource_type="compliance_notice",
        resource_id=notice_id,
        details=details,
    )


def draft_response_for_notice(
    db: Session,
    *,
    notice: ComplianceNotice,
    user_id: int | None,
    user_guidance: str = "",
) -> dict[str, Any]:
    """Generate a Markdown response draft for `notice`.

    Returns:
        {
            "draft_body_markdown": str,
            "model": "<provider>:<model>",
            "tokens_in": int,
            "tokens_out": int,
            "latency_ms": int,
            "extracted_fields_used": [str],
        }

    Raises:
        ResponseDraftCredentialMissingError: tenant has no AICredential.
        ai_service.AIOutOfScopeError: provider returned OUT_OF_SCOPE.
        AIAuthError / AIRateLimitError / AIProviderError: provider transport
        errors.
    """
    # Truncate guidance up front so the same value the prompt sees is the
    # value we hash for audit. Prevents downstream "audit hash does not
    # match prompt" drift if a future prompt revision changes the cap.
    guidance = (user_guidance or "")[:MAX_GUIDANCE_CHARS]
    guidance_sha = _sha256_text(guidance)

    cred = ai_service.resolve_credential(db, client_id=notice.client_id)
    if cred is None:
        raise ResponseDraftCredentialMissingError(
            "No AI credential configured for this tenant"
        )

    provider = ai_service._build_active_provider(db, cred)
    started = time.monotonic()

    extracted_fields = notice.extracted_fields or {}
    fields_dict = extracted_fields.get("fields") if isinstance(extracted_fields, dict) else None
    extracted_field_keys = sorted(fields_dict.keys()) if isinstance(fields_dict, dict) else []

    user_prompt = build_user_prompt(notice=notice, user_guidance=guidance)

    try:
        raw_text = ai_service._run(provider, user_prompt, max_tokens=MAX_RESPONSE_TOKENS)
    except (AIAuthError, AIRateLimitError, AIProviderError) as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        _write_audit(
            user_id=user_id,
            notice_id=notice.id,
            provider_name=cred.provider,
            model=cred.model,
            tokens_in=len(user_prompt),
            tokens_out=0,
            latency_ms=elapsed_ms,
            body_sha256=_sha256_text(""),
            guidance_sha256=guidance_sha,
            extracted_fields_used=extracted_field_keys,
            failure=f"{type(exc).__name__}: {exc}",
        )
        raise

    elapsed_ms = int((time.monotonic() - started) * 1000)
    draft_body = (raw_text or "").strip()

    _write_audit(
        user_id=user_id,
        notice_id=notice.id,
        provider_name=cred.provider,
        model=cred.model,
        tokens_in=len(user_prompt),
        tokens_out=len(draft_body),
        latency_ms=elapsed_ms,
        body_sha256=_sha256_text(draft_body),
        guidance_sha256=guidance_sha,
        extracted_fields_used=extracted_field_keys,
    )

    return {
        "draft_body_markdown": draft_body,
        "model": f"{cred.provider}:{cred.model}",
        "tokens_in": len(user_prompt),
        "tokens_out": len(draft_body),
        "latency_ms": elapsed_ms,
        "extracted_fields_used": extracted_field_keys,
    }
