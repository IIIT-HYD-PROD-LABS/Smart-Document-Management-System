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
    """Each adapter exposes two methods.

    `complete(system, user)` is the one-shot helper used by the per-page
    summaries and action lists.

    `chat(system, messages)` is the multi-turn variant used by the
    sidebar chat drawer. Messages must be an alternating user/assistant
    list ending on a user turn — the adapter does NOT validate this; the
    caller is responsible.

    Both are synchronous because FastAPI request handlers run blocking
    work on a threadpool, and the AI surface is one-shot (no streaming
    for v1).
    """

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        max_tokens: int = 1024,
    ) -> str:
        ...

    @abstractmethod
    def chat(
        self,
        system: str,
        messages: list[dict],
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

    def _send(self, system: str, messages: list[dict], max_tokens: int) -> str:
        """Shared helper used by both `complete` and `chat`."""
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
                messages=messages,
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

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        return self._send(system, [{"role": "user", "content": user}], max_tokens)

    def chat(
        self, system: str, messages: list[dict], max_tokens: int = 1024
    ) -> str:
        return self._send(system, messages, max_tokens)


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

    @staticmethod
    def _to_gemini_contents(messages: list[dict]) -> list[dict]:
        """Map our `{role: 'user'|'assistant', content: str}` shape to
        Gemini's `{role: 'user'|'model', parts: [{text}]}` schema."""
        out = []
        for m in messages:
            role = "model" if m.get("role") == "assistant" else "user"
            out.append({"role": role, "parts": [{"text": m.get("content", "")}]})
        return out

    def _send(
        self, system: str, contents: list[dict], max_tokens: int
    ) -> str:
        """Shared helper used by both `complete` and `chat`.

        The API key goes in the `x-goog-api-key` header rather than the
        URL query string (Google supports both). URLs end up in proxy
        logs, error messages, and trace exporters; secrets in headers
        are far less likely to leak.
        """
        url = f"{self._BASE}/{self._model}:generateContent"
        payload = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": max_tokens,
            },
        }
        try:
            r = httpx.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self._api_key},
                timeout=30.0,
            )
        except httpx.RequestError as e:
            raise AIProviderError(f"gemini request failed: {e}") from e

        if r.status_code in (401, 403):
            raise AIAuthError(f"gemini auth failed: {r.text[:200]}")
        if r.status_code == 429:
            raise AIRateLimitError(f"gemini rate-limited: {r.text[:200]}")
        if r.status_code == 404:
            # Most common 404 cause: the stored model name was retired
            # by Google (e.g., gemini-1.5-flash → gemini-2.5-flash).
            # Surface a user-actionable message instead of a raw dump.
            raise AIProviderError(
                f"Model '{self._model}' is not available on Google's API. "
                "Update the model name in Settings → AI (current generation: "
                "gemini-2.5-flash, gemini-2.5-pro, gemini-2.5-flash-lite)."
            )
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

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        return self._send(
            system,
            [{"role": "user", "parts": [{"text": user}]}],
            max_tokens,
        )

    def chat(
        self, system: str, messages: list[dict], max_tokens: int = 1024
    ) -> str:
        return self._send(system, self._to_gemini_contents(messages), max_tokens)


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
