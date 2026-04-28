"""Phase 10 — risk_scorer rule-based v1 unit tests.

Verifies score computation, tier assignment, and SHAP-style explanations
against deterministic inputs. All tests are pure-Python (no DB, no Celery).
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.ml.compliance.risk_scorer import (
    AUTHORITY_SEVERITY,
    DEFAULT_THRESHOLDS,
    MODEL_VERSION,
    RiskAssessment,
    score,
)


TODAY = date(2026, 4, 28)


def test_critical_tier_combination():
    """High penalty + tight deadline + RBI authority + critical section → Critical."""
    result = score(
        authority="RBI",
        penalty_amount=Decimal("5000000"),  # ₹50 lakh
        tax_demand=None,
        deadline=TODAY + timedelta(days=2),
        today=TODAY,
        legal_sections=["u/s 271(1)(c)"],
        has_show_cause_chain=False,
    )
    assert result.tier == "critical"
    assert result.score >= DEFAULT_THRESHOLDS["critical"]
    assert result.model_version == MODEL_VERSION
    assert len(result.top_factors) == 3


def test_low_tier_combination():
    """No penalty, ample deadline (>30 days), moderate authority → Low.

    Note: under log10 scaling even small penalties contribute meaningful points,
    so a true low-tier scenario means no quantified penalty/tax demand.
    """
    result = score(
        authority="MCA",
        penalty_amount=None,
        tax_demand=None,
        deadline=TODAY + timedelta(days=90),
        today=TODAY,
    )
    assert result.tier == "low"
    assert result.score < DEFAULT_THRESHOLDS["medium"]


def test_overdue_deadline_max_pressure():
    """Overdue notice gets full deadline pressure points."""
    result = score(
        authority="GST",
        penalty_amount=Decimal("100000"),
        tax_demand=None,
        deadline=TODAY - timedelta(days=10),
        today=TODAY,
    )
    deadline_factor = next(
        (f for f in result.top_factors if f.feature == "deadline_pressure"),
        None,
    )
    assert deadline_factor is not None
    assert deadline_factor.contribution == 25.0
    assert "overdue by 10 days" in deadline_factor.natural_language


def test_authority_severity_weights_present():
    """Each authority lookup produces a non-zero contribution."""
    for authority in AUTHORITY_SEVERITY:
        result = score(
            authority=authority,
            penalty_amount=None,
            tax_demand=None,
            deadline=None,
            today=TODAY,
        )
        auth_factor = next(
            (f for f in result.top_factors if f.feature == "authority_severity"),
            None,
        )
        assert auth_factor is not None
        assert auth_factor.contribution > 0


def test_score_clamped_to_100():
    """Score never exceeds 100 even with all factors maxed."""
    result = score(
        authority="RBI",
        penalty_amount=Decimal("100000000"),  # ₹10 crore
        tax_demand=Decimal("100000000"),
        deadline=TODAY - timedelta(days=30),
        today=TODAY,
        legal_sections=["u/s 271(1)(c)", "Section 132"],
        has_show_cause_chain=True,
    )
    assert result.score <= 100.0


def test_no_attributes_yields_low_tier_with_authority_only():
    """Notice with only authority (no amounts, no deadline) is Low if authority alone < 30."""
    result = score(
        authority="MCA",  # weight 0.6 → 15 points
        penalty_amount=None,
        tax_demand=None,
        deadline=None,
        today=TODAY,
    )
    assert result.tier == "low"


def test_critical_section_pattern_match():
    """Citation under 271(1)(c) adds critical-section bonus."""
    with_section = score(
        authority="IT",
        penalty_amount=Decimal("50000"),
        tax_demand=None,
        deadline=TODAY + timedelta(days=20),
        today=TODAY,
        legal_sections=["u/s 271(1)(c)"],
    )
    without_section = score(
        authority="IT",
        penalty_amount=Decimal("50000"),
        tax_demand=None,
        deadline=TODAY + timedelta(days=20),
        today=TODAY,
        legal_sections=["Section 220"],
    )
    assert with_section.score > without_section.score


def test_show_cause_chain_bonus():
    """has_show_cause_chain=True adds 5 points vs False."""
    with_scn = score(
        authority="GST",
        penalty_amount=Decimal("50000"),
        tax_demand=None,
        deadline=TODAY + timedelta(days=15),
        today=TODAY,
        has_show_cause_chain=True,
    )
    without_scn = score(
        authority="GST",
        penalty_amount=Decimal("50000"),
        tax_demand=None,
        deadline=TODAY + timedelta(days=15),
        today=TODAY,
        has_show_cause_chain=False,
    )
    assert with_scn.score - without_scn.score == pytest.approx(5.0, abs=0.01)


def test_penalty_uses_larger_of_two_amounts():
    """Score uses max(penalty, tax_demand), not sum."""
    only_penalty = score(
        authority="GST",
        penalty_amount=Decimal("1000000"),  # ₹10 lakh
        tax_demand=None,
        deadline=TODAY + timedelta(days=30),
        today=TODAY,
    )
    only_tax_demand = score(
        authority="GST",
        penalty_amount=None,
        tax_demand=Decimal("1000000"),
        deadline=TODAY + timedelta(days=30),
        today=TODAY,
    )
    assert only_penalty.score == pytest.approx(only_tax_demand.score, abs=0.01)


def test_top_factors_capped_at_three():
    """Even with 5+ contributing factors, only top 3 are returned."""
    result = score(
        authority="SEBI",
        penalty_amount=Decimal("10000000"),
        tax_demand=Decimal("5000000"),
        deadline=TODAY,
        today=TODAY,
        legal_sections=["u/s 271(1)(c)"],
        has_show_cause_chain=True,
    )
    assert len(result.top_factors) == 3
    # Sorted descending by absolute contribution.
    contribs = [abs(f.contribution) for f in result.top_factors]
    assert contribs == sorted(contribs, reverse=True)


def test_inr_formatting_in_natural_language():
    """Penalty phrase uses Indian numbering (lakh/crore)."""
    result = score(
        authority="GST",
        penalty_amount=Decimal("2500000"),  # ₹25 lakh
        tax_demand=None,
        deadline=None,
        today=TODAY,
    )
    financial = next(
        (f for f in result.top_factors if f.feature == "financial_magnitude"),
        None,
    )
    assert financial is not None
    assert "lakh" in financial.natural_language


def test_per_client_threshold_override():
    """Custom thresholds shift tier boundaries."""
    # Default critical ≥ 85; with override, 50 should be critical.
    result = score(
        authority="GST",  # 0.7 × 25 = 17.5 points
        penalty_amount=Decimal("100000"),  # ~15 points
        tax_demand=None,
        deadline=TODAY + timedelta(days=10),  # ~17 points
        today=TODAY,
        thresholds={"critical": 40.0, "high": 25.0, "medium": 10.0},
    )
    assert result.tier == "critical"


def test_assessment_returns_correct_dataclass():
    """Returned object is a RiskAssessment with all expected fields."""
    result = score(
        authority="GST",
        penalty_amount=Decimal("10000"),
        tax_demand=None,
        deadline=None,
        today=TODAY,
    )
    assert isinstance(result, RiskAssessment)
    assert isinstance(result.score, float)
    assert result.tier in ("critical", "high", "medium", "low")
    assert isinstance(result.raw_components, dict)
