"""LLM-based document extraction and summarization service.

Supports Ollama (local), Google Gemini (free tier), Anthropic Claude, OpenAI GPT, and a regex fallback.
"""

import json
import structlog
from abc import ABC, abstractmethod

from app.config import settings

logger = structlog.stdlib.get_logger()

# Category-specific extraction prompts
CATEGORY_FIELDS = {
    "bills": ["bill_number", "billing_date", "due_date", "total_amount", "vendor", "account_number"],
    "invoices": ["invoice_number", "invoice_date", "due_date", "total_amount", "vendor", "line_items"],
    "tax": ["form_type", "assessment_year", "taxpayer_name", "pan_number", "total_income", "tax_payable"],
    "bank": ["account_number", "bank_name", "statement_period", "opening_balance", "closing_balance"],
    "upi": ["transaction_id", "sender", "receiver", "amount", "date", "upi_id"],
    "tickets": ["event_name", "date", "venue", "seat_number", "ticket_price", "booking_id"],
    "unknown": ["dates", "amounts", "parties", "key_terms"],
}

SYSTEM_PROMPT = """You are a document data extraction assistant. Extract structured information from the given document text.

Rules:
- Return ONLY valid JSON, no markdown or explanation.
- For each extracted field, include a "confidence" score from 0.0 to 1.0.
- If a field is not found in the text, omit it from the output.
- Extract dates in ISO 8601 format (YYYY-MM-DD).
- Extract monetary amounts as numbers with currency code.
- Be precise — only extract information explicitly stated in the text."""


def _build_extraction_prompt(text: str, category: str) -> str:
    fields = CATEGORY_FIELDS.get(category, CATEGORY_FIELDS["unknown"])
    fields_str = ", ".join(fields)
    return f"""Extract the following fields from this {category} document: {fields_str}

Return a JSON object with this structure:
{{
  "fields": {{
    "<field_name>": {{"value": "<extracted_value>", "confidence": 0.95}},
    ...
  }},
  "summary": "A concise one-paragraph summary of this document."
}}

Document text:
---
{text[:4000]}
---"""


def _parse_llm_response(raw: str | None) -> dict:
    """Parse JSON from LLM response, handling markdown code blocks and edge cases."""
    if not raw:
        raise ValueError("LLM returned empty response")
    text = raw.strip()
    if not text:
        raise ValueError("LLM returned whitespace-only response")
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()
    if not text:
        raise ValueError("LLM response contained only code fences")
    return json.loads(text)


class LLMProvider(ABC):
    @abstractmethod
    def extract(self, text: str, category: str) -> dict:
        """Returns {"fields": {...}, "summary": "..."}"""


class AnthropicProvider(LLMProvider):
    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.LLM_MODEL or "claude-sonnet-4-20250514"

    def extract(self, text: str, category: str) -> dict:
        message = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _build_extraction_prompt(text, category)}],
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        return _parse_llm_response(message.content[0].text)


class OpenAIProvider(LLMProvider):
    def __init__(self):
        from openai import OpenAI
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.LLM_MODEL or "gpt-4o-mini"

    def extract(self, text: str, category: str) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _build_extraction_prompt(text, category)},
            ],
            max_tokens=1024,
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        return _parse_llm_response(response.choices[0].message.content)


class OllamaProvider(LLMProvider):
    """Uses a local Ollama instance — free, no API keys needed."""

    def __init__(self):
        import httpx
        self.client = httpx
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.LLM_MODEL or "llama3.2"

    def extract(self, text: str, category: str) -> dict:
        import httpx
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": _build_extraction_prompt(text, category)},
                ],
                "stream": False,
                "options": {"temperature": 0.1},
            },
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content")
        if not content:
            raise ValueError(f"Ollama returned unexpected response structure: {list(data.keys())}")
        return _parse_llm_response(content)


class GeminiProvider(LLMProvider):
    """Uses Google Gemini API — generous free tier (15 RPM, 1M tokens/day)."""

    def __init__(self):
        import httpx
        self.client = httpx
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.LLM_MODEL or "gemini-2.0-flash"

    def extract(self, text: str, category: str) -> dict:
        import httpx
        prompt = SYSTEM_PROMPT + "\n\n" + _build_extraction_prompt(text, category)
        response = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            headers={"x-goog-api-key": self.api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
            },
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        try:
            content = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as e:
            # Gemini may return blocked responses, empty candidates, or safety filters
            raise ValueError(f"Gemini returned unexpected response structure: {e}") from e
        return _parse_llm_response(content)


class LocalProvider(LLMProvider):
    """Fallback: wraps the existing regex metadata extractor as structured output."""

    def extract(self, text: str, category: str) -> dict:
        from app.ml.metadata_extractor import extract_metadata
        meta = extract_metadata(text) if text else {}
        fields = {}
        if meta.get("dates"):
            fields["dates"] = {"value": meta["dates"], "confidence": 0.6}
        if meta.get("amounts"):
            fields["amounts"] = {"value": meta["amounts"], "confidence": 0.6}
        if meta.get("vendor"):
            fields["vendor"] = {"value": meta["vendor"], "confidence": 0.5}
        summary = f"Document classified as {category}."
        if meta.get("vendor"):
            summary += f" From {meta['vendor']}."
        if meta.get("amounts"):
            amounts = [a.get("amount", a) if isinstance(a, dict) else a for a in meta["amounts"]]
            summary += f" Amount(s): {', '.join(str(a) for a in amounts)}."
        return {"fields": fields, "summary": summary}


def _get_provider_chain() -> list[tuple[str, LLMProvider]]:
    """Build ordered list of providers to try. First success wins."""
    provider = settings.LLM_PROVIDER.lower()
    chain: list[tuple[str, LLMProvider]] = []

    if provider == "ollama+gemini" or provider == "ollama":
        chain.append(("ollama", OllamaProvider()))
    if provider == "ollama+gemini" or provider == "gemini":
        if settings.GEMINI_API_KEY:
            chain.append(("gemini", GeminiProvider()))
    if provider == "anthropic" and settings.ANTHROPIC_API_KEY:
        chain.append(("anthropic", AnthropicProvider()))
    if provider == "openai" and settings.OPENAI_API_KEY:
        chain.append(("openai", OpenAIProvider()))

    # Always have local as final fallback
    chain.append(("local", LocalProvider()))
    return chain


def _sanitize_error(error: str) -> str:
    """Remove potential API keys/tokens from error messages before logging."""
    import re
    # Redact long hex/base64 strings that look like API keys (32+ chars)
    sanitized = re.sub(r'[A-Za-z0-9_\-]{32,}', '***REDACTED***', error)
    # Redact query parameters that typically carry keys
    sanitized = re.sub(r'(key|token|secret|password|api_key)=[^&\s]+', r'\1=***', sanitized, flags=re.IGNORECASE)
    return sanitized


def extract_with_llm(text: str, category: str) -> dict:
    """Try providers in order. First success wins, failures fall through."""
    chain = _get_provider_chain()

    for provider_name, provider in chain:
        try:
            result = provider.extract(text, category)
            result["provider"] = provider_name
            logger.info("llm_extraction_success", provider=provider_name)
            return result
        except json.JSONDecodeError:
            logger.warning("llm_json_parse_failed", provider=provider_name)
        except Exception as e:
            logger.warning("llm_provider_failed", provider=provider_name, error=_sanitize_error(str(e)))

    # Should never reach here since LocalProvider doesn't fail, but just in case
    return LocalProvider().extract(text, category)
