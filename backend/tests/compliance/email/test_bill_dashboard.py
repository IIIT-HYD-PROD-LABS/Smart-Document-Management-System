"""Phase 15 — BILL-03 bill dashboard tests.

RED-state stub. Plan 03 lands `bill_service.list_bills` with filter
buckets (upcoming / due_soon / overdue / paid) and a bulk mark-as-paid
service method.
"""
from __future__ import annotations

import pytest


def test_filter_upcoming_due_soon_overdue_paid():
    """list_bills(filter='due_soon') returns bills due within next 7 days (BILL-03)."""
    try:
        from app.email.services.bill_service import list_bills  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — bill_service.list_bills not yet implemented")
    pytest.skip("Plan 03 — filter bucket assertion lands then")


def test_bulk_mark_as_paid_atomically():
    """bulk_mark_paid([bill_ids]) updates all-or-nothing in a transaction (BILL-03)."""
    try:
        from app.email.services.bill_service import bulk_mark_paid  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — bulk_mark_paid not yet implemented")
    pytest.skip("Plan 03 — atomic bulk update assertion lands then")
