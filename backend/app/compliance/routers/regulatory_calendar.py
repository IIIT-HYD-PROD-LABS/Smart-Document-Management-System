"""Regulatory calendar lookup router — Phase 9 INFRA-05.

GET /regulatory-calendar — query holidays + filing deadlines.

The calendar is seeded by migration 0016 (12 rows for 2026: 6 filing
deadlines + 6 holidays). Phase 11 will extend this for deadline-aware
notification timing (skip weekends, advance to next business day).

Permission: NOTICE_VIEW. Reference data; same access tier as notice_types.
"""
from datetime import date as date_t
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import extract, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.models.regulatory_calendar import RegulatoryCalendar
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_async_db


router = APIRouter(
    prefix="/regulatory-calendar",
    tags=["compliance-lookups"],
)


class CalendarEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    year: int
    date: date_t
    authority: Optional[str] = None
    label: str
    category: str
    reference_url: Optional[str] = None
    notes: Optional[str] = None


@router.get("", response_model=List[CalendarEntryOut])
async def list_calendar_entries(
    year: int = Query(..., ge=2020, le=2050),
    month: Optional[int] = Query(None, ge=1, le=12),
    authority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    _gate: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """List regulatory calendar entries for a given year (and optional filters)."""
    q = select(RegulatoryCalendar).where(RegulatoryCalendar.year == year)
    if month is not None:
        q = q.where(extract("month", RegulatoryCalendar.date) == month)
    if authority:
        q = q.where(RegulatoryCalendar.authority == authority)
    if category:
        q = q.where(RegulatoryCalendar.category == category)
    q = q.order_by(RegulatoryCalendar.date.asc())
    result = await db.execute(q)
    return result.scalars().all()
