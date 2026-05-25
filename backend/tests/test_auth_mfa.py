"""Endpoint flow tests for MFA login, enrollment, and per-account lockout.

Mock-DB style (mirrors test_auth.py): ``get_db`` is overridden with a MagicMock
and ``get_current_user`` is overridden for the protected enrollment endpoints.
Rate limiting is disabled. ``log_audit_event`` is patched on the failure/enable
paths so tests never touch the real audit table.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _user(**ov):
    d = dict(
        id=1, email="a@e.com", username="a", hashed_password="$2b$12$x",
        full_name="A", role="editor", auth_provider="local", oauth_id=None,
        is_active=True, created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc), deleted_at=None,
        mfa_enabled=False, totp_secret_enc=None, mfa_backup_codes_enc=None,
        mfa_enrolled_at=None, failed_login_count=0, locked_until=None,
    )
    d.update(ov)
    u = MagicMock()
    for k, v in d.items():
        setattr(u, k, v)
    return u


class _Q:
    def __init__(self, rv):
        self._rv = rv

    def filter(self, *a, **k):
        return self

    def with_for_update(self, **k):
        return self

    def first(self):
        return self._rv

    def count(self):
        return 0 if self._rv is None else 1


@pytest.fixture()
def client():
    from app.main import app
    from app.database import get_db
    from app.utils.rate_limiter import limiter

    mock_db = MagicMock()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    limiter.enabled = False
    yield TestClient(app), mock_db
    limiter.enabled = True
    app.dependency_overrides.clear()


def _as_user(user):
    """Override get_current_user so protected endpoints see `user`."""
    from app.main import app
    from app.utils.security import get_current_user
    app.dependency_overrides[get_current_user] = lambda: user


class TestLoginLockoutAndMfa:
    @patch("app.routers.auth.verify_password", return_value=True)
    def test_mfa_enabled_returns_challenge_not_tokens(self, _vp, client):
        tc, db = client
        db.query.return_value = _Q(_user(mfa_enabled=True))
        r = tc.post("/api/auth/login", json={"email": "a@e.com", "password": "x"})
        assert r.status_code == 200
        body = r.json()
        assert body.get("mfa_required") is True
        assert "mfa_token" in body and "access_token" not in body

    @patch("app.routers.auth.verify_password", return_value=True)
    def test_mfa_user_password_success_does_not_reset_lockout(self, _vp, client):
        # Regression: a correct password for an MFA account must NOT clear the
        # failure counter (only a full login via mfa_verify may), else the MFA
        # guess budget refills every round and lockout is unenforceable.
        tc, db = client
        user = _user(mfa_enabled=True, failed_login_count=4)
        db.query.return_value = _Q(user)
        r = tc.post("/api/auth/login", json={"email": "a@e.com", "password": "x"})
        assert r.status_code == 200 and r.json().get("mfa_required") is True
        assert user.failed_login_count == 4 and user.locked_until is None

    def test_locked_account_returns_429(self, client):
        tc, db = client
        db.query.return_value = _Q(_user(locked_until=datetime.now(timezone.utc) + timedelta(minutes=10)))
        r = tc.post("/api/auth/login", json={"email": "a@e.com", "password": "x"})
        assert r.status_code == 429

    @patch("app.services.audit_service.log_audit_event")
    @patch("app.routers.auth.verify_password", return_value=False)
    def test_bad_password_locks_at_threshold(self, _vp, _audit, client):
        tc, db = client
        user = _user(failed_login_count=4)  # next failure -> 5 -> lock
        db.query.return_value = _Q(user)
        r = tc.post("/api/auth/login", json={"email": "a@e.com", "password": "x"})
        assert r.status_code == 429
        assert user.failed_login_count == 5 and user.locked_until is not None

    @patch("app.services.audit_service.log_audit_event")
    @patch("app.routers.auth.verify_password", return_value=False)
    def test_bad_password_below_threshold_returns_401(self, _vp, _audit, client):
        tc, db = client
        user = _user(failed_login_count=0)
        db.query.return_value = _Q(user)
        r = tc.post("/api/auth/login", json={"email": "a@e.com", "password": "x"})
        assert r.status_code == 401
        assert user.failed_login_count == 1


class TestMfaVerify:
    @patch("app.routers.auth.create_refresh_token", return_value=("ref", datetime.now(timezone.utc) + timedelta(days=7)))
    @patch("app.routers.auth.create_access_token", return_value="acc")
    @patch("app.routers.auth.mfa_service.verify_totp", return_value=True)
    @patch("app.routers.auth.mfa_service.decrypt_secret", return_value="SECRET")
    def test_valid_totp_returns_tokens(self, _ds, _vt, _ca, _cr, client):
        from app.services import mfa_service
        tc, db = client
        db.query.return_value = _Q(_user(mfa_enabled=True, totp_secret_enc=b"x"))
        token = mfa_service.issue_challenge_token(1)
        r = tc.post("/api/auth/mfa/verify", json={"mfa_token": token, "code": "123456"})
        assert r.status_code == 200 and r.json()["access_token"] == "acc"

    @patch("app.services.audit_service.log_audit_event")
    @patch("app.routers.auth.mfa_service.verify_totp", return_value=False)
    @patch("app.routers.auth.mfa_service.decrypt_secret", return_value="SECRET")
    def test_bad_code_returns_401_and_counts_failure(self, _ds, _vt, _audit, client):
        from app.services import mfa_service
        tc, db = client
        user = _user(mfa_enabled=True, totp_secret_enc=b"x")
        db.query.return_value = _Q(user)
        token = mfa_service.issue_challenge_token(1)
        r = tc.post("/api/auth/mfa/verify", json={"mfa_token": token, "code": "000000"})
        assert r.status_code == 401 and user.failed_login_count == 1

    def test_garbage_token_returns_401(self, client):
        tc, db = client
        r = tc.post("/api/auth/mfa/verify", json={"mfa_token": "garbage.token", "code": "123456"})
        assert r.status_code == 401


class TestEnrollment:
    def test_enroll_returns_secret_and_qr(self, client):
        tc, db = client
        user = _user(mfa_enabled=False)
        _as_user(user)
        r = tc.post("/api/auth/totp/enroll")
        assert r.status_code == 200
        b = r.json()
        assert b["secret"] and b["qr_data_uri"].startswith("data:image/png;base64,")
        assert user.totp_secret_enc is not None  # pending secret stored, not yet enabled
        assert user.mfa_enabled is False

    @patch("app.services.audit_service.log_audit_event")
    @patch("app.routers.auth.mfa_service.verify_totp", return_value=True)
    @patch("app.routers.auth.mfa_service.decrypt_secret", return_value="JBSWY3DPEHPK3PXP")
    def test_confirm_enables_and_returns_backup_codes(self, _ds, _vt, _audit, client):
        tc, db = client
        user = _user(mfa_enabled=False, totp_secret_enc=b"x")
        _as_user(user)
        r = tc.post("/api/auth/totp/confirm", json={"code": "123456"})
        assert r.status_code == 200
        assert len(r.json()["backup_codes"]) >= 8
        assert user.mfa_enabled is True and user.mfa_backup_codes_enc is not None

    def test_enroll_blocked_when_already_enabled(self, client):
        tc, db = client
        _as_user(_user(mfa_enabled=True))
        r = tc.post("/api/auth/totp/enroll")
        assert r.status_code == 400
