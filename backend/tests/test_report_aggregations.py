"""Phase 13 report_service aggregation tests — pure-Python with MagicMock."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.compliance.services.report_service import (
    _window_start,
    notice_volume_by_status,
    penalty_by_authority,
    response_time_distribution,
)


def test_window_start_returns_aware_utc():
    """Window helper must return tz-aware datetime to compare safely with
    `created_at` columns."""
    out = _window_start(30)
    assert out.tzinfo is not None
    delta = datetime.now(timezone.utc) - out
    assert timedelta(days=29, hours=23) < delta < timedelta(days=30, hours=1)


def test_penalty_by_authority_returns_typed_rows():
    db = MagicMock()
    fake_row = MagicMock()
    fake_row.authority = "GST"
    fake_row.count = 3
    fake_row.total_penalty = 1500000
    fake_row.total_tax_demand = 800000
    db.query.return_value.filter.return_value.group_by.return_value.order_by.return_value.all.return_value = [
        fake_row
    ]

    out = penalty_by_authority(db, client_id=42, window_days=90)
    assert len(out) == 1
    assert out[0]["authority"] == "GST"
    assert out[0]["count"] == 3
    assert out[0]["total_penalty"] == 1500000.0
    assert isinstance(out[0]["total_penalty"], float)


def test_notice_volume_by_status_returns_dicts():
    db = MagicMock()
    rows = [
        MagicMock(status="received", count=5),
        MagicMock(status="resolved", count=2),
    ]
    db.query.return_value.filter.return_value.group_by.return_value.all.return_value = rows
    out = notice_volume_by_status(db, client_id=1, window_days=30)
    assert out == [
        {"status": "received", "count": 5},
        {"status": "resolved", "count": 2},
    ]


def test_response_time_distribution_handles_empty():
    """Empty percentile result should not propagate None — return zeros."""
    db = MagicMock()
    fake = MagicMock()
    fake.count = 0
    fake.p50 = None
    fake.p90 = None
    fake.p95 = None
    fake.mean = None
    db.execute.return_value.fetchone.return_value = fake
    out = response_time_distribution(db, client_id=1, window_days=90)
    assert out == {"p50": 0.0, "p90": 0.0, "p95": 0.0, "mean": 0.0, "count": 0}


def test_response_time_distribution_returns_floats():
    db = MagicMock()
    fake = MagicMock()
    fake.count = 5
    fake.p50 = 2.5
    fake.p90 = 7.0
    fake.p95 = 12.0
    fake.mean = 4.2
    db.execute.return_value.fetchone.return_value = fake
    out = response_time_distribution(db, client_id=1, window_days=90)
    assert out == {"p50": 2.5, "p90": 7.0, "p95": 12.0, "mean": 4.2, "count": 5}
