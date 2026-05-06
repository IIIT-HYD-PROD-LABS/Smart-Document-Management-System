"""Seed the compliance_regulatory_calendar with FY 2025-26 statutory deadlines.

Idempotent — uses ON CONFLICT DO NOTHING via SQLAlchemy `merge`.
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
        existing = (
            db.query(RegulatoryCalendar)
            .filter(
                RegulatoryCalendar.year == year,
                RegulatoryCalendar.date == d.due_date,
                RegulatoryCalendar.label == d.label,
                RegulatoryCalendar.category == d.category,
            )
            .first()
        )
        if existing is not None:
            skipped += 1
            continue
        row = RegulatoryCalendar(
            year=year,
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
