"""Tests for security utilities and schema validation.

All tests run without a database connection.
"""

import re
import string
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from pydantic import ValidationError

from app.schemas import UserLogin, UserRegister
from app.utils.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    verify_password,
)

# ---------------------------------------------------------------------------
# Shared helpers / constants
# ---------------------------------------------------------------------------

TEST_SECRET_KEY = "test-secret-key-that-is-long-enough-for-validation-1234567890"
TEST_ALGORITHM = "HS256"


def _mock_settings():
    """Return a MagicMock that behaves like app.config.settings."""
    s = MagicMock()
    s.SECRET_KEY = TEST_SECRET_KEY
    s.ALGORITHM = TEST_ALGORITHM
    s.ACCESS_TOKEN_EXPIRE_MINUTES = 30
    s.REFRESH_TOKEN_EXPIRE_DAYS = 7
    return s


# =========================================================================
# 1. Password hashing
# =========================================================================


class TestPasswordHashing:
    """Tests for hash_password and verify_password."""

    def test_hash_password_returns_bcrypt_hash(self):
        hashed = hash_password("StrongP@ss1")
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$")

    def test_verify_password_accepts_correct_password(self):
        password = "C0rrect!Horse"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_rejects_wrong_password(self):
        hashed = hash_password("C0rrect!Horse")
        assert verify_password("Wr0ng!Horse", hashed) is False

    def test_hash_password_produces_unique_hashes(self):
        password = "SameP@ss1"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2, "Each call should produce a different salt"


# =========================================================================
# 2. Access token creation / decoding
# =========================================================================


class TestAccessToken:
    """Tests for create_access_token and decode_access_token."""

    @patch("app.utils.security.settings", new_callable=_mock_settings)
    def test_create_access_token_returns_valid_jwt(self, mock_settings):
        token = create_access_token({"sub": "42"})
        assert isinstance(token, str)
        # Manually decode to confirm it is a real JWT
        payload = jwt.decode(token, TEST_SECRET_KEY, algorithms=[TEST_ALGORITHM])
        assert payload["sub"] == "42"

    @patch("app.utils.security.settings", new_callable=_mock_settings)
    def test_decode_access_token_returns_payload(self, mock_settings):
        token = create_access_token({"sub": "7", "role": "admin"})
        payload = decode_access_token(token)
        assert payload["sub"] == "7"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    @patch("app.utils.security.settings", new_callable=_mock_settings)
    def test_expired_token_raises_401(self, mock_settings):
        token = create_access_token(
            {"sub": "1"}, expires_delta=timedelta(seconds=-1)
        )
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    @patch("app.utils.security.settings", new_callable=_mock_settings)
    def test_wrong_token_type_raises_401(self, mock_settings):
        token = create_access_token({"sub": "1", "type": "refresh"})
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)
        assert exc_info.value.status_code == 401
        assert "token type" in exc_info.value.detail.lower()

    @patch("app.utils.security.settings", new_callable=_mock_settings)
    def test_access_token_includes_jti(self, mock_settings):
        token = create_access_token({"sub": "99"})
        payload = decode_access_token(token)
        assert "jti" in payload
        assert isinstance(payload["jti"], str)
        assert len(payload["jti"]) > 0

    @patch("app.utils.security.settings", new_callable=_mock_settings)
    def test_access_token_default_type_is_access(self, mock_settings):
        token = create_access_token({"sub": "5"})
        payload = decode_access_token(token)
        assert payload["type"] == "access"

    @patch("app.utils.security.settings", new_callable=_mock_settings)
    def test_invalid_token_string_raises_401(self, mock_settings):
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token("not-a-valid-jwt")
        assert exc_info.value.status_code == 401


# =========================================================================
# 3. Refresh token creation
# =========================================================================


