"""Phase 15 — BILL-05 mark-as-paid tests.

RED-state stub. Plan 03 lands `bill_service.mark_paid` enforcing the
state machine (pending|overdue → paid), recording payment_method/date/
reference, writing an audit log row, and cancelling pending reminders.
"""
from __future__ import annotations

import pytest


def test_mark_paid_records_payment_method_date_reference():
    """mark_paid persists payment_method, payment_date, payment_reference on the bill row (BILL-05)."""
    try:
        from app.email.services.bill_service import mark_paid  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — mark_paid not yet implemented")
    pytest.skip("Plan 03 — payment metadata persistence assertion lands then")


def test_mark_paid_writes_audit_log():
    """mark_paid calls log_audit_event with action=BILL_MARK_PAID (BILL-05 + Phase 9 audit)."""
    try:
        from app.email.services.bill_service import mark_paid  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — mark_paid not yet implemented")
    pytest.skip("Plan 03 — audit log row assertion lands then")


def test_mark_paid_cancels_pending_reminders():
    """mark_paid cancels APScheduler bill_t3/bill_t1 jobs for the bill (BILL-05)."""
    try:
        from app.email.services.bill_service import mark_paid  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — mark_paid not yet implemented")
    pytest.skip("Plan 03 — reminder cancellation assertion lands then")
