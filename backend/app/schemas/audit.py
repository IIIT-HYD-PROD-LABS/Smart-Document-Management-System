"""Pydantic schemas for Audit Log API routes."""

from datetime import datetime
from pydantic import ConfigDict, BaseModel


class AuditLogResponse(BaseModel):
    id: int
    user_id: int | None = None
    action: str
    resource_type: str | None = None
    resource_id: int | None = None
    details: dict | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total: int
    page: int = 1
    per_page: int = 50
