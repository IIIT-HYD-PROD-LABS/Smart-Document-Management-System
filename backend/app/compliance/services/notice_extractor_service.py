"""Notice field extractor — Phase 17 D-01, D-13, D-16.

`extract_notice_fields` is the single entry point.  It:

  1. Resolves the tenant's BYOK credential via Phase 16 `get_credential`.
     Raises `NoticeExtractionCredentialMissingError` (mapped to HTTP 412)
     when no credential is configured (D-14).
  2. Builds the provider via Phase 16 `build_provider`, calls
     `provider.complete(SCOPE_LOCK_SYSTEM, build_user_prompt(text))`,
     parses the JSON envelope, drops fields not in `FIELD_SCHEMA`,
     and computes a raw average over returned-field confidences.
  3. Runs the structural validator (D-33) to halve confidence on
     shape failures and annotate `validation_failure` per field.
  4. Writes one immutable audit row (`action='notice_ai_extract'`) with
     PII-redacted args (provider, model, token counts, latency, average
     confidence, body SHA-256, list of returned field KEYS — never values).
  5. Returns the envelope shaped per `ExtractionEnvelope`.

Notice persistence is NOT done here.  Routing + write-to-notice live in
`extraction_routing_service` and the caller (router or Celery task).
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.compliance.services import ai_service
from app.compliance.services.ai_providers import (
    AIAuthError,
    AIProviderError,
    AIRateLimitError,
)
from app.compliance.services.notice_extraction_prompt import (
    EXTRACTION_SYSTEM_PROMPT,
    FIELD_SCHEMA,
    MAX_TEXT_WINDOW,
    build_user_prompt,
)
from app.compliance.services.notice_extraction_validator import validate_and_score
from app.services.audit_service import log_audit_event_strict


logger = logging.getLogger(__name__)


# Re-export Phase 16 exceptions so callers can import everything they need
# from this module (matches the ai_service convention).
__all__ = [
    "AIAuthError",
    "AIProviderError",
    "AIRateLimitError",
    "NoticeExtractionCredentialMissingError",
    "NoticeExtractionParseError",
    "extract_notice_fields",
    "extract_notice_fields_async",
]


class NoticeExtractionCredentialMissingError(Exception):
    """Tenant has no AICredential row — router maps to HTTP 412 (D-14)."""


class NoticeExtractionParseError(Exception):
    """Provider returned a body that could not be parsed as the expected envelope."""


def _run_extraction(provider, user_prompt: str, max_tokens: int) -> str:
    """Call the provider with the dedicated EXTRACTION_SYSTEM_PROMPT.

    Deliberately does NOT go through ai_service._run (which pins the chat
    scope-lock prompt and raises AIOutOfScopeError on the OUT_OF_SCOPE
    sentinel). Extraction must never refuse a document the user explicitly
    uploaded — see notice_extraction_prompt for the full rationale.
    """
    raw = provider.complete(EXTRACTION_SYSTEM_PROMPT, user_prompt, max_tokens=max_tokens)
    return (raw or "").strip()


def _sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="ignore")).hexdigest()


def _filter_to_schema(fields: dict) -> dict:
    """Drop any keys the model invented; keep only canonical FIELD_SCHEMA names (D-04)."""
    if not isinstance(fields, dict):
        return {}
    return {name: payload for name, payload in fields.items() if name in FIELD_SCHEMA}


_DEFAULT_FIELD_CONFIDENCE = 0.7


def _normalize_fields(fields: dict) -> dict:
    """Coerce each field into the {value, confidence} object the envelope schema
    (ExtractedField) requires, regardless of how the provider shaped it.

    Small/local models (e.g. Ollama llama3.2) are inconsistent: they often
    return a FLAT mapping ({"notice_number": "DRC-01/..."}) instead of the
    nested {"notice_number": {"value": ..., "confidence": ...}} envelope, and
    routinely omit per-field confidence. Without this, flat scalars fail FastAPI
    response validation (HTTP 500) and missing confidences collapse the average
    to 0.0 so every field routes to "review" and the form looks empty. This
    wraps bare scalars and backfills a sensible default confidence so ANY
    provider's output is usable and renders pre-filled.
    """
    out: dict = {}
    for name, payload in (fields or {}).items():
        if isinstance(payload, dict):
            raw_conf = payload.get("confidence")
            try:
                conf = float(raw_conf)
            except (TypeError, ValueError):
                conf = _DEFAULT_FIELD_CONFIDENCE
            conf = min(1.0, max(0.0, conf))
            obj = {"value": payload.get("value"), "confidence": conf}
            if payload.get("source_span") is not None:
                obj["source_span"] = payload["source_span"]
            out[name] = obj
        else:
            # Flat scalar/list value (the common small-model shape): wrap it.
            out[name] = {"value": payload, "confidence": _DEFAULT_FIELD_CONFIDENCE}
    return out


def _raw_average(fields: dict) -> float:
    if not fields:
        return 0.0
    confidences: list[float] = []
    for payload in fields.values():
        if not isinstance(payload, dict):
            continue
        try:
            confidences.append(float(payload.get("confidence") or 0.0))
        except (TypeError, ValueError):
            continue
    if not confidences:
        return 0.0
    return round(sum(confidences) / len(confidences), 4)


def _write_audit(
    *,
    user_id: int | None,
    notice_id: int | None,
    provider_name: str,
    model: str,
    average_confidence: float,
    tokens_in: int,
    tokens_out: int,
    latency_ms: int,
    body_sha256: str,
    field_keys: list[str],
    failure: Optional[str] = None,
) -> None:
    """One audit row per extract attempt — PII-redacted per D-16.

    Field VALUES are never recorded. Only the list of returned keys.
    """
    details = {
        "provider": provider_name,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": latency_ms,
        "average_confidence": average_confidence,
        "fields_returned": field_keys,
        "body_sha256": body_sha256,
    }
    if failure:
        details["failure"] = failure
    log_audit_event_strict(
        user_id=user_id,
        action="notice_ai_extract",
        resource_type="compliance_notice",
        resource_id=notice_id,
        details=details,
    )


def extract_notice_fields(
    db: Session,
    *,
    client_id: int,
    user_id: int | None,
    text: str,
    notice_id: int | None = None,
) -> dict:
    """Run extraction and return the envelope (sync — Session).

    Stays sync: app/tasks/document_tasks.py (Celery) calls this with a sync
    Session. Router callers use `extract_notice_fields_async` instead.

    Raises:
        NoticeExtractionCredentialMissingError: tenant has no AICredential.
        AIAuthError / AIRateLimitError /
        AIProviderError:                        provider transport errors.
        NoticeExtractionParseError:             provider response unparseable.
    """
    cred = ai_service.resolve_credential(db, client_id=client_id)
    if cred is None:
        raise NoticeExtractionCredentialMissingError(
            "No AI credential configured for this tenant"
        )

    provider = ai_service._build_active_provider(db, cred)
    return _extract_notice_fields_impl(
        provider, cred, user_id=user_id, notice_id=notice_id, text=text
    )


async def extract_notice_fields_async(
    db: AsyncSession,
    *,
    client_id: int,
    user_id: int | None,
    text: str,
    notice_id: int | None = None,
) -> dict:
    """Async twin of `extract_notice_fields`, for the router call chain."""
    cred = await ai_service.resolve_credential_async(db, client_id=client_id)
    if cred is None:
        raise NoticeExtractionCredentialMissingError(
            "No AI credential configured for this tenant"
        )

    provider = await ai_service._build_active_provider_async(db, cred)
    return _extract_notice_fields_impl(
        provider, cred, user_id=user_id, notice_id=notice_id, text=text
    )


def _extract_notice_fields_impl(
    provider,
    cred,
    *,
    user_id: int | None,
    notice_id: int | None,
    text: str,
) -> dict:
    """Shared (no-db) extraction logic used by the sync/async entry points."""
    body_sha = _sha256_text(text or "")
    started = time.monotonic()

    try:
        raw_text = _run_extraction(provider, build_user_prompt(text), max_tokens=2048)
    except (AIAuthError, AIRateLimitError, AIProviderError) as exc:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        _write_audit(
            user_id=user_id,
            notice_id=notice_id,
            provider_name=cred.provider,
            model=cred.model,
            average_confidence=0.0,
            tokens_in=0,
            tokens_out=0,
            latency_ms=elapsed_ms,
            body_sha256=body_sha,
            field_keys=[],
            failure=f"{type(exc).__name__}: {exc}",
        )
        raise

    elapsed_ms = int((time.monotonic() - started) * 1000)
    parsed = ai_service._parse_json_or_default(raw_text, {})

    # Defensive: the extraction prompt instructs the model NOT to refuse, but a
    # model could still echo the legacy refusal sentinel as bare text. Treat that
    # as "no notice fields found" — an empty (manual-fill) envelope, never a hard
    # error — so a misfire degrades gracefully instead of a scary 502/422.
    if (
        not (isinstance(parsed, dict) and isinstance(parsed.get("fields"), dict))
        and raw_text == ai_service.OUT_OF_SCOPE_SENTINEL
    ):
        parsed = {"fields": {}}

    if not isinstance(parsed, dict) or not isinstance(parsed.get("fields"), dict):
        _write_audit(
            user_id=user_id,
            notice_id=notice_id,
            provider_name=cred.provider,
            model=cred.model,
            average_confidence=0.0,
            tokens_in=min(len(text or ""), MAX_TEXT_WINDOW),
            tokens_out=len(raw_text or ""),
            latency_ms=elapsed_ms,
            body_sha256=body_sha,
            field_keys=[],
            failure="envelope_parse_failure",
        )
        raise NoticeExtractionParseError(
            "Provider response could not be parsed as a fields envelope"
        )

    fields = _normalize_fields(_filter_to_schema(parsed["fields"]))
    raw_avg = _raw_average(fields)

    envelope = {
        "fields": fields,
        "average_confidence": raw_avg,
        "model": f"{cred.provider}:{cred.model}",
        # Token counts are approximated from char length — the provider
        # SDKs do not surface true token counts uniformly across Anthropic
        # and Gemini, and we only need a coarse signal for cost telemetry.
        "tokens_in": min(len(text or ""), MAX_TEXT_WINDOW),
        "tokens_out": len(raw_text or ""),
        "latency_ms": elapsed_ms,
    }

    envelope = validate_and_score(envelope)

    _write_audit(
        user_id=user_id,
        notice_id=notice_id,
        provider_name=cred.provider,
        model=cred.model,
        average_confidence=envelope["average_confidence"],
        tokens_in=envelope["tokens_in"],
        tokens_out=envelope["tokens_out"],
        latency_ms=envelope["latency_ms"],
        body_sha256=body_sha,
        field_keys=sorted(envelope["fields"].keys()),
    )

    return envelope
