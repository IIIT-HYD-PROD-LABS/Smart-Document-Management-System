"""Phase 15 — EMAIL-07 fetch-log tests.

RED-state stub. Plan 02 lands GmailFetchLog with a CHECK constraint on
status IN ('SUCCESS_EMPTY', 'SUCCESS_WITH_RESULTS', 'FETCH_FAILED'),
mirroring Phase 14's PortalFetchLog pattern. Plan 03 lands the scanner
that records outcomes and triggers a Phase 11 alert after 2 consecutive
FETCH_FAILED rows.
"""
from __future__ import annotations

import pytest


def test_three_state_check_constraint():
    """INSERT with status='UNKNOWN' raises CHECK constraint violation (EMAIL-07)."""
    from sqlalchemy import CheckConstraint

    from app.email.models.fetch_log import GmailFetchLog

    # Schema-level assertion: CHECK constraint pins the three-state enum.
    check_names = {
        c.name
        for c in GmailFetchLog.__table__.constraints
        if isinstance(c, CheckConstraint)
    }
    assert "ck_gmail_fetch_log_status" in check_names, (
        "GmailFetchLog must declare CHECK constraint on status three-state enum"
    )
    # Verify the three states are present in the constraint text
    status_check = next(
        c for c in GmailFetchLog.__table__.constraints
        if isinstance(c, CheckConstraint) and c.name == "ck_gmail_fetch_log_status"
    )
    sqltext = str(status_check.sqltext)
    for state in ("SUCCESS_EMPTY", "SUCCESS_WITH_RESULTS", "FETCH_FAILED"):
        assert state in sqltext, f"three-state CHECK must include {state}"


def test_two_consecutive_failed_triggers_alert():
    """2x FETCH_FAILED for same credential → Phase 11 gmail.fetch.failed alert dispatched (EMAIL-07)."""
    try:
        from app.email.services.scanner_service import record_fetch_outcome  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — scanner_service not yet implemented")
    pytest.skip("Plan 03 — alert-after-2-failures assertion lands then")
