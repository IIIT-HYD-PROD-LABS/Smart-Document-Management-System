"""Phase 17 EXTRACT-03 — conjunctive routing gate (D-06).

Plan 17-03 GREEN. `extraction_routing_service.route_or_apply` encodes
the three-condition gate: average ≥ 0.85 AND notice_number ≥ 0.85 AND
authority ≥ 0.85. Failure of any one routes to the Phase 10 review queue.
"""
from __future__ import annotations

import pytest

from app.compliance.services.extraction_routing_service import route_or_apply


@pytest.fixture(autouse=True)
def _pin_gate_thresholds(monkeypatch):
    """Pin the D-06 gate to its documented 0.85 thresholds.

    route_or_apply reads settings.EXTRACTION_AVG_GATE / _CRITICAL_GATE at call
    time, and deployments lower them for local LLMs that under-report their
    confidence. These tests assert the gate LOGIC at the canonical thresholds,
    so they must not inherit the ambient deployment tuning.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "EXTRACTION_AVG_GATE", 0.85)
    monkeypatch.setattr(settings, "EXTRACTION_CRITICAL_GATE", 0.85)


def test_high_confidence_envelope_routes_to_apply(extraction_envelope_fixture):
    """All three D-06 conditions satisfied → action='apply'."""
    decision = route_or_apply(extraction_envelope_fixture)
    assert decision["action"] == "apply"
    assert decision["reason"] is None
    assert decision["average_confidence"] >= 0.85
    assert decision["critical_field_confidence"]["notice_number"] >= 0.85
    assert decision["critical_field_confidence"]["authority"] >= 0.85


def test_low_average_routes_to_review_queue(low_confidence_envelope_fixture):
    """Average 0.79 < 0.85 → review_queue."""
    decision = route_or_apply(low_confidence_envelope_fixture)
    assert decision["action"] == "review_queue"
    assert "average confidence" in (decision["reason"] or "")


def test_critical_field_below_threshold_routes_to_review(critical_field_low_envelope_fixture):
    """Average 0.89 ≥ 0.85 BUT notice_number 0.70 < 0.85 → review_queue (D-06 critical-field rule)."""
    decision = route_or_apply(critical_field_low_envelope_fixture)
    assert decision["action"] == "review_queue"
    assert "notice_number" in (decision["reason"] or "")


def test_authority_below_threshold_routes_to_review():
    """Average ≥ 0.85 BUT authority < 0.85 → review_queue."""
    env = {
        "fields": {
            "notice_number": {"value": "X", "confidence": 0.95, "source_span": "x"},
            "authority": {"value": "GST", "confidence": 0.70, "source_span": "y"},
        },
        "average_confidence": 0.85,
        "model": "stub", "tokens_in": 1, "tokens_out": 1, "latency_ms": 1,
    }
    decision = route_or_apply(env)
    assert decision["action"] == "review_queue"
    assert "authority" in (decision["reason"] or "")


def test_post_validation_confidence_is_what_the_gate_uses(structurally_invalid_envelope_fixture):
    """D-33 + D-06: routing gate evaluates POST-validation confidence."""
    from app.compliance.services.notice_extraction_validator import validate_and_score
    validated = validate_and_score(structurally_invalid_envelope_fixture)
    decision = route_or_apply(validated)
    # GSTIN was 0.90 → post-validation 0.45 → drags the average below 0.85 → review
    assert decision["action"] == "review_queue"
    assert decision["average_confidence"] < 0.85
