"""Pydantic schemas for document sharing."""

from datetime import datetime
from pydantic import BaseModel, Field


class ShareDocumentRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=255)
    permission: str = Field("view", pattern="^(view|edit)$")


class DocumentPermissionResponse(BaseModel):
    id: int
    document_id: int
    user_id: int
    user_email: str
    user_name: str
    permission: str
    granted_by: int
    created_at: datetime

    class Config:
        from_attributes = True
