"""Phase 17 EXTRACT-03b — structural validation (D-33, D-34).

Plan 17-03 GREEN. validate_and_score is a pure function that downgrades
field confidence on shape failure (bad GSTIN, bad date, deadline-before-issued,
liability arithmetic mismatch, bad authority).
"""
from __future__ import annotations


import pytest


def test_validator_halves_confidence_on_bad_gstin(structurally_invalid_envelope_fixture):
    """D-33: GSTIN failing the 15-char regex has its confidence multiplied by 0.5."""
    from app.compliance.services.notice_extraction_validator import validate_and_score

    validated = validate_and_score(structurally_invalid_envelope_fixture)
    original = structurally_invalid_envelope_fixture["fields"]["gstin"]["confidence"]
    assert validated["fields"]["gstin"]["confidence"] == pytest.approx(original * 0.5, rel=1e-3)
    assert validated["fields"]["gstin"]["validation_failure"] is not None
    assert validated["fields"]["gstin"]["original_confidence"] == original


def test_validator_flags_deadline_before_issued(structurally_invalid_envelope_fixture):
    """D-33: response_deadline earlier than issued_date is a validation failure."""
    from app.compliance.services.notice_extraction_validator import validate_and_score

    validated = validate_and_score(structurally_invalid_envelope_fixture)
    # issued_date=2026-05-12, response_deadline=2026-04-11 → fails
    assert validated["fields"]["response_deadline"]["validation_failure"] is not None
    original = structurally_invalid_envelope_fixture["fields"]["response_deadline"]["confidence"]
    assert validated["fields"]["response_deadline"]["confidence"] == pytest.approx(original * 0.5, rel=1e-3)


def test_validator_flags_liability_arithmetic_mismatch():
    """D-33: total_liability must equal tax + interest + penalty within 1 INR."""
    from app.compliance.services.notice_extraction_validator import validate_and_score

    env = {
        "fields": {
            "tax_demand": {"value": 100000.0, "confidence": 0.90, "source_span": "x"},
            "interest": {"value": 5000.0, "confidence": 0.90, "source_span": "y"},
            "penalty": {"value": 10000.0, "confidence": 0.90, "source_span": "z"},
            "total_liability": {"value": 200000.0, "confidence": 0.90, "source_span": "w"},
        },
        "average_confidence": 0.90,
        "model": "stub", "tokens_in": 1, "tokens_out": 1, "latency_ms": 1,
    }
    validated = validate_and_score(env)
    assert validated["fields"]["total_liability"]["validation_failure"] is not None
    assert validated["fields"]["total_liability"]["confidence"] == pytest.approx(0.45, rel=1e-3)


def test_validator_penalises_field_at_most_once():
    """A field failing BOTH a single-field rule and the cross-field liability
    rule is halved once (0.5x), never twice (0.25x).

    total_liability is negative (single-field failure) AND breaks the
    tax+interest+penalty arithmetic (cross-field failure). The cross-field
    annotation must be skipped because the field already failed, so the
    confidence is original*0.5 and the recorded reason is the single-field one.
    """
    from app.compliance.services.notice_extraction_validator import validate_and_score

    env = {
        "fields": {
            "tax_demand": {"value": 100000.0, "confidence": 0.90, "source_span": "x"},
            "interest": {"value": 5000.0, "confidence": 0.90, "source_span": "y"},
            "penalty": {"value": 10000.0, "confidence": 0.90, "source_span": "z"},
            "total_liability": {"value": -50000.0, "confidence": 0.80, "source_span": "w"},
        },
        "average_confidence": 0.875,
        "model": "stub", "tokens_in": 1, "tokens_out": 1, "latency_ms": 1,
    }
    validated = validate_and_score(env)
    tl = validated["fields"]["total_liability"]
    assert tl["confidence"] == pytest.approx(0.80 * 0.5, rel=1e-3)
    assert tl["confidence"] != pytest.approx(0.80 * 0.25, rel=1e-3)
    assert tl["original_confidence"] == 0.80
    # Single-field rule wins; cross-field reason did not overwrite it.
    assert tl["validation_failure"] == "is negative"


def test_validator_passes_clean_envelope_unchanged(extraction_envelope_fixture):
    """No structural failure → confidences untouched, validation_failure=None on every field."""
    from app.compliance.services.notice_extraction_validator import validate_and_score

    validated = validate_and_score(extraction_envelope_fixture)
    for name, payload in validated["fields"].items():
        original_conf = extraction_envelope_fixture["fields"][name]["confidence"]
        assert payload["confidence"] == pytest.approx(original_conf), f"{name} drifted"
        assert payload["validation_failure"] is None, f"{name} should pass"


def test_validator_does_not_mutate_input(extraction_envelope_fixture):
    """validate_and_score is a pure function (caller-side correctness)."""
    from app.compliance.services.notice_extraction_validator import validate_and_score

    original_snapshot = repr(extraction_envelope_fixture)
    validate_and_score(extraction_envelope_fixture)
    assert repr(extraction_envelope_fixture) == original_snapshot
