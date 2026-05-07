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
    try:
        from app.email.models.fetch_log import GmailFetchLog  # noqa: F401
    except ImportError:
        pytest.skip("Plan 02 — GmailFetchLog ORM not yet implemented")
    pytest.skip("Plan 02 — three-state CHECK assertion lands then")


def test_two_consecutive_failed_triggers_alert():
    """2x FETCH_FAILED for same credential → Phase 11 gmail.fetch.failed alert dispatched (EMAIL-07)."""
    try:
        from app.email.services.scanner_service import record_fetch_outcome  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — scanner_service not yet implemented")
    pytest.skip("Plan 03 — alert-after-2-failures assertion lands then")
