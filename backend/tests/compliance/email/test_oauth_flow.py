"""Phase 15 — EMAIL-01 OAuth round-trip tests.

RED-state stub. Plan 03 lands GmailOAuth + the /oauth/callback route.
"""
from __future__ import annotations

import pytest


def test_authorize_url_includes_consent_and_offline():
    """authorize_url() returns Google consent URL with prompt=consent + access_type=offline (EMAIL-01)."""
    try:
        from app.email.services.oauth_service import GmailOAuth  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — GmailOAuth service not yet implemented")
    pytest.skip("Plan 03 — full behavior assertions land then")


def test_callback_persists_refresh_token_encrypted():
    """OAuth callback exchanges code, persists refresh_token Fernet-encrypted (EMAIL-01 + EMAIL-03)."""
    try:
        from app.email.routers.oauth import gmail_oauth_callback  # noqa: F401
    except ImportError:
        pytest.skip("Plan 05 — gmail_oauth_callback router not yet implemented")
    pytest.skip("Plan 05 — full behavior assertions land then")


def test_state_jwt_csrf_validation():
    """state JWT signed with SECRET_KEY; mismatched state rejected with 400 (EMAIL-01)."""
    try:
        from app.email.services.oauth_service import GmailOAuth  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — GmailOAuth service not yet implemented")
    pytest.skip("Plan 03 — CSRF state validation lands then")