class TestRefreshToken:
    """Tests for create_refresh_token."""

    @patch("app.utils.security.settings", new_callable=_mock_settings)
    def test_returns_tuple_of_token_and_datetime(self, mock_settings):
        result = create_refresh_token()
        assert isinstance(result, tuple)
        assert len(result) == 2
        token, expires_at = result
        assert isinstance(token, str)
        assert isinstance(expires_at, datetime)

    @patch("app.utils.security.settings", new_callable=_mock_settings)
    def test_token_is_url_safe(self, mock_settings):
        token, _ = create_refresh_token()
        url_safe_chars = set(string.ascii_letters + string.digits + "-_=")
        assert all(c in url_safe_chars for c in token)

    @patch("app.utils.security.settings", new_callable=_mock_settings)
    def test_expiry_is_in_the_future(self, mock_settings):
        _, expires_at = create_refresh_token()
        assert expires_at > datetime.now(timezone.utc)

    @patch("app.utils.security.settings", new_callable=_mock_settings)
    def test_expiry_matches_configured_days(self, mock_settings):
        before = datetime.now(timezone.utc)
        _, expires_at = create_refresh_token()
        after = datetime.now(timezone.utc)
        expected_min = before + timedelta(days=7)
        expected_max = after + timedelta(days=7)
        assert expected_min <= expires_at <= expected_max


# =========================================================================
# 4. Schema validation
# =========================================================================


class TestUserRegisterSchema:
    """Tests for the UserRegister Pydantic schema."""

    _VALID_KWARGS = {
        "email": "Test@Example.COM",
        "username": "johndoe",
        "password": "Str0ng!Pass",
        "full_name": "John Doe",
    }

    def test_rejects_password_without_uppercase(self):
        with pytest.raises(ValidationError, match="uppercase"):
            UserRegister(**{**self._VALID_KWARGS, "password": "nouppercase1!"})

    def test_rejects_password_without_digit(self):
        with pytest.raises(ValidationError, match="digit"):
            UserRegister(**{**self._VALID_KWARGS, "password": "NoDigitsHere!"})

    def test_rejects_password_without_special_char(self):
        with pytest.raises(ValidationError, match="special"):
            UserRegister(**{**self._VALID_KWARGS, "password": "NoSpecial1A"})

    def test_rejects_password_too_short(self):
        with pytest.raises(ValidationError):
            UserRegister(**{**self._VALID_KWARGS, "password": "Sh0r!t"})

    def test_rejects_password_too_long(self):
        long_pw = "A1!" + "a" * 126  # 129 chars, exceeds max_length=128
        with pytest.raises(ValidationError):
            UserRegister(**{**self._VALID_KWARGS, "password": long_pw})

    def test_normalizes_email_to_lowercase(self):
        user = UserRegister(**self._VALID_KWARGS)
        assert user.email == "test@example.com"

    def test_strips_html_from_full_name(self):
        user = UserRegister(
            **{**self._VALID_KWARGS, "full_name": "<b>John</b> <script>alert(1)</script>Doe"}
        )
        assert "<" not in user.full_name
        assert ">" not in user.full_name
        assert "John" in user.full_name
        assert "Doe" in user.full_name

    def test_full_name_strips_nested_html_tags(self):
        user = UserRegister(
            **{**self._VALID_KWARGS, "full_name": "<div><span>Alice</span></div>"}
        )
        assert user.full_name == "Alice"

    def test_full_name_none_is_allowed(self):
        kwargs = {**self._VALID_KWARGS}
        kwargs.pop("full_name")
        user = UserRegister(**kwargs)
        assert user.full_name is None


class TestUserLoginSchema:
    """Tests for the UserLogin Pydantic schema."""

    def test_normalizes_email_to_lowercase(self):
        login = UserLogin(email="Admin@Example.COM", password="anything")
        assert login.email == "admin@example.com"

    def test_strips_whitespace_from_email(self):
        login = UserLogin(email="  user@example.com  ", password="p")
        assert login.email == "user@example.com"
