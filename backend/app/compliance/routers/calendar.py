"""Phase 11 calendar router — month/week views + holiday-aware adjust.

Endpoints under /api/compliance/calendar (mounted in main.py):

  GET  /entries           NOTICE_VIEW  filter+paginate calendar entries
  POST /adjust-deadline   NOTICE_VIEW  pure adjust_deadline preview
  GET  /compliance-score  REPORT_VIEW  rolling 90-day compliance score
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.compliance.calendar.adjust import adjust_deadline
from app.compliance.dependencies import (
    is_cross_client_mode,
    require_compliance_permission,
)
from app.compliance.models.membership import ClientMembership
from app.compliance.models.notice import ComplianceNotice
from app.compliance.models.regulatory_calendar import RegulatoryCalendar
from app.compliance.services.permission_registry import CompliancePermission
from app.database import get_db

router = APIRouter(prefix="/calendar", tags=["compliance-calendar"])


class CalendarEntryOut(BaseModel):
    id: int
    year: int
    date: date
    authority: Optional[str] = None
    label: str
    category: str
    reference_url: Optional[str] = None
    notes: Optional[str] = None


class AdjustDeadlineRequest(BaseModel):
    deadline: date
    state_code: Optional[str] = Field(None, pattern=r"^IN-[A-Z]{2}$")


class AdjustDeadlineResponse(BaseModel):
    original: date
    adjusted: date
    shifted: bool


class ComplianceScoreResponse(BaseModel):
    score: float
    window_days: int
    notices_total: int
    notices_on_time: int
    notices_overdue: int
    as_of: datetime


@router.get(
    "/entries",
    response_model=list[CalendarEntryOut],
    summary="List calendar entries (holidays + statutory deadlines)",
)
def list_calendar_entries(
    year: int = Query(..., ge=2020, le=2050),
    month: Optional[int] = Query(None, ge=1, le=12),
    authority: Optional[str] = Query(None, pattern=r"^(GST|IT|MCA|RBI|SEBI)$"),
    category: Optional[str] = Query(
        None, pattern=r"^(holiday|filing_deadline|circular_extension)$"
    ),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
    db: Session = Depends(get_db),
):
    q = db.query(RegulatoryCalendar).filter(RegulatoryCalendar.year == year)
    if month:
        # PostgreSQL EXTRACT(MONTH FROM date) — use func
        q = q.filter(func.extract("month", RegulatoryCalendar.date) == month)
    if authority:
        q = q.filter(RegulatoryCalendar.authority == authority)
    if category:
        q = q.filter(RegulatoryCalendar.category == category)
    rows = q.order_by(RegulatoryCalendar.date).all()
    return [CalendarEntryOut.model_validate(r, from_attributes=True) for r in rows]


@router.post(
    "/adjust-deadline",
    response_model=AdjustDeadlineResponse,
    summary="Holiday-aware deadline adjustment preview",
)
def adjust_deadline_endpoint(
    body: AdjustDeadlineRequest,
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.NOTICE_VIEW)
    ),
):
    adjusted = adjust_deadline(body.deadline, body.state_code)
    return AdjustDeadlineResponse(
        original=body.deadline,
        adjusted=adjusted,
        shifted=adjusted != body.deadline,
    )


@router.get(
    "/compliance-score",
    response_model=ComplianceScoreResponse,
    summary="Rolling 90-day compliance score for the active client",
)
def compliance_score(
    window_days: int = Query(90, ge=7, le=365),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.REPORT_VIEW)
    ),
    db: Session = Depends(get_db),
):
    """Phase 11 D-14 — % notices resolved within deadline over rolling window.

    Formula (v2.0): on_time / total. Severity-weighted variants ship in v2.1.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(days=window_days)

    base = db.query(ComplianceNotice).filter(
        ComplianceNotice.created_at >= window_start
    )
    if not is_cross_client_mode():
        base = base.filter(ComplianceNotice.client_id == membership.client_id)

    notices = base.all()
    total = len(notices)
    on_time = 0
    overdue = 0
    for n in notices:
        if n.status in ("resolved", "submitted"):
            if n.response_deadline and n.status_changed_at:
                changed_date = n.status_changed_at.date()
                if changed_date <= n.response_deadline:
                    on_time += 1
                else:
                    overdue += 1
            else:
                # L6 — limitation: when response_deadline or
                # status_changed_at is missing we can't prove lateness, so
                # the notice is counted on-time (optimistic). status_changed_at
                # is only populated by the transition path, so notices closed
                # before that column existed inflate the score slightly. A
                # severity-weighted v2.1 rework is the proper fix.
                on_time += 1
        elif n.status == "dismissed":
            on_time += 1
        elif n.response_deadline and n.response_deadline < now.date():
            overdue += 1

    denominator = on_time + overdue
    score = (on_time / denominator * 100.0) if denominator else 100.0

    return ComplianceScoreResponse(
        score=round(score, 1),
        window_days=window_days,
        notices_total=total,
        notices_on_time=on_time,
        notices_overdue=overdue,
        as_of=now,
    )
