"""Phase 15 — BILL-06 recurring-bill detection tests.

RED-state stub. Plan 03 lands `bill_service.detect_recurrence`, which
clusters by normalized (biller_name, account_number_last4) and links
matches via `parent_bill_id`.
"""
from __future__ import annotations

import pytest


def test_parent_bill_id_links_matching_biller_and_last4():
    """Two bills with same biller + last4 → second.parent_bill_id == first.id (BILL-06)."""
    try:
        from app.email.services.bill_service import detect_recurrence  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — bill_service.detect_recurrence not yet implemented")
    pytest.skip("Plan 03 — parent_bill_id linking assertion lands then")


def test_null_last4_does_not_link_two_unrelated_bills():
    """Partial unique index on (biller, last4) WHERE last4 IS NOT NULL — null last4 must NOT collide (Pitfall 8)."""
    try:
        from app.email.services.bill_service import detect_recurrence  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — bill_service.detect_recurrence not yet implemented")
    pytest.skip("Plan 02 — partial unique index migration lands then")
