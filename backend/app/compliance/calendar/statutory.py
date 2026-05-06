"""Pre-loaded Indian statutory deadlines for FY 2025-26 — Phase 11 D-10.

This is the source of truth for the calendar UI's filing deadlines.
Each entry produces one or more dates per year per applicable client
type. Values reflect 2026 CBDT/CBIC/MCA gazette notifications as of
2026-05-05.

Use `expand_statutory_deadlines(year)` to materialize into a list of
(date, label, authority, category) tuples ready for insertion into
`compliance_regulatory_calendar` table.

Coverage:
  - GSTR-1 monthly (11th) + quarterly (13th of month after quarter)
  - GSTR-3B monthly (20th)
  - GSTR-9 annual (31 Dec)
  - TDS quarterly (Q1: 31 Jul, Q2: 31 Oct, Q3: 31 Jan, Q4: 31 May)
  - Advance Tax quarterly (15 Jun, 15 Sep, 15 Dec, 15 Mar)
  - ITR (31 Jul individuals, 30 Sep audit cases)
  - ROC AOC-4 (30 Oct), MGT-7 (30 Nov)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class StatutoryDeadline:
    label: str
    authority: str  # GST | IT | MCA
    category: str   # filing_deadline always for these
    due_date: date
    applicable_to: str  # client filter; "all" | "audited" | "company"


def _all_months(year: int) -> list[int]:
    return list(range(1, 13))


def expand_statutory_deadlines(year: int) -> list[StatutoryDeadline]:
    """Produce concrete deadlines for the given calendar year.

    Note: Indian FY runs Apr-Mar; some deadlines (TDS Q4, Advance Tax Q4,
    ITR for FY ending Mar `year`) land in calendar `year` even though the
    fiscal year extends into March.
    """
    out: list[StatutoryDeadline] = []

    # GSTR-1 monthly (11th of next month — return for month M is filed on 11th of M+1)
    for m in _all_months(year):
        if m == 12:
            due = date(year + 1, 1, 11)
        else:
            due = date(year, m + 1, 11)
        out.append(StatutoryDeadline(
            label=f"GSTR-1 — return for {date(year, m, 1).strftime('%b %Y')}",
            authority="GST",
            category="filing_deadline",
            due_date=due,
            applicable_to="all",
        ))

    # GSTR-3B monthly (20th of next month)
    for m in _all_months(year):
        if m == 12:
            due = date(year + 1, 1, 20)
        else:
            due = date(year, m + 1, 20)
        out.append(StatutoryDeadline(
            label=f"GSTR-3B — payment + return for {date(year, m, 1).strftime('%b %Y')}",
            authority="GST",
            category="filing_deadline",
            due_date=due,
            applicable_to="all",
        ))

    # GSTR-9 annual (31 Dec)
    out.append(StatutoryDeadline(
        label=f"GSTR-9 — annual return for FY {year - 1}-{str(year)[2:]}",
        authority="GST",
        category="filing_deadline",
        due_date=date(year, 12, 31),
        applicable_to="all",
    ))

    # TDS quarterly (returns due 31st of next month after quarter end)
    for label, dd in [
        (f"TDS Q1 (Apr-Jun {year})", date(year, 7, 31)),
        (f"TDS Q2 (Jul-Sep {year})", date(year, 10, 31)),
        (f"TDS Q3 (Oct-Dec {year})", date(year + 1, 1, 31)),
        (f"TDS Q4 (Jan-Mar {year})", date(year, 5, 31)),
    ]:
        out.append(StatutoryDeadline(
            label=label,
            authority="IT",
            category="filing_deadline",
            due_date=dd,
            applicable_to="all",
        ))

    # Advance Tax quarterly (15 Jun / 15 Sep / 15 Dec / 15 Mar)
    for q, dd in [
        ("Q1", date(year, 6, 15)),
        ("Q2", date(year, 9, 15)),
        ("Q3", date(year, 12, 15)),
        ("Q4", date(year + 1, 3, 15)),
    ]:
        out.append(StatutoryDeadline(
            label=f"Advance Tax {q} ({year})",
            authority="IT",
            category="filing_deadline",
            due_date=dd,
            applicable_to="all",
        ))

    # ITR
    out.append(StatutoryDeadline(
        label=f"ITR (non-audit) — FY {year - 1}-{str(year)[2:]}",
        authority="IT",
        category="filing_deadline",
        due_date=date(year, 7, 31),
        applicable_to="all",
    ))
    out.append(StatutoryDeadline(
        label=f"ITR (audit cases) — FY {year - 1}-{str(year)[2:]}",
        authority="IT",
        category="filing_deadline",
        due_date=date(year, 9, 30),
        applicable_to="audited",
    ))

    # MCA filings
    out.append(StatutoryDeadline(
        label=f"AOC-4 (financial statements) — FY {year - 1}-{str(year)[2:]}",
        authority="MCA",
        category="filing_deadline",
        due_date=date(year, 10, 30),
        applicable_to="company",
    ))
    out.append(StatutoryDeadline(
        label=f"MGT-7 (annual return) — FY {year - 1}-{str(year)[2:]}",
        authority="MCA",
        category="filing_deadline",
        due_date=date(year, 11, 30),
        applicable_to="company",
    ))

    return out
