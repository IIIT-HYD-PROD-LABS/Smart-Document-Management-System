"""Seed the compliance_regulatory_calendar with FY 2025-26 statutory deadlines.

Idempotent via an explicit existence check on the full natural key
(year, date, label, category, authority) before each INSERT. A UNIQUE
constraint on that key is added by a separate migration; until it lands
this pre-check is what makes re-seeding a no-op.
Run via:
    docker exec smartdocs-backend python -m app.compliance.calendar.seed --year 2026
"""
from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.compliance.calendar.statutory import expand_statutory_deadlines
from app.compliance.models.regulatory_calendar import RegulatoryCalendar
from app.database import SessionLocal

logger = logging.getLogger(__name__)


def seed_year(db: Session, year: int) -> dict[str, int]:
    """Insert statutory deadlines for `year` if not already present.

    Returns a {inserted, skipped} count summary.
    """
    deadlines = expand_statutory_deadlines(year)
    inserted = 0
    skipped = 0
    for d in deadlines:
        # Store under the deadline's actual calendar year, not the seed
        # arg: some FY `year` deadlines (GSTR-1/3B for Dec, TDS Q3) land in
        # Jan of `year+1`. The calendar query filters on year AND derives
        # month from the date, so a row whose year != date.year is invisible.
        row_year = d.due_date.year
        # L4 — match the full natural key the INSERT writes (authority was
        # omitted before, so two deadlines differing only by authority would
        # collapse to one and re-seeding wasn't truly idempotent).
        existing = (
            db.query(RegulatoryCalendar)
            .filter(
                RegulatoryCalendar.year == row_year,
                RegulatoryCalendar.date == d.due_date,
                RegulatoryCalendar.label == d.label,
                RegulatoryCalendar.category == d.category,
                RegulatoryCalendar.authority == d.authority,
            )
            .first()
        )
        if existing is not None:
            skipped += 1
            continue
        row = RegulatoryCalendar(
            year=row_year,
            date=d.due_date,
            authority=d.authority,
            label=d.label,
            category=d.category,
        )
        db.add(row)
        inserted += 1
    db.commit()
    return {"inserted": inserted, "skipped": skipped}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # Bypass RLS for seed inserts
        db.execute(text("RESET ROLE"))
        result = seed_year(db, args.year)
        print(f"Seeded year {args.year}: {result}")
        return 0
    except Exception as e:
        print(f"Seed failed: {e}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
