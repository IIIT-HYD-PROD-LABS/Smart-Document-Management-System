"""Notice type lookup router — Phase 9 D-01.

GET /notice-types — enumerate the per-authority notice type catalog.

Per CONTEXT D-01: notice types live in a DB table (NOT enum) so admins can
add new types without code deploys. Authority is the enum (GST, IT, MCA,
RBI, SEBI). Each authority has its own (code, label, description) rows.

Permission: NOTICE_VIEW. The catalog is reference data — every role with
NOTICE_VIEW (which is all 7 compliance roles) can read it.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.models.notice_type import NoticeType
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_async_db


router = APIRouter(prefix="/notice-types", tags=["compliance-lookups"])


class NoticeTypeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    authority: str
    code: str
    label: str
    description: Optional[str] = None
    is_active: bool


@router.get("", response_model=List[NoticeTypeOut])
async def list_notice_types(
    authority: Optional[str] = Query(None),
    _gate: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """Enumerate active notice types, optionally filtered by authority."""
    q = select(NoticeType).where(NoticeType.is_active.is_(True))
    if authority:
        q = q.where(NoticeType.authority == authority)
    q = q.order_by(NoticeType.authority, NoticeType.code)
    result = await db.execute(q)
    return result.scalars().all()
