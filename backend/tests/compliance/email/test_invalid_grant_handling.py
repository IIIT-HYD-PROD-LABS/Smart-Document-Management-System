"""Phase 15 — EMAIL-10 connection health tests.

RED-state stub. Plan 03 lands `credential_vault.handle_invalid_grant`,
which on `google.auth.exceptions.RefreshError` marks the credential
status=REVOKED, disables the APScheduler job, and emits a
`gmail.connection.lost` event through the Phase 11 alert pipeline.
"""
from __future__ import annotations

import pytest


def test_refresh_error_marks_credential_revoked():
    """RefreshError → credential.status='REVOKED' (EMAIL-10)."""
    try:
        from app.email.services.credential_vault import handle_invalid_grant  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — handle_invalid_grant not yet implemented")
    pytest.skip("Plan 03 — REVOKED status assertion lands then")


def test_invalid_grant_disables_scanner_job():
    """RefreshError → APScheduler job for credential is paused/removed (EMAIL-10)."""
    try:
        from app.email.services.credential_vault import handle_invalid_grant  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — handle_invalid_grant not yet implemented")
    pytest.skip("Plan 03 — scanner job disable assertion lands then")


def test_invalid_grant_emits_connection_lost_event():
    """RefreshError → emits gmail.connection.lost alert (EMAIL-10 + Phase 11 alert pipeline)."""
    try:
        from app.email.services.credential_vault import handle_invalid_grant  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — handle_invalid_grant not yet implemented")
    pytest.skip("Plan 03 — gmail.connection.lost event assertion lands then")
