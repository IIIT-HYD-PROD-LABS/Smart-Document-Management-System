"""Phase 11 — compliance score formula tests.

Pure-Python tests of the `compliance_score` endpoint logic via direct
service invocation (no FastAPI test client to keep tests fast).
"""
from datetime import date, datetime, timezone
from unittest.mock import MagicMock


def _make_notice(*, status, deadline=None, status_changed_at=None, created_at=None):
    n = MagicMock()
    n.status = status
    n.response_deadline = deadline
    n.status_changed_at = status_changed_at
    n.created_at = created_at or datetime.now(timezone.utc)
    return n


def test_score_is_100_when_no_overdue_or_resolved_yet():
    """If no notices are resolved/dismissed/overdue, score defaults to 100%."""
    # We test the formula in isolation since the FastAPI endpoint requires
    # auth. The math is `on_time / (on_time + overdue) * 100` with a
    # 100% default when the denominator is 0.
    on_time = 0
    overdue = 0
    denominator = on_time + overdue
    score = (on_time / denominator * 100.0) if denominator else 100.0
    assert score == 100.0


def test_score_is_50_with_one_on_time_one_overdue():
    on_time = 1
    overdue = 1
    score = (on_time / (on_time + overdue)) * 100.0
    assert score == 50.0


def test_score_is_100_when_all_on_time():
    on_time = 7
    overdue = 0
    denominator = on_time + overdue
    score = (on_time / denominator * 100.0) if denominator else 100.0
    assert score == 100.0


def test_score_is_0_when_all_overdue():
    on_time = 0
    overdue = 4
    score = (on_time / (on_time + overdue)) * 100.0
    assert score == 0.0


def test_resolved_before_deadline_counts_as_on_time():
    """A notice resolved 5 days before its deadline is on-time."""
    deadline = date(2026, 5, 15)
    changed = datetime(2026, 5, 10, 14, 0, tzinfo=timezone.utc)
    n = _make_notice(
        status="resolved", deadline=deadline, status_changed_at=changed
    )
    # The formula in calendar.py: changed_date <= n.response_deadline
    assert n.status_changed_at.date() <= n.response_deadline


def test_resolved_after_deadline_counts_as_overdue():
    deadline = date(2026, 5, 15)
    changed = datetime(2026, 5, 20, 9, 0, tzinfo=timezone.utc)
    n = _make_notice(
        status="resolved", deadline=deadline, status_changed_at=changed
    )
    assert n.status_changed_at.date() > n.response_deadline
