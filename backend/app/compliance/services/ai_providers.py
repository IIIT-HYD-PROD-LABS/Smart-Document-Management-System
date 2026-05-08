"""Provider adapters for BYOK AI — Phase 16.

Single tiny interface (`AIProvider.complete(system, user) -> str`) backed
by two concrete adapters:

  - `AnthropicProvider`  — uses the official `anthropic` SDK (already a
                           dep, used elsewhere in the codebase).
  - `GoogleProvider`     — uses raw `httpx` against the Generative
                           Language REST API (no extra package needed).

Both adapters surface the same exception hierarchy so the service layer
doesn't have to special-case providers:
  - `AIAuthError`          → key invalid or expired (HTTP 401/403)
  - `AIRateLimitError`     → provider rate limit hit  (HTTP 429)
  - `AIProviderError`      → anything else (timeout, 5xx, malformed body)

The output is plain text. Markdown / JSON parsing happens in `ai_service`.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────
# Exceptions
# ─────────────────────────────────────────────────────────────────────


class AIProviderError(Exception):
    """Any non-auth, non-rate-limit failure talking to the provider."""


class AIAuthError(AIProviderError):
    """Provider rejected the key (401/403)."""


class AIRateLimitError(AIProviderError):
    """Provider returned 429."""


# ─────────────────────────────────────────────────────────────────────
# Interface
# ─────────────────────────────────────────────────────────────────────


class AIProvider(ABC):
    """Each adapter exposes a single `complete` method. We keep it
    synchronous because the FastAPI request handlers are already running
    on a threadpool for blocking work, and the AI surface is one-shot
    (no streaming for v1)."""

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
    ) -> str:
        ...


# ─────────────────────────────────────────────────────────────────────
# Anthropic
# ─────────────────────────────────────────────────────────────────────


class AnthropicProvider(AIProvider):
    def __init__(self, api_key: str, model: str):
        from anthropic import Anthropic  # local import — keeps cold start fast

        self._client = Anthropic(api_key=api_key, timeout=30.0)
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        try:
            from anthropic import (  # noqa: F401 — type imports only
                APIStatusError,
                AuthenticationError,
                RateLimitError,
            )
        except ImportError:
            APIStatusError = AuthenticationError = RateLimitError = Exception

        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except AuthenticationError as e:
            raise AIAuthError(str(e)) from e
        except RateLimitError as e:
            raise AIRateLimitError(str(e)) from e
        except APIStatusError as e:
            raise AIProviderError(str(e)) from e
        except Exception as e:  # noqa: BLE001 — surface as provider error
            raise AIProviderError(f"anthropic call failed: {e}") from e

        # `resp.content` is a list of content blocks; we want the first
        # text block. Older SDK versions used `resp.content[0].text`; this
        # is stable on 0.52.x.
        if not resp.content:
            raise AIProviderError("empty response from anthropic")
        first = resp.content[0]
        text = getattr(first, "text", None)
        if text is None:
            raise AIProviderError(
                f"unexpected content block type: {type(first).__name__}"
            )
        return text


# ─────────────────────────────────────────────────────────────────────
# Google Gemini  (REST)
# ─────────────────────────────────────────────────────────────────────


class GoogleProvider(AIProvider):
    """Hits Google's Generative Language REST API via httpx — avoids
    pulling in google-generativeai (~ 30 MB transitive). The endpoint
    schema is from the v1beta `generateContent` route, which has been
    stable for the Gemini family since 1.0."""

    _BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str, model: str):
        self._api_key = api_key
        self._model = model

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        url = f"{self._BASE}/{self._model}:generateContent?key={self._api_key}"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [
                {"role": "user", "parts": [{"text": user}]},
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": max_tokens,
            },
        }
        try:
            r = httpx.post(url, json=payload, timeout=30.0)
        except httpx.RequestError as e:
            raise AIProviderError(f"gemini request failed: {e}") from e

        if r.status_code in (401, 403):
            raise AIAuthError(f"gemini auth failed: {r.text[:200]}")
        if r.status_code == 429:
            raise AIRateLimitError(f"gemini rate-limited: {r.text[:200]}")
        if r.status_code >= 400:
            raise AIProviderError(
                f"gemini http {r.status_code}: {r.text[:300]}"
            )

        try:
            body = r.json()
        except ValueError as e:
            raise AIProviderError(f"gemini returned non-JSON: {e}") from e

        candidates = body.get("candidates") or []
        if not candidates:
            raise AIProviderError(f"gemini empty candidates: {body}")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        if not parts or "text" not in parts[0]:
            raise AIProviderError(f"gemini missing text part: {body}")
        return parts[0]["text"]


# ─────────────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────────────


def build_provider(provider: str, api_key: str, model: str) -> AIProvider:
    """Return an adapter for the given provider name. Raises ValueError
    for unknown providers — the DB CHECK constraint and Pydantic Literal
    should make this unreachable in practice."""
    if provider == "anthropic":
        return AnthropicProvider(api_key=api_key, model=model)
    if provider == "google":
        return GoogleProvider(api_key=api_key, model=model)
    raise ValueError(f"unknown AI provider: {provider!r}")
