"""Core extraction service -- orchestrates LLM calls with structured output and regex fallback."""

from __future__ import annotations

import structlog

from app.services.llm.prompts import get_extraction_prompt
from app.services.llm.schemas import DocumentExtraction, ExtractedField

logger = structlog.stdlib.get_logger()

# Truncate documents beyond this limit to stay within context windows
MAX_CHARS = 50_000


def extract_with_llm(
    text: str,
    category: str,
    provider: str,
    api_key: str,
    model_name: str | None = None,
) -> DocumentExtraction:
    """Extract structured data from document text using an LLM.

    Calls the specified LLM provider via instructor for structured output.
    Falls back to regex-based extraction on any LLM error.

    Args:
        text: Raw document text.
        category: Document category (e.g. "invoices", "tax", "bills").
        provider: LLM provider name ("gemini", "openai", "anthropic").
        api_key: API key for the provider.
        model_name: Optional model override.

    Returns:
        DocumentExtraction with fields, confidence scores, and summary.
    """
    if not text or not text.strip():
        logger.warning("extraction_empty_text", category=category)
        return DocumentExtraction()

    # Truncate silently to fit context windows
    if len(text) > MAX_CHARS:
        logger.info(
            "extraction_text_truncated",
            original_len=len(text),
            truncated_to=MAX_CHARS,
        )
        text = text[:MAX_CHARS]

    try:
        from app.services.llm.provider import get_llm_client

        client, model = get_llm_client(provider, api_key, model_name)

        system_prompt = get_extraction_prompt(category)

        result = client.chat.completions.create(
            response_model=DocumentExtraction,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Document text:\n\n{text}"},
            ],
            model=model,
        )

        logger.info(
            "extraction_llm_success",
            provider=provider,
            model=model,
            category=category,
            dates_count=len(result.dates),
            amounts_count=len(result.amounts),
            parties_count=len(result.parties),
            overall_confidence=result.overall_confidence,
        )
        return result

    except Exception as exc:
        logger.warning(
            "extraction_llm_failed_using_fallback",
            provider=provider,
            category=category,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return _fallback_extraction(text)


def _fallback_extraction(text: str) -> DocumentExtraction:
    """Regex-based fallback using the existing metadata extractor.

    Returns a DocumentExtraction with confidence=0.3 for all regex-matched fields
    and an empty summary (regex cannot summarize).
    """
    from app.ml.metadata_extractor import extract_metadata

    meta = extract_metadata(text)
    fallback_confidence = 0.3

    dates = [
        ExtractedField(value=d, confidence=fallback_confidence, source_hint="regex")
        for d in meta.get("dates", [])
    ]

    amounts = [
        ExtractedField(
            value=a["amount"],
            confidence=fallback_confidence,
            source_hint="regex",
        )
        for a in meta.get("amounts", [])
    ]

    vendor = meta.get("vendor")
    parties = []
    if vendor:
        parties.append(
            ExtractedField(
                value=vendor,
                confidence=fallback_confidence,
                source_hint="regex",
            )
        )

    logger.info(
        "extraction_fallback_complete",
        dates_count=len(dates),
        amounts_count=len(amounts),
        parties_count=len(parties),
    )

    return DocumentExtraction(
        dates=dates,
        amounts=amounts,
        parties=parties,
        key_terms=[],
        summary="",
        overall_confidence=fallback_confidence if (dates or amounts or parties) else 0.0,
    )
