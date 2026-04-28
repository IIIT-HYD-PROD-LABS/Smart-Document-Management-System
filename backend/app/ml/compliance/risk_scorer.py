"""Risk scoring with rule-based v1 + XGBoost roadmap — CONTEXT D-13..D-17.

Implements the deterministic rule-based scorer per RESEARCH section 3
strategy 3 ("Hand-crafted scoring rules first, then train XGBoost to mimic +
improve"). This is the v1 production scorer; XGBoost lands in a later plan
once labeled training data is available.

Risk tiers (D-14, configurable per client via Phase 9 D-17 config_overrides):
  - Critical: score >= 85
  - High:     60 <= score < 85
  - Medium:   30 <= score < 60
  - Low:      score < 30

SHAP-style explanations (D-15): top-3 features by absolute contribution
rendered as natural-language phrases. The rule-based scorer can produce
these directly since its weights are explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Literal

RiskTier = Literal["critical", "high", "medium", "low"]

MODEL_VERSION = "rules-v1.0"

# Default tier thresholds — overridable per client via Phase 9 config_overrides.
DEFAULT_THRESHOLDS = {"critical": 85.0, "high": 60.0, "medium": 30.0}

# Authority severity weights (CONTEXT D-13). Placeholder values; CA/CFO
# domain expert sign-off pending per RESEARCH section 6 open question 4.
AUTHORITY_SEVERITY = {
    "GST": 0.7,
    "IT": 0.8,
    "MCA": 0.6,
    "RBI": 0.95,
    "SEBI": 0.9,
}

# Penalty contribution: log10(penalty) maps to points 0-30.
# log10(1) = 0 → 0 points
# log10(10000) = 4 → ~7.5 points
# log10(100000) = 5 → ~15 points (₹1 lakh)
# log10(1000000) = 6 → ~22.5 points (₹10 lakh)
# log10(10000000) = 7 → 30 points (₹1 crore)
PENALTY_LOG_FACTOR = 30.0 / 7.0  # 30 points at 1 crore

# Deadline pressure: days_to_deadline (clipped [0, 30]) inversely → points 0-25.
DEADLINE_PRESSURE_MAX_POINTS = 25.0
DEADLINE_PRESSURE_DAYS = 30  # >30 days = 0 points

# Authority severity: weight × 25 points.
AUTHORITY_MAX_POINTS = 25.0

# Critical section bonus.
CRITICAL_SECTION_POINTS = 15.0
CRITICAL_SECTION_PATTERNS = (
    "271(1)(c)",  # Concealment penalty under IT Act — 100-300% of tax
    "132",        # IT search and seizure
    "454",        # MCA penalty for failure
    "271AAB",     # Search-related undisclosed income
    "276",        # IT prosecution
)

# Show-cause chain bonus: SCN parents amplify follow-on assessment severity.
SHOW_CAUSE_CHAIN_POINTS = 5.0


@dataclass
class RiskExplanation:
    feature: str
    contribution: float  # signed points contribution (positive = increases risk)
    natural_language: str


@dataclass
class RiskAssessment:
    score: float                       # final clamped to [0, 100]
    tier: RiskTier
    top_factors: list[RiskExplanation] = field(default_factory=list)
    model_version: str = MODEL_VERSION
    raw_components: dict = field(default_factory=dict)


def score(
    *,
    authority: str,
    penalty_amount: Decimal | float | None,
    tax_demand: Decimal | float | None,
    deadline: date | None,
    today: date,
    legal_sections: list[str] | None = None,
    has_show_cause_chain: bool = False,
    thresholds: dict | None = None,
) -> RiskAssessment:
    """Compute deterministic risk score from notice attributes.

    Args:
        authority: One of GST/IT/MCA/RBI/SEBI.
        penalty_amount: INR penalty amount (Decimal preferred; float OK).
        tax_demand: INR tax demand amount.
        deadline: response_deadline (Date) or None if not set.
        today: Reference date for deadline computation (passed in for testability).
        legal_sections: List of section reference strings (e.g. ["u/s 271(1)(c)"]).
        has_show_cause_chain: True if parent_notice_id points to a Show-Cause notice.
        thresholds: Optional per-client tier threshold override (Phase 9 config_overrides).

    Returns:
        RiskAssessment with score [0, 100], tier, and top-3 factors.
    """
    import math

    components: list[RiskExplanation] = []

    # Authority severity contribution.
    auth_weight = AUTHORITY_SEVERITY.get(authority, 0.5)
    auth_points = auth_weight * AUTHORITY_MAX_POINTS
    components.append(
        RiskExplanation(
            feature="authority_severity",
            contribution=auth_points,
            natural_language=(
                f"{authority} regulator severity contributes +{auth_points:.1f} points"
            ),
        )
    )

    # Penalty / tax-demand magnitude (use larger of the two for scoring).
    largest_amount = max(
        float(penalty_amount or 0),
        float(tax_demand or 0),
    )
    if largest_amount > 0:
        penalty_points = min(
            math.log10(largest_amount) * PENALTY_LOG_FACTOR,
            30.0,
        )
        amount_label = "Penalty" if (penalty_amount or 0) >= (tax_demand or 0) else "Tax demand"
        amount_str = _format_inr(largest_amount)
        components.append(
            RiskExplanation(
                feature="financial_magnitude",
                contribution=penalty_points,
                natural_language=(
                    f"{amount_label} of {amount_str} contributes "
                    f"+{penalty_points:.1f} points"
                ),
            )
        )

    # Deadline pressure.
    if deadline is not None:
        days_to_deadline = (deadline - today).days
        if days_to_deadline < 0:
            # Overdue — full pressure.
            deadline_points = DEADLINE_PRESSURE_MAX_POINTS
            phrase = (
                f"Notice is overdue by {abs(days_to_deadline)} days, contributing "
                f"+{deadline_points:.1f} points"
            )
        else:
            clipped = min(days_to_deadline, DEADLINE_PRESSURE_DAYS)
            # Inverse linear: 0 days = max points, DEADLINE_PRESSURE_DAYS = 0 points.
            deadline_points = DEADLINE_PRESSURE_MAX_POINTS * (
                1 - (clipped / DEADLINE_PRESSURE_DAYS)
            )
            phrase = (
                f"Deadline within {clipped} days contributes "
                f"+{deadline_points:.1f} points"
            )
        components.append(
            RiskExplanation(
                feature="deadline_pressure",
                contribution=deadline_points,
                natural_language=phrase,
            )
        )

    # Critical section bonus.
    if legal_sections:
        for section_ref in legal_sections:
            if any(p in section_ref for p in CRITICAL_SECTION_PATTERNS):
                components.append(
                    RiskExplanation(
                        feature="critical_section",
                        contribution=CRITICAL_SECTION_POINTS,
                        natural_language=(
                            f"Cited under {section_ref} (high-severity provision) "
                            f"contributes +{CRITICAL_SECTION_POINTS:.1f} points"
                        ),
                    )
                )
                break  # Only count once even if multiple critical sections cited.

    # Show-cause chain bonus.
    if has_show_cause_chain:
        components.append(
            RiskExplanation(
                feature="show_cause_chain",
                contribution=SHOW_CAUSE_CHAIN_POINTS,
                natural_language=(
                    f"Follow-on to a Show-Cause notice contributes "
                    f"+{SHOW_CAUSE_CHAIN_POINTS:.1f} points"
                ),
            )
        )

    # Sum and clamp to [0, 100].
    raw_score = sum(c.contribution for c in components)
    final_score = max(0.0, min(100.0, raw_score))

    # Tier assignment.
    t = thresholds or DEFAULT_THRESHOLDS
    if final_score >= t["critical"]:
        tier: RiskTier = "critical"
    elif final_score >= t["high"]:
        tier = "high"
    elif final_score >= t["medium"]:
        tier = "medium"
    else:
        tier = "low"

    # Top 3 by absolute contribution.
    top_factors = sorted(components, key=lambda c: abs(c.contribution), reverse=True)[:3]

    return RiskAssessment(
        score=round(final_score, 2),
        tier=tier,
        top_factors=top_factors,
        model_version=MODEL_VERSION,
        raw_components={c.feature: c.contribution for c in components},
    )


def _format_inr(amount: float) -> str:
    """Format amount in Indian numbering style (lakhs/crores)."""
    if amount >= 10_000_000:
        return f"₹{amount / 10_000_000:.2f} crore"
    if amount >= 100_000:
        return f"₹{amount / 100_000:.2f} lakh"
    return f"₹{amount:,.0f}"


def feature_engineer(notice, client_history) -> dict:
    """Build a feature dict for a single notice.

    For the rule-based scorer, this is just argument extraction. The XGBoost
    successor will use the same dict shape so the migration is transparent.
    """
    return {
        "authority": notice.authority,
        "penalty_amount": notice.penalty,
        "tax_demand": notice.tax_demand,
        "deadline": notice.response_deadline,
        "legal_sections": notice.legal_sections or [],
        "has_show_cause_chain": (
            notice.parent_notice_id is not None
            and getattr(notice.parent_notice, "notice_type", None) is not None
            and getattr(notice.parent_notice.notice_type, "code", "").upper().startswith("SCN")
        ),
        "client_appeal_history_count": getattr(client_history, "appeal_count", 0),
    }
