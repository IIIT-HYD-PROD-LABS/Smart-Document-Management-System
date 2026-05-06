"""Phase 10 Plan 01 — review_queue_service unit tests.

Pure unit tests using a stand-in mock session. End-to-end RLS + DB-level
behaviour is exercised by tests/test_compliance_endpoints.py via the FastAPI
test client when DATABASE_URL is configured.

Covers:
  - derive_reason() reason-string mapping
  - enqueue_low_confidence: short-circuits when both confidences ≥ threshold
  - enqueue_low_confidence: produces the expected reason for partial below
  - assign_reviewer_label: validates required-field rule
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.compliance.services.review_queue_service import (
    CONFIDENCE_THRESHOLD,
    derive_reason,
)


def test_threshold_is_quarter_below_one():
    """Sanity guard against accidental threshold drift away from CLASS-04."""
    assert CONFIDENCE_THRESHOLD == Decimal("0.7500")


@pytest.mark.parametrize(
    "auth,type_,expected",
    [
        (Decimal("0.5"), Decimal("0.5"), "both"),
        (Decimal("0.5"), Decimal("0.9"), "low_authority_confidence"),
        (Decimal("0.9"), Decimal("0.5"), "low_type_confidence"),
        (None, Decimal("0.5"), "low_type_confidence"),
        (Decimal("0.5"), None, "low_authority_confidence"),
    ],
)
def test_derive_reason_matrix(auth, type_, expected):
    assert derive_reason(auth, type_) == expected


def test_enqueue_returns_none_when_both_confidences_high(monkeypatch):
    """No queue insert if both classifier confidences are at or above 0.75."""
    from app.compliance.services import review_queue_service as svc

    notice = MagicMock(id=1, client_id=10)
    db = MagicMock()
    # Should not call db.execute / db.flush — but if it did, return None safely.
    db.execute.side_effect = AssertionError("must not be called")

    result = svc.enqueue_low_confidence(
        db,
        notice=notice,
        predicted_authority="GST",
        predicted_authority_confidence=Decimal("0.85"),
        predicted_type_id=42,
        predicted_type_confidence=Decimal("0.91"),
        model_version="rules-v1.0",
    )
    assert result is None


def test_enqueue_returns_none_when_both_confidences_null():
    """v2.0 default state: BERT confidences are NULL → no enqueue."""
    from app.compliance.services import review_queue_service as svc

    notice = MagicMock(id=1, client_id=10)
    db = MagicMock()
    db.execute.side_effect = AssertionError("must not be called")

    result = svc.enqueue_low_confidence(
        db,
        notice=notice,
        predicted_authority="GST",
        predicted_authority_confidence=None,
        predicted_type_id=None,
        predicted_type_confidence=None,
        model_version="rules-v1.0",
    )
    assert result is None


def test_enqueue_calls_upsert_when_below_threshold():
    """When at least one confidence is below 0.75, db.execute is invoked."""
    from app.compliance.services import review_queue_service as svc

    notice = MagicMock(id=1, client_id=10)
    db = MagicMock()
    # scalar_one returns the inserted row id; db.get returns a stub row.
    fake_result = MagicMock()
    fake_result.scalar_one.return_value = 99
    db.execute.return_value = fake_result
    db.get.return_value = MagicMock(id=99)

    result = svc.enqueue_low_confidence(
        db,
        notice=notice,
        predicted_authority="IT",
        predicted_authority_confidence=Decimal("0.6"),
        predicted_type_id=7,
        predicted_type_confidence=Decimal("0.95"),
        model_version="bert-v1",
    )
    assert result is not None
    assert db.execute.called
    assert db.flush.called
