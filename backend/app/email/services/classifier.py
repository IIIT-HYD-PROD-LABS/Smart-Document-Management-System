"""Rule-based compliance detector — Phase 15 EMAIL-06 (D-16 revised).

v2.0: regex on sender domain + subject keywords. Binary confidence.
v2.1: replace classify() body with BERT classifier call; signature stays.

Per reconciliation #2 (researcher): D-17's spaCy NER is broken (ner.py:49
NotImplementedError). Downstream extraction uses regex_patterns.py +
extract_with_llm() — NOT ner.py.
"""
from __future__ import annotations

from app.email.classifier_rules import (
    COMPLIANCE_SENDER_PATTERNS,
    COMPLIANCE_SUBJECT_KEYWORDS,
)


def classify(sender: str, subject: str) -> tuple[bool, float]:
    """Returns (is_compliance_notice, confidence).

    Cases:
      sender + subject match  -> (True, 1.0)  -> auto-create ComplianceNotice
      sender match only       -> (False, 0.5) -> Phase 10 review queue (CLASS-04)
      subject match only      -> (False, 0.0) -> dms_only per D-33 (forwarded)
      neither match           -> (False, 0.0) -> ignored
    """
    sender_match = any(p.search(sender) for p in COMPLIANCE_SENDER_PATTERNS)
    subject_match = bool(COMPLIANCE_SUBJECT_KEYWORDS.search(subject))
    if sender_match and subject_match:
        return True, 1.0
    if sender_match and not subject_match:
        return False, 0.5
    return False, 0.0
