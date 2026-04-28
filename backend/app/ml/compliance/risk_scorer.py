"""XGBoost risk scoring with SHAP explanations — CONTEXT D-13..D-17.

Features (D-13):
  - log(penalty_amount), log(tax_demand_amount), log(total_liability)
  - days_to_deadline (clipped [0, 365]; negative = overdue)
  - authority_severity_weight (lookup: GST=0.7, IT=0.8, MCA=0.6, RBI=0.95, SEBI=0.9)
  - notice_type_severity (per-type weight from canonical severity table)
  - is_critical_section (boolean: u/s 271(1)(c), Section 132, Penalty under §454)
  - client_appeal_history_count
  - days_since_received
  - has_show_cause_chain (boolean: parent_notice_id with type=SCN)

Risk tiers (D-14, configurable per client via Phase 9 D-17):
  - Critical: score >= 85
  - High:     60 <= score < 85
  - Medium:   30 <= score < 60
  - Low:      score < 30

SHAP (D-15): TreeExplainer (XGBoost native). Top 3 features by absolute SHAP
impact rendered as natural-language phrases.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Literal

RiskTier = Literal["critical", "high", "medium", "low"]

MODEL_PATH = Path("/app/models/compliance/risk_xgboost.json")

# Default tier thresholds — overridable per client via Phase 9 config_overrides.
DEFAULT_THRESHOLDS = {"critical": 85, "high": 60, "medium": 30}

AUTHORITY_SEVERITY = {
    "GST": 0.7,
    "IT": 0.8,
    "MCA": 0.6,
    "RBI": 0.95,
    "SEBI": 0.9,
}


@dataclass
class RiskExplanation:
    feature: str
    contribution: float  # signed SHAP value (positive = increases risk)
    natural_language: str  # e.g. "Penalty above ₹10 lakh contributes +18 points"


@dataclass
class RiskAssessment:
    score: float  # 0-100
    tier: RiskTier
    top_factors: list[RiskExplanation]  # length 3
    model_version: str


def score(features: dict) -> RiskAssessment:
    """Compute risk score, tier, and top-3 SHAP explanations.

    `features` is the engineered feature dict from `feature_engineer()`.
    Returns RiskAssessment with score [0, 100], tier label, and top 3 factors.

    NOTE: Phase 10 Wave 0 skeleton. Training pipeline + calibration land in
    Plan 10-XX after /gsd:research-phase 10 sources training data.
    """
    raise NotImplementedError(
        "XGBoost risk scorer not yet trained. "
        "Pending /gsd:research-phase 10 (training data sourcing) and Plan 10-XX."
    )


def feature_engineer(notice, client_history) -> dict:
    """Build the feature dict for a single notice given the notice ORM row and
    pre-fetched client history (for client_appeal_history_count etc).

    Pure function; no DB access.
    """
    raise NotImplementedError("Pending Phase 10 plan execution.")
