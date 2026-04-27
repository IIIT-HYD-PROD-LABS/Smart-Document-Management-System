"""RBAC-04: Auditor time-bound access enforced on every request."""

from datetime import datetime, timezone

import pytest


pytestmark = pytest.mark.integration


def test_expired_membership_rejected(freezer, db_as_app_runtime, auditor_membership):
    auditor_membership.access_end = datetime(2026, 4, 30, tzinfo=timezone.utc)
    db_as_app_runtime.commit()
    freezer.move_to("2026-05-01")
    # The middleware uses datetime.now(); freezer freezes it
    from app.compliance.middleware.auditor_expiry import is_membership_active
    assert is_membership_active(auditor_membership) is False


def test_future_access_start_blocked(freezer, db_as_app_runtime, auditor_membership):
    auditor_membership.access_start = datetime(2026, 6, 1, tzinfo=timezone.utc)
    db_as_app_runtime.commit()
    freezer.move_to("2026-04-01")  # before access_start
    from app.compliance.middleware.auditor_expiry import is_membership_active
    assert is_membership_active(auditor_membership) is False


def test_active_window_allows(freezer, db_as_app_runtime, auditor_membership):
    auditor_membership.access_start = datetime(2026, 4, 1, tzinfo=timezone.utc)
    auditor_membership.access_end = datetime(2026, 6, 1, tzinfo=timezone.utc)
    db_as_app_runtime.commit()
    freezer.move_to("2026-05-01")
    from app.compliance.middleware.auditor_expiry import is_membership_active
    assert is_membership_active(auditor_membership) is True
