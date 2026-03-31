"""Pydantic schemas for Early Access requests."""

import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class EarlyAccessSubmit(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=200)
    email: str = Field(..., min_length=5, max_length=255)
    company: str | None = Field(None, max_length=200)
    reason: str | None = Field(None, max_length=1000)

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()

    @field_validator("full_name")
    @classmethod
    def sanitize_name(cls, v: str) -> str:
        sanitized = re.sub(r'<[^>]*>', '', v)
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', sanitized)
        return sanitized.strip()


class EarlyAccessResponse(BaseModel):
    id: int
    full_name: str
    email: str
    company: str | None
    reason: str | None
    status: str
    admin_note: str | None
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by: int | None

    class Config:
        from_attributes = True


class EarlyAccessListResponse(BaseModel):
    items: list[EarlyAccessResponse]
    total: int
    page: int
    per_page: int


class EarlyAccessReviewRequest(BaseModel):
    status: str = Field(..., pattern=r"^(approved|rejected)$")
    admin_note: str | None = Field(None, max_length=500)
