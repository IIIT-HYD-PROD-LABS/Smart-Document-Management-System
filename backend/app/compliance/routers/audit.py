"""Audit log viewer router — Phase 9 AUDIT-01 (read-only by design).

GET /audit — query the immutable audit_logs table with filters.

There is NO POST/PUT/DELETE on this router. AUDIT-01 / AUDIT-02:
audit_logs is append-only at the DB level (trigger + REVOKE on app_runtime
in migration 0014/0017). This router exposes a read-only viewer; the rows
are populated by log_audit_event calls inside service layers and routers.

Permission: AUDIT_VIEW (auditor only per the registry — even compliance_head
does NOT have it; the audit log is the auditor's domain).
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_async_db
from app.models.audit_log import AuditLog


router = APIRouter(prefix="/audit", tags=["compliance-audit"])


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: Optional[int] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    details: Optional[dict] = None
    ip_address: Optional[str] = None
    created_at: datetime


@router.get("", response_model=List[AuditLogOut])
async def list_audit(
    date_from: Optional[datetime] = Query(None),
    date_to: Optional[datetime] = Query(None),
    actor_user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    resource_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    _gate: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.AUDIT_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """Read-only audit log viewer — AUDIT-01.

    DB-level immutability (trigger + REVOKE) ensures rows cannot be edited
    via UI or API regardless of any future code change in this layer.
    """
    q = select(AuditLog)
    if date_from is not None:
        q = q.where(AuditLog.created_at >= date_from)
    if date_to is not None:
        q = q.where(AuditLog.created_at <= date_to)
    if actor_user_id is not None:
        q = q.where(AuditLog.user_id == actor_user_id)
    if action:
        q = q.where(AuditLog.action == action)
    if resource_type:
        q = q.where(AuditLog.resource_type == resource_type)
    offset = (page - 1) * page_size
    q = q.order_by(AuditLog.created_at.desc()).offset(offset).limit(page_size)
    result = await db.execute(q)
    return result.scalars().all()
