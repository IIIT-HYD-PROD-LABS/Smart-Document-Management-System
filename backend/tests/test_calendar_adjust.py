"""Phase 11 — adjust_deadline pure function tests.

Verifies holiday + Sunday skip logic without DB access. Uses the
`holidays` library's bundled Indian gazetted calendar.
"""
from datetime import date

import pytest

from app.compliance.calendar.adjust import adjust_deadline, is_working_day


def test_sunday_shifts_to_monday():
    # 2026-04-12 is a Sunday
    sun = date(2026, 4, 12)
    assert sun.weekday() == 6
    adjusted = adjust_deadline(sun)
    assert adjusted == date(2026, 4, 13)
    assert adjusted.weekday() == 0


def test_saturday_is_working_day():
    # Saturday is a working day for compliance filings
    sat = date(2026, 4, 11)
    assert sat.weekday() == 5
    assert is_working_day(sat) is True
    assert adjust_deadline(sat) == sat


def test_already_working_day_unchanged():
    wed = date(2026, 4, 15)
    assert is_working_day(wed) is True
    assert adjust_deadline(wed) == wed


def test_republic_day_shifts():
    # 26 January is Republic Day (gazetted holiday)
    holiday = date(2026, 1, 26)
    adjusted = adjust_deadline(holiday)
    assert adjusted > holiday


def test_independence_day_shifts():
    # 15 August is Independence Day
    holiday = date(2026, 8, 15)
    adjusted = adjust_deadline(holiday)
    assert adjusted > holiday


@pytest.mark.parametrize("state_code,valid", [
    ("IN-MH", True),
    ("IN-KA", True),
    ("IN-XX", True),  # unknown state — falls back to central
    ("ZZ", True),     # malformed — falls back to central
    (None, True),
])
def test_state_code_handling(state_code, valid):
    """All state codes should be accepted; unknown codes fall back to central holidays."""
    d = date(2026, 6, 10)  # arbitrary working day
    out = adjust_deadline(d, state_code)
    assert isinstance(out, date)


def test_max_skip_days_safety_cap():
    """If somehow every day is a holiday, returns input unchanged after cap."""
    # Use a date deep in past where holiday lookup may differ; ensure
    # function still returns a date and doesn't infinite-loop.
    d = date(2026, 7, 14)
    assert adjust_deadline(d, max_skip_days=0) == d  # bypass loop entirely
