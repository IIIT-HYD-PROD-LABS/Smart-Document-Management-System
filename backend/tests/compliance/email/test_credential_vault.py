"""Phase 15 — EMAIL-03 credential vault tests.

RED-state stub. Plan 03 lands credential_vault + access_token_cache.
"""
from __future__ import annotations

import pytest


def test_refresh_token_fernet_round_trip():
    """save_credential encrypts refresh_token; load_credential decrypts (EMAIL-03)."""
    try:
        from app.email.services.credential_vault import save_credential, load_credential  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — credential_vault not yet implemented")
    pytest.skip("Plan 03 — full Fernet round-trip lands then")


def test_access_token_never_persisted_to_db():
    """get_or_refresh_access_token writes to Redis only; no DB columns hold access tokens (EMAIL-03)."""
    try:
        from app.email.services.access_token_cache import get_or_refresh_access_token  # noqa: F401
    except ImportError:
        pytest.skip("Plan 03 — access_token_cache not yet implemented")
    pytest.skip("Plan 03 — Redis-only assertion lands then")
