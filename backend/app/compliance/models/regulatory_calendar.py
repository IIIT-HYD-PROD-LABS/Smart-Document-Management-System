"""RegulatoryCalendar ORM model — Phase 9 INFRA-05.

Maps to migration 0013 table compliance_regulatory_calendar (data seeded by
migration 0016 — 12 rows for 2026: 6 filing deadlines + 6 holidays).

Phase 11 will use this calendar for deadline-aware notification timing
(skip weekends, skip CBDT/CBIC holidays, advance to next business day).
"""
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)

from app.database import Base


class RegulatoryCalendar(Base):
    __tablename__ = "compliance_regulatory_calendar"

    id = Column(Integer, primary_key=True, autoincrement=True)
    year = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    # NULL = cross-authority / general holiday (e.g. Republic Day)
    authority = Column(String(10), nullable=True)
    label = Column(String(200), nullable=False)
    # 'holiday' | 'filing_deadline' | 'circular_extension'
    category = Column(String(30), nullable=False)
    reference_url = Column(String(1000), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )

    __table_args__ = (
        CheckConstraint(
            "year >= 2020 AND year <= 2050",
            name="ck_calendar_year",
        ),
        CheckConstraint(
            "category IN ('holiday', 'filing_deadline', 'circular_extension')",
            name="ck_calendar_category",
        ),
        Index("ix_calendar_year_date", "year", "date"),
    )

    def __repr__(self):
        return (
            f"<RegulatoryCalendar(year={self.year}, date={self.date}, "
            f"label='{self.label}', category='{self.category}')>"
        )
