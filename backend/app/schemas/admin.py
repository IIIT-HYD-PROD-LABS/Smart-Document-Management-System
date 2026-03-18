"""Pydantic schemas for Admin API routes."""

from datetime import datetime
from pydantic import BaseModel, Field


class AdminUserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str | None
    role: str
    is_active: bool
    auth_provider: str
    document_count: int
    created_at: datetime
    updated_at: datetime | None

    class Config:
        from_attributes = True


class AdminUserListResponse(BaseModel):
    users: list[AdminUserResponse]
    total: int
    page: int = 1
    per_page: int = 20


class RoleUpdateRequest(BaseModel):
    role: str = Field(..., pattern="^(admin|editor|viewer)$")


class StatusUpdateRequest(BaseModel):
    is_active: bool


class AdminStatsResponse(BaseModel):
    total_users: int
    active_users: int
    users_by_role: dict[str, int]
    total_documents: int
    documents_by_status: dict[str, int]
