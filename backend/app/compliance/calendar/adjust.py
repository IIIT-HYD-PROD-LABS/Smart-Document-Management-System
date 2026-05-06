"""Pure deadline-adjustment function — Phase 11 D-12.

If a deadline falls on Sunday OR an Indian gazetted holiday in the
applicable state, advance to the next working day.

This is a pure function (no DB, no I/O) so risk-scoring (Phase 10) and
alert scheduling (Phase 11) can both call it without the holiday
calendar being a remote-fetch concern.

The `holidays` library is the data source for gazetted dates; the input
`state_code` follows the ISO 3166-2:IN convention (e.g. "IN-MH" for
Maharashtra) — the library's IndiaHolidays class accepts the
2-letter state suffix.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from typing import Optional


_INDIAN_STATE_PREFIX_MAP = {
    "AN": "Andaman and Nicobar Islands",
    "AP": "Andhra Pradesh",
    "AR": "Arunachal Pradesh",
    "AS": "Assam",
    "BR": "Bihar",
    "CH": "Chandigarh",
    "CT": "Chhattisgarh",
    "DL": "Delhi",
    "GA": "Goa",
    "GJ": "Gujarat",
    "HP": "Himachal Pradesh",
    "HR": "Haryana",
    "JH": "Jharkhand",
    "JK": "Jammu and Kashmir",
    "KA": "Karnataka",
    "KL": "Kerala",
    "LA": "Ladakh",
    "MH": "Maharashtra",
    "ML": "Meghalaya",
    "MN": "Manipur",
    "MP": "Madhya Pradesh",
    "MZ": "Mizoram",
    "NL": "Nagaland",
    "OR": "Odisha",
    "PB": "Punjab",
    "PY": "Puducherry",
    "RJ": "Rajasthan",
    "SK": "Sikkim",
    "TG": "Telangana",
    "TN": "Tamil Nadu",
    "TR": "Tripura",
    "UK": "Uttarakhand",
    "UP": "Uttar Pradesh",
    "WB": "West Bengal",
}


@lru_cache(maxsize=8)
def _india_holidays(year: int, state_code: Optional[str] = None):
    """Lazy-imported holiday calendar for a given year + state.

    Cached because constructing the calendar parses files on first call.
    """
    try:
        import holidays  # type: ignore[import-not-found]
    except ImportError:
        # If the library isn't installed (degraded environment), return empty
        # set — the function still works, it just won't recognize gazetted
        # holidays. Sundays are still rejected.
        return {}

    kwargs = {"years": [year]}
    if state_code and state_code.startswith("IN-"):
        suffix = state_code.split("-", 1)[1]
        if suffix in _INDIAN_STATE_PREFIX_MAP:
            kwargs["subdiv"] = suffix
    return holidays.country_holidays("IN", **kwargs)


def is_working_day(d: date, state_code: Optional[str] = None) -> bool:
    """True iff `d` is not a Sunday and not a gazetted holiday.

    `state_code` follows ISO 3166-2:IN (e.g. "IN-MH"). When None or
    unrecognized, only central holidays are considered.
    """
    if d.weekday() == 6:  # Sunday
        return False
    cal = _india_holidays(d.year, state_code)
    return d not in cal


def adjust_deadline(
    d: date,
    state_code: Optional[str] = None,
    max_skip_days: int = 14,
) -> date:
    """Forward-shift `d` to the next working day.

    Args:
        d: Original deadline.
        state_code: ISO 3166-2:IN state code; None = central-only.
        max_skip_days: Safety cap to prevent runaway loops on a corrupted
            holiday calendar. Returns the input unchanged if exceeded.

    Returns:
        Working day on or after `d`.
    """
    candidate = d
    for _ in range(max_skip_days + 1):
        if is_working_day(candidate, state_code):
            return candidate
        candidate = candidate + timedelta(days=1)
    return d
