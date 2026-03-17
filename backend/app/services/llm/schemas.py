"""Pydantic schemas for LLM-based document extraction."""

from pydantic import BaseModel, Field
from typing import Union


class ExtractedField(BaseModel):
    """A single extracted data field with confidence score."""

    value: Union[str, float, list, None] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_hint: str | None = None


class DocumentExtraction(BaseModel):
    """Structured extraction result from LLM or regex fallback."""

    dates: list[ExtractedField] = Field(default_factory=list)
    amounts: list[ExtractedField] = Field(default_factory=list)
    parties: list[ExtractedField] = Field(default_factory=list)
    key_terms: list[ExtractedField] = Field(default_factory=list)
    summary: str = ""
    overall_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
