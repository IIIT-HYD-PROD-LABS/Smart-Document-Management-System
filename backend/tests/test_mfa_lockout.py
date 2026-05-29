"""Unit tests for TOTP MFA + per-account lockout service logic.

Pure logic (no DB, no HTTP). A throwaway FERNET_KEY is set so the encryption
paths are hermetic regardless of the container's .env.
"""
import types
from datetime import datetime, timedelta, timezone

import pyotp
import pytest
from cryptography.fernet import Fernet

from app.config import settings
from app.compliance.utils.pii_encryption import reset_cipher_cache
from app.services import mfa_service, lockout_service


@pytest.fixture(autouse=True)
def _fernet_key(monkeypatch):
    monkeypatch.setenv("FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.delenv("FERNET_KEY_OLD", raising=False)
    reset_cipher_cache()
    yield
    reset_cipher_cache()


# ---------------- TOTP ----------------
def test_totp_secret_is_unique_base32():
    s1, s2 = mfa_service.generate_totp_secret(), mfa_service.generate_totp_secret()
    assert s1 != s2 and len(s1) >= 16


def test_verify_totp_accepts_current_and_rejects_wrong():
    secret = mfa_service.generate_totp_secret()
    assert mfa_service.verify_totp(secret, pyotp.TOTP(secret).now()) is True
    assert mfa_service.verify_totp(secret, "000000") is False
    assert mfa_service.verify_totp(secret, "") is False


def test_secret_encryption_roundtrip():
    secret = mfa_service.generate_totp_secret()
    blob = mfa_service.encrypt_secret(secret)
    assert isinstance(blob, bytes) and blob != secret.encode()
    assert mfa_service.decrypt_secret(blob) == secret


def test_provisioning_uri_carries_issuer_and_account():
    uri = mfa_service.provisioning_uri("JBSWY3DPEHPK3PXP", "alice@example.com")
    assert uri.startswith("otpauth://totp/")
    assert "issuer=TaxSync" in uri


# ---------------- backup codes ----------------
def test_backup_codes_count_unique_formatted():
    codes = mfa_service.generate_backup_codes()
    assert len(codes) == settings.MFA_BACKUP_CODE_COUNT
    assert len(set(codes)) == len(codes)
    assert all(c.count("-") == 3 for c in codes)


def test_backup_code_is_single_use():
    codes = mfa_service.generate_backup_codes(3)
    blob = mfa_service.encrypt_backup_codes(codes)
    ok, blob2 = mfa_service.verify_and_consume_backup_code(blob, codes[0])
    assert ok is True and blob2 is not None
    ok_again, _ = mfa_service.verify_and_consume_backup_code(blob2, codes[0])
    assert ok_again is False
    ok2, _ = mfa_service.verify_and_consume_backup_code(blob2, codes[1])
    assert ok2 is True


def test_backup_code_normalizes_hyphens_and_case():
    codes = mfa_service.generate_backup_codes(1)
    typed = codes[0].replace("-", "").lower()
    ok, _ = mfa_service.verify_and_consume_backup_code(
        mfa_service.encrypt_backup_codes(codes), typed
    )
    assert ok is True


def test_backup_code_rejects_unknown():
    blob = mfa_service.encrypt_backup_codes(mfa_service.generate_backup_codes(2))
    ok, newblob = mfa_service.verify_and_consume_backup_code(blob, "ZZZZZ-ZZZZZ-ZZZZZ-ZZZZZ")
    assert ok is False and newblob is None


# ---------------- challenge token ----------------
def test_challenge_token_roundtrip():
    assert mfa_service.decode_challenge_token(mfa_service.issue_challenge_token(42)) == 42


def test_challenge_token_rejects_access_token_and_garbage():
    from app.utils.security import create_access_token

    with pytest.raises(ValueError):
        mfa_service.decode_challenge_token(create_access_token({"sub": "42"}))
    with pytest.raises(ValueError):
        mfa_service.decode_challenge_token("not.a.jwt")


# ---------------- lockout ----------------
def _user(**kw):
    base = dict(failed_login_count=0, locked_until=None)
    base.update(kw)
    return types.SimpleNamespace(**base)


def test_lockout_triggers_at_threshold():
    u = _user()
    for _ in range(settings.MAX_FAILED_LOGINS - 1):
        assert lockout_service.register_failure(u) is False
        assert lockout_service.is_locked(u) is False
    assert lockout_service.register_failure(u) is True
    assert lockout_service.is_locked(u) is True
    assert lockout_service.seconds_remaining(u) > 0


def test_reset_clears_lock():
    u = _user(failed_login_count=9, locked_until=datetime.now(timezone.utc) + timedelta(minutes=15))
    lockout_service.reset(u)
    assert u.failed_login_count == 0 and u.locked_until is None
    assert lockout_service.is_locked(u) is False


def test_expired_lock_reads_as_unlocked():
    u = _user(locked_until=datetime.now(timezone.utc) - timedelta(minutes=1))
    assert lockout_service.is_locked(u) is False


def test_backoff_doubles_past_threshold():
    u = _user()
    for _ in range(settings.MAX_FAILED_LOGINS):
        lockout_service.register_failure(u)
    first = lockout_service.seconds_remaining(u)
    lockout_service.register_failure(u)
    assert lockout_service.seconds_remaining(u) > first
