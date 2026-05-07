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
    # Schema-level assertion lands now (Plan 02). The full service-level
    # behavior (detect_recurrence picking the right cluster) lands in Plan 03.
    from sqlalchemy import create_engine, text
    import os

    eng = create_engine(os.environ.get("DATABASE_URL_RUNTIME") or os.environ["DATABASE_URL"])
    with eng.connect() as conn:
        result = conn.execute(text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE indexname = 'ux_bills_recurrence_key'"
        )).fetchone()
        assert result is not None, "ux_bills_recurrence_key partial unique index must exist"
        indexdef = result[0]
        assert "UNIQUE" in indexdef.upper(), "ux_bills_recurrence_key must be UNIQUE"
        assert "account_number_last4 IS NOT NULL" in indexdef, (
            "ux_bills_recurrence_key must be partial WHERE account_number_last4 IS NOT NULL"
        )
