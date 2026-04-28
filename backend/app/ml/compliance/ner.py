"""spaCy NER for compliance notices — CONTEXT D-08..D-12.

Two-layer extraction:
  1. regex_patterns.py runs first (deterministic, 100% precision on patterns)
  2. spaCy NER runs second (catches free-form entities like party names)

On conflict between regex hit and NER hit on the same span, regex wins.

Custom entities trained on 500+ hand-annotated notices (annotation effort
during /gsd:research-phase 10):
  - NOTICE_NUMBER, DEADLINE_DATE, PENALTY_AMOUNT, TAX_DEMAND
  - LEGAL_SECTION, ASSESSMENT_YEAR, FINANCIAL_YEAR

All extracted dates normalized to ISO 8601 via dateparser (D-11).
All amounts parsed via Indian currency parser (D-12) and stored as Decimal INR.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

NER_MODEL_PATH = Path("/app/models/compliance/ner_pipeline")


@dataclass
class ExtractedFields:
    notice_number: str | None = None
    deadline: date | None = None
    penalty_amount: Decimal | None = None
    tax_demand: Decimal | None = None
    interest: Decimal | None = None
    total_liability: Decimal | None = None
    legal_sections: list[str] = field(default_factory=list)
    gstins: list[str] = field(default_factory=list)
    pans: list[str] = field(default_factory=list)
    cins: list[str] = field(default_factory=list)
    assessment_year: str | None = None
    financial_year: str | None = None


def extract(text: str) -> ExtractedFields:
    """Run regex-first then spaCy NER over text and return structured fields.

    NOTE: Phase 10 Wave 0 skeleton. Custom NER training lands in Plan 10-XX.
    """
    raise NotImplementedError(
        "spaCy custom NER not yet trained. "
        "Run /gsd:research-phase 10 to scope annotation effort, then /gsd:plan-phase 10."
    )
