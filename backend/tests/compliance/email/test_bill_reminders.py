"""Phase 15 — BILL-04 bill-reminder tests.

RED-state stub. Plan 03 adds `bill_t3`, `bill_t1`, `bill_overdue` to
`VALID_ALERT_TYPES` in `app/compliance/models/alert.py`. Plan 03 also
lands `bill_service.schedule_bill_reminders` enforcing max-3-per-bill
cool-down (D-22).
"""
from __future__ import annotations

import pytest


def test_bill_t3_t1_overdue_alert_types_registered():
    """VALID_ALERT_TYPES contains bill_t3, bill_t1, bill_overdue (BILL-04)."""
    try:
        from app.compliance.models.alert import VALID_ALERT_TYPES  # noqa: F401
    except ImportError:
        pytest.skip("VALID_ALERT_TYPES module unexpectedly missing — Phase 11 prerequisite")
    pytest.skip("Plan 03 — VALID_ALERT_TYPES extension assertion lands then")


def test_max_three_reminders_per_bill_cool_down():
    """schedule_bill_reminders refuses 4th reminder per bill lifetime (BILL-04 cool-down D-22)."""
    try:
        from app.email.services.bill_service import schedule_bill_reminders  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — schedule_bill_reminders not yet implemented")
    pytest.skip("Plan 03 — max-3 cool-down assertion lands then")
