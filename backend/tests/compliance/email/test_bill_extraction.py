"""Phase 15 — BILL-01 / BILL-02 bill extraction tests.

RED-state stub. Plan 03 lands `app.email.services.bill_extractor.extract_bill`,
which calls the v1.0 LLM extraction service with a bill-specific prompt
template and falls back to local regex (amount + date) on LLM unavailability.
"""
from __future__ import annotations

import pytest


def test_extract_bill_from_tatapower_email():
    """LLM extraction yields biller_name='Tata Power', biller_category='utility', amount_due=4250 (BILL-01, BILL-02)."""
    try:
        from app.email.services.bill_extractor import extract_bill  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — bill_extractor not yet implemented")
    pytest.skip("Plan 03 — LLM extraction assertion lands then")


def test_regex_fallback_when_llm_unavailable():
    """When extract_with_llm raises LLMUnavailable, regex fallback yields amount + due_date (BILL-02)."""
    try:
        from app.email.services.bill_extractor import extract_bill  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — bill_extractor not yet implemented")
    pytest.skip("Plan 03 — regex fallback assertion lands then")


def test_biller_category_enum_values():
    """biller_category constrained to utility/telecom/credit_card/subscription/other (D-20)."""
    try:
        from app.email.models.bill import BillerCategory  # noqa: F401
    except ImportError:
        pytest.skip("Plan 02 — Bill ORM not yet implemented")
    pytest.skip("Plan 02 — enum membership assertion lands then")
