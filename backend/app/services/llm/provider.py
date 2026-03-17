"""LLM provider factory -- returns instructor-patched clients for Gemini, OpenAI, and Anthropic."""

from __future__ import annotations

from typing import Any
import structlog

logger = structlog.stdlib.get_logger()


def get_llm_client(
    provider: str,
    api_key: str,
    model_name: str | None = None,
) -> tuple[Any, str]:
    """Create an instructor-patched LLM client for the given provider.

    Args:
        provider: One of "gemini", "openai", "anthropic".
        api_key: The API key for the provider.
        model_name: Optional model override. Defaults vary by provider.

    Returns:
        Tuple of (instructor_client, model_string).

    Raises:
        ValueError: If provider is unknown.
    """
    import instructor  # lazy import -- only needed when LLM is used

    if provider == "gemini":
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = model_name or "gemini-2.0-flash"
        client = instructor.from_gemini(
            genai.GenerativeModel(model),
            mode=instructor.Mode.GEMINI_JSON,
        )
        logger.info("llm_client_created", provider=provider, model=model)
        return client, model

    elif provider == "openai":
        from openai import OpenAI

        client = instructor.from_openai(OpenAI(api_key=api_key))
        model = model_name or "gpt-4o-mini"
        logger.info("llm_client_created", provider=provider, model=model)
        return client, model

    elif provider == "anthropic":
        from anthropic import Anthropic

        client = instructor.from_anthropic(Anthropic(api_key=api_key))
        model = model_name or "claude-haiku-4-5-20251001"
        logger.info("llm_client_created", provider=provider, model=model)
        return client, model

    else:
        raise ValueError(
            f"Unknown LLM provider '{provider}'. "
            f"Supported providers: gemini, openai, anthropic"
        )
