"""Pydantic schemas for LLM settings API."""

from pydantic import BaseModel, Field


class LLMSettingsResponse(BaseModel):
    """Response schema for GET /api/settings/llm."""

    llm_provider: str = "gemini"
    model_name: str | None = None
    api_key_set: bool = False
    api_key_last4: str | None = None
    ollama_base_url: str | None = None


class LLMSettingsUpdate(BaseModel):
    """Request schema for PUT /api/settings/llm."""

    llm_provider: str = Field("gemini", pattern="^(gemini|openai|anthropic|local)$")
    model_name: str | None = None
    api_key: str | None = Field(None, min_length=10)
    ollama_base_url: str | None = None
