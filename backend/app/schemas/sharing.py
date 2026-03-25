"""Pydantic schemas for document sharing."""

import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class ShareDocumentRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    permission: str = Field("view", pattern="^(view|edit)$")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()


class DocumentPermissionResponse(BaseModel):
    id: int
    document_id: int
    user_id: int
    user_email: str
    user_name: str
    permission: str
    granted_by: int | None = None
    created_at: datetime

    class Config:
        from_attributes = True
