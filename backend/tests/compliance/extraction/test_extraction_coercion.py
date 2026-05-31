"""Phase 17 hardening — extraction value coercion + auto-apply fill.

Covers extraction_coercion (currency/date/authority normalization) and the
apply_extraction_to_notice auto-fill path that back-populates canonical
columns on a high-confidence 'apply' decision (the detail-page / Gmail /
Celery upload flow that previously dead-ended in JSONB).
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.compliance.services.extraction_coercion import (
    CoercionError,
    coerce_amount,
    coerce_authority,
    coerce_date,
    coerce_notice_number,
)
from app.compliance.services.extraction_routing_service import (
    _apply_fields_to_columns,
    apply_extraction_to_notice,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("145000", Decimal("145000.00")),
        ("1,45,000", Decimal("145000.00")),
        ("₹1,45,000", Decimal("145000.00")),
        ("Rs. 1,45,000/-", Decimal("145000.00")),
        ("Rs. 1.45 lakh", Decimal("145000.00")),
        ("2 crore", Decimal("20000000.00")),
        ("INR 50000", Decimal("50000.00")),
        (145000.0, Decimal("145000.00")),
        ("", None),
        (None, None),
    ],
)
def test_coerce_amount(raw, expected):
    assert coerce_amount(raw) == expected


@pytest.mark.parametrize("raw", ["see annexure", "N/A", "abc"])
def test_coerce_amount_rejects_garbage(raw):
    with pytest.raises(CoercionError):
        coerce_amount(raw)


def test_coerce_amount_rejects_overflow():
    with pytest.raises(CoercionError):
        coerce_amount("9" * 17)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2025-03-31", date(2025, 3, 31)),
        ("31-03-2025", date(2025, 3, 31)),
        ("31/03/2025", date(2025, 3, 31)),
        ("31 Mar 2025", date(2025, 3, 31)),
        ("2025-03-31T10:00:00", date(2025, 3, 31)),
        ("", None),
        (None, None),
    ],
)
def test_coerce_date(raw, expected):
    assert coerce_date(raw) == expected


@pytest.mark.parametrize("raw", ["not a date", "32-01-2025", "2025-13-01"])
def test_coerce_date_rejects_garbage(raw):
    with pytest.raises(CoercionError):
        coerce_date(raw)


def test_coerce_authority_normalizes_case():
    assert coerce_authority("gst") == "GST"


def test_coerce_authority_rejects_unknown():
    with pytest.raises(CoercionError):
        coerce_authority("CUSTOMS")


def test_coerce_notice_number_truncates():
    assert coerce_notice_number("X" * 200) == "X" * 100


def _blank_notice():
    return SimpleNamespace(
        notice_number="DRC-01/2026/1",
        authority="GST",
        received_date=date(2026, 1, 1),
        response_deadline=None,
        tax_demand=None,
        interest=None,
        penalty=None,
        total_liability=None,
    )


def _envelope():
    return {
        "fields": {
            "notice_number": {"value": "DRC-01/2026/9999", "confidence": 0.97},
            "response_deadline": {"value": "31-03-2026", "confidence": 0.95},
            "tax_demand": {"value": "₹1,45,000", "confidence": 0.93},
            "interest": {"value": "see order", "confidence": 0.4},
        },
        "average_confidence": 0.9,
        "model": "anthropic:test",
    }


def test_apply_fields_fills_empty_columns_with_coercion():
    notice = _blank_notice()
    _apply_fields_to_columns(notice, _envelope())
    # response_deadline + tax_demand were empty -> filled and coerced.
    assert notice.response_deadline == date(2026, 3, 31)
    assert notice.tax_demand == Decimal("145000.00")


def test_apply_fields_does_not_clobber_existing_value():
    notice = _blank_notice()
    # notice_number already set at creation -> a confident extraction must not
    # overwrite the human-entered value.
    _apply_fields_to_columns(notice, _envelope())
    assert notice.notice_number == "DRC-01/2026/1"
    # received_date already has the creation default -> untouched.
    assert notice.received_date == date(2026, 1, 1)


def test_apply_fields_skips_unparseable_value_without_raising():
    notice = _blank_notice()
    # interest='see order' cannot be coerced -> field skipped, never raises.
    _apply_fields_to_columns(notice, _envelope())
    assert notice.interest is None


class _FakeDB:
    def flush(self):
        pass


def test_apply_extraction_apply_decision_fills_and_marks_accepted():
    notice = _blank_notice()
    notice.extracted_fields = None
    notice.extraction_confidence = None
    notice.extracted_by_provider = None
    notice.extracted_at = None
    notice.extraction_status = "pending"
    apply_extraction_to_notice(
        _FakeDB(), notice, _envelope(), {"action": "apply"}
    )
    assert notice.extraction_status == "accepted"
    assert notice.tax_demand == Decimal("145000.00")
    assert notice.response_deadline == date(2026, 3, 31)


def test_apply_extraction_fill_columns_false_persists_envelope_only():
    notice = _blank_notice()
    notice.extracted_fields = None
    notice.extraction_confidence = None
    notice.extracted_by_provider = None
    notice.extracted_at = None
    notice.extraction_status = "pending"
    apply_extraction_to_notice(
        _FakeDB(), notice, _envelope(), {"action": "apply"}, fill_columns=False
    )
    # Replay path: envelope persisted, status 'completed', NO column writes.
    assert notice.extraction_status == "completed"
    assert notice.tax_demand is None
    assert notice.response_deadline is None
    assert notice.extracted_fields is not None
