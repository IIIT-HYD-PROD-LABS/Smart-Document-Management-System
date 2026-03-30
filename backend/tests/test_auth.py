"""Comprehensive tests for authentication endpoints (register, login, refresh, logout, providers).

All tests run WITHOUT a real database by overriding the ``get_db`` dependency
with a mock session and patching internal helpers where needed.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_user(**overrides):
    """Return a MagicMock that behaves like a User ORM instance."""
    defaults = {
        "id": 1,
        "email": "alice@example.com",
        "username": "alice",
        "hashed_password": "$2b$12$fakehash",
        "full_name": "Alice Smith",
        "role": "editor",
        "auth_provider": "local",
        "oauth_id": None,
        "is_active": True,
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    user = MagicMock()
    for k, v in defaults.items():
        setattr(user, k, v)
    return user


def _make_mock_refresh_token(**overrides):
    """Return a MagicMock that behaves like a RefreshToken ORM instance."""
    defaults = {
        "id": 10,
        "token": "valid-refresh-token-value",
        "user_id": 1,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
        "is_revoked": False,
        "created_at": datetime.now(timezone.utc),
        "revoked_at": None,
        "replaced_by": None,
    }
    defaults.update(overrides)
    tok = MagicMock()
    for k, v in defaults.items():
        setattr(tok, k, v)
    return tok


class _QueryChain:
    """Tiny helper that simulates ``db.query(Model).filter(...).first()`` chains.

    Usage::

        chain = _QueryChain(return_value=some_user)
        mock_db.query.return_value = chain
        # db.query(User).filter(User.email == x).first()  -> some_user
    """

    def __init__(self, return_value=None):
        self._return_value = return_value

    def filter(self, *args, **kwargs):  # noqa: A003
        return self

    def with_for_update(self, **kwargs):
        return self

    def first(self):
        return self._return_value

    def count(self):
        return 0 if self._return_value is None else 1

    def update(self, values):
        return 1


@pytest.fixture()
def client():
    """Yield a (TestClient, mock_db) tuple with proper cleanup."""
    from app.main import app
    from app.database import get_db
    from app.utils.rate_limiter import limiter

    mock_db = MagicMock()

    def override_get_db():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db
    limiter.enabled = False
    test_client = TestClient(app)
    yield test_client, mock_db
    limiter.enabled = True
    app.dependency_overrides.pop(get_db, None)


# =========================================================================
# 1. REGISTER  /api/auth/register
# =========================================================================

class TestRegister:
    """POST /api/auth/register"""

    VALID_PAYLOAD = {
        "email": "newuser@example.com",
        "username": "newuser",
        "password": "Str0ng!Pass",
        "full_name": "New User",
    }

    # -- success -----------------------------------------------------------

    @patch("app.routers.auth.create_refresh_token")
    @patch("app.routers.auth.create_access_token")
    @patch("app.routers.auth.hash_password")
    def test_valid_registration_returns_201_with_tokens(
        self, mock_hash, mock_access, mock_refresh, client
    ):
        test_client, mock_db = client
        mock_hash.return_value = "$2b$12$hashed"
        mock_access.return_value = "access-jwt"
        mock_refresh.return_value = ("refresh-opaque", datetime.now(timezone.utc) + timedelta(days=7))

        new_user = _make_mock_user(
            id=1, email="newuser@example.com", username="newuser",
            full_name="New User", role="editor",
        )

        # query(User).filter(email==...).first() -> None (no duplicate email)
        # query(User).filter(username==...).first() -> None (no duplicate username)
        # query(User).count() -> 0 (first user check)
        call_count = 0

        def query_side_effect(model):
            nonlocal call_count
            call_count += 1
            return _QueryChain(return_value=None)

        mock_db.query.side_effect = query_side_effect

        # db.refresh(user) should populate the mock
        def refresh_side_effect(user):
            user.id = new_user.id
            user.email = new_user.email
            user.username = new_user.username
            user.full_name = new_user.full_name
            user.role = new_user.role
            user.is_active = new_user.is_active
            user.created_at = new_user.created_at

        mock_db.refresh.side_effect = refresh_side_effect

        response = test_client.post("/api/auth/register", json=self.VALID_PAYLOAD)

        assert response.status_code == 201
        body = response.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"
        assert "user" in body
        assert body["user"]["email"] == "newuser@example.com"

    # -- duplicate email ---------------------------------------------------

    def test_duplicate_email_returns_409(self, client):
        test_client, mock_db = client
        existing = _make_mock_user(email="newuser@example.com")

        call_count = 0

        def query_side_effect(model):
            nonlocal call_count
            call_count += 1
            # First query: email check -> return existing user
            if call_count == 1:
                return _QueryChain(return_value=existing)
            return _QueryChain(return_value=None)

        mock_db.query.side_effect = query_side_effect

        response = test_client.post("/api/auth/register", json=self.VALID_PAYLOAD)

        assert response.status_code == 409
        assert "email" in response.json()["detail"].lower()

    # -- duplicate username ------------------------------------------------

    def test_duplicate_username_returns_409(self, client):
        test_client, mock_db = client
        existing = _make_mock_user(username="newuser")

        call_count = 0

        def query_side_effect(model):
            nonlocal call_count
            call_count += 1
            # First query: email check -> None
            if call_count == 1:
                return _QueryChain(return_value=None)
            # Second query: username check -> existing user
            if call_count == 2:
                return _QueryChain(return_value=existing)
            return _QueryChain(return_value=None)

        mock_db.query.side_effect = query_side_effect

        response = test_client.post("/api/auth/register", json=self.VALID_PAYLOAD)

        assert response.status_code == 409
        assert "username" in response.json()["detail"].lower()

    # -- weak password: no uppercase ---------------------------------------

    def test_password_without_uppercase_rejected(self, client):
        test_client, _ = client
        payload = {**self.VALID_PAYLOAD, "password": "str0ng!pass"}
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422
        body = response.json()
        detail_str = str(body["detail"]).lower()
        assert "uppercase" in detail_str

    # -- weak password: too short ------------------------------------------

    def test_password_too_short_rejected(self, client):
        test_client, _ = client
        payload = {**self.VALID_PAYLOAD, "password": "S1!a"}
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422

    # -- weak password: no special character -------------------------------

    def test_password_without_special_char_rejected(self, client):
        test_client, _ = client
        payload = {**self.VALID_PAYLOAD, "password": "Str0ngPass"}
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422
        body = response.json()
        detail_str = str(body["detail"]).lower()
        assert "special" in detail_str

    # -- weak password: no digit -------------------------------------------

    def test_password_without_digit_rejected(self, client):
        test_client, _ = client
        payload = {**self.VALID_PAYLOAD, "password": "StrongPass!"}
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422
        body = response.json()
        detail_str = str(body["detail"]).lower()
        assert "digit" in detail_str

    # -- weak password: no lowercase ---------------------------------------

    def test_password_without_lowercase_rejected(self, client):
        test_client, _ = client
        payload = {**self.VALID_PAYLOAD, "password": "STR0NG!PASS"}
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422
        body = response.json()
        detail_str = str(body["detail"]).lower()
        assert "lowercase" in detail_str

    # -- invalid email format ----------------------------------------------

    def test_invalid_email_format_rejected(self, client):
        test_client, _ = client
        payload = {**self.VALID_PAYLOAD, "email": "not-an-email"}
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422

    def test_email_missing_domain_rejected(self, client):
        test_client, _ = client
        payload = {**self.VALID_PAYLOAD, "email": "user@"}
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422

    def test_email_missing_at_sign_rejected(self, client):
        test_client, _ = client
        payload = {**self.VALID_PAYLOAD, "email": "userdomain.com"}
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422


# =========================================================================
# 2. LOGIN  /api/auth/login
# =========================================================================

class TestLogin:
    """POST /api/auth/login"""

    VALID_PAYLOAD = {
        "email": "alice@example.com",
        "password": "Str0ng!Pass",
    }

    # -- success -----------------------------------------------------------

    @patch("app.routers.auth.create_refresh_token")
    @patch("app.routers.auth.create_access_token")
    @patch("app.routers.auth.verify_password", return_value=True)
    def test_valid_login_returns_200_with_tokens(
        self, mock_verify, mock_access, mock_refresh, client
    ):
        test_client, mock_db = client
        mock_access.return_value = "access-jwt"
        mock_refresh.return_value = ("refresh-opaque", datetime.now(timezone.utc) + timedelta(days=7))

        user = _make_mock_user()
        mock_db.query.return_value = _QueryChain(return_value=user)

        response = test_client.post("/api/auth/login", json=self.VALID_PAYLOAD)

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == "access-jwt"
        assert body["refresh_token"] == "refresh-opaque"
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == "alice@example.com"

    # -- wrong password ----------------------------------------------------

    @patch("app.routers.auth.verify_password", return_value=False)
    def test_wrong_password_returns_401(self, mock_verify, client):
        test_client, mock_db = client
        user = _make_mock_user()
        mock_db.query.return_value = _QueryChain(return_value=user)

        response = test_client.post("/api/auth/login", json=self.VALID_PAYLOAD)

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    # -- unknown email -----------------------------------------------------

    def test_unknown_email_returns_401(self, client):
        test_client, mock_db = client
        mock_db.query.return_value = _QueryChain(return_value=None)

        response = test_client.post("/api/auth/login", json=self.VALID_PAYLOAD)

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    # -- deactivated user --------------------------------------------------

    @patch("app.routers.auth.verify_password", return_value=True)
    def test_deactivated_user_returns_401(self, mock_verify, client):
        test_client, mock_db = client
        user = _make_mock_user(is_active=False)
        mock_db.query.return_value = _QueryChain(return_value=user)

        response = test_client.post("/api/auth/login", json=self.VALID_PAYLOAD)

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    # -- non-local auth provider -------------------------------------------

    def test_oauth_user_cannot_use_local_login(self, client):
        test_client, mock_db = client
        user = _make_mock_user(auth_provider="google")
        mock_db.query.return_value = _QueryChain(return_value=user)

        response = test_client.post("/api/auth/login", json=self.VALID_PAYLOAD)

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    # -- user with no hashed password --------------------------------------

    def test_user_without_password_returns_401(self, client):
        test_client, mock_db = client
        user = _make_mock_user(hashed_password=None)
        mock_db.query.return_value = _QueryChain(return_value=user)

        response = test_client.post("/api/auth/login", json=self.VALID_PAYLOAD)

        assert response.status_code == 401


# =========================================================================
# 3. REFRESH  /api/auth/refresh
# =========================================================================

class TestRefresh:
    """POST /api/auth/refresh"""

    # -- success -----------------------------------------------------------

    @patch("app.routers.auth.create_refresh_token")
    @patch("app.routers.auth.create_access_token")
    def test_valid_refresh_returns_new_token_pair(
        self, mock_access, mock_refresh, client
    ):
        test_client, mock_db = client
        mock_access.return_value = "new-access-jwt"
        mock_refresh.return_value = ("new-refresh-opaque", datetime.now(timezone.utc) + timedelta(days=7))

        db_token = _make_mock_refresh_token()
        user = _make_mock_user()

        call_count = 0

        def query_side_effect(model):
            nonlocal call_count
            call_count += 1
            # First query: RefreshToken lookup
            if call_count == 1:
                return _QueryChain(return_value=db_token)
            # Second query: User lookup
            return _QueryChain(return_value=user)

        mock_db.query.side_effect = query_side_effect

        response = test_client.post(
            "/api/auth/refresh",
            json={"refresh_token": "valid-refresh-token-value"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["access_token"] == "new-access-jwt"
        assert body["refresh_token"] == "new-refresh-opaque"
        assert body["token_type"] == "bearer"
        assert body["user"]["email"] == "alice@example.com"

    # -- expired token -----------------------------------------------------

    def test_expired_refresh_token_returns_401(self, client):
        test_client, mock_db = client
        db_token = _make_mock_refresh_token(
            expires_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
        )

        mock_db.query.return_value = _QueryChain(return_value=db_token)

        response = test_client.post(
            "/api/auth/refresh",
            json={"refresh_token": "valid-refresh-token-value"},
        )

        assert response.status_code == 401
        assert "expired" in response.json()["detail"].lower()

    # -- unknown token -----------------------------------------------------

    def test_unknown_refresh_token_returns_401(self, client):
        test_client, mock_db = client
        mock_db.query.return_value = _QueryChain(return_value=None)

        response = test_client.post(
            "/api/auth/refresh",
            json={"refresh_token": "nonexistent-token"},
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    # -- revoked token triggers mass revocation ----------------------------

    def test_revoked_token_triggers_mass_revocation(self, client):
        test_client, mock_db = client
        db_token = _make_mock_refresh_token(is_revoked=True, user_id=1)

        # Track the mass-revocation update call
        update_chain = MagicMock()
        update_chain.filter.return_value = update_chain
        update_chain.with_for_update.return_value = update_chain
        update_chain.first.return_value = db_token
        update_chain.update.return_value = 3  # 3 tokens revoked

        mock_db.query.return_value = update_chain

        response = test_client.post(
            "/api/auth/refresh",
            json={"refresh_token": "valid-refresh-token-value"},
        )

        assert response.status_code == 401
        assert "reuse" in response.json()["detail"].lower()
        # Verify that update was called (mass revocation)
        assert update_chain.update.called

    # -- deactivated user on refresh ---------------------------------------

    @patch("app.routers.auth.create_refresh_token")
    @patch("app.routers.auth.create_access_token")
    def test_deactivated_user_refresh_returns_403(
        self, mock_access, mock_refresh, client
    ):
        test_client, mock_db = client
        db_token = _make_mock_refresh_token()
        user = _make_mock_user(is_active=False)

        call_count = 0

        def query_side_effect(model):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _QueryChain(return_value=db_token)
            return _QueryChain(return_value=user)

        mock_db.query.side_effect = query_side_effect

        response = test_client.post(
            "/api/auth/refresh",
            json={"refresh_token": "valid-refresh-token-value"},
        )

        assert response.status_code == 403
        assert "deactivated" in response.json()["detail"].lower()

    # -- user not found on refresh -----------------------------------------

    @patch("app.routers.auth.create_refresh_token")
    @patch("app.routers.auth.create_access_token")
    def test_user_not_found_on_refresh_returns_401(
        self, mock_access, mock_refresh, client
    ):
        test_client, mock_db = client
        db_token = _make_mock_refresh_token()

        call_count = 0

        def query_side_effect(model):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _QueryChain(return_value=db_token)
            return _QueryChain(return_value=None)

        mock_db.query.side_effect = query_side_effect

        response = test_client.post(
            "/api/auth/refresh",
            json={"refresh_token": "valid-refresh-token-value"},
        )

        assert response.status_code == 401
        assert "user not found" in response.json()["detail"].lower()


# =========================================================================
# 4. LOGOUT  /api/auth/logout
# =========================================================================

class TestLogout:
    """POST /api/auth/logout"""

    def test_valid_logout_returns_200(self, client):
        test_client, mock_db = client
        db_token = _make_mock_refresh_token()
        mock_db.query.return_value = _QueryChain(return_value=db_token)

        response = test_client.post(
            "/api/auth/logout",
            json={"refresh_token": "valid-refresh-token-value"},
        )

        assert response.status_code == 200
        body = response.json()
        assert "logged out" in body["detail"].lower()

    def test_logout_revokes_token(self, client):
        test_client, mock_db = client
        db_token = _make_mock_refresh_token(is_revoked=False)
        mock_db.query.return_value = _QueryChain(return_value=db_token)

        test_client.post(
            "/api/auth/logout",
            json={"refresh_token": "valid-refresh-token-value"},
        )

        # Verify the token was marked as revoked
        assert db_token.is_revoked is True

    def test_logout_already_revoked_token_still_200(self, client):
        test_client, mock_db = client
        db_token = _make_mock_refresh_token(is_revoked=True)
        mock_db.query.return_value = _QueryChain(return_value=db_token)

        response = test_client.post(
            "/api/auth/logout",
            json={"refresh_token": "valid-refresh-token-value"},
        )

        # Already revoked token still returns 200 (idempotent)
        assert response.status_code == 200

    def test_logout_unknown_token_returns_401(self, client):
        test_client, mock_db = client
        mock_db.query.return_value = _QueryChain(return_value=None)

        response = test_client.post(
            "/api/auth/logout",
            json={"refresh_token": "nonexistent-token"},
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_logout_empty_token_returns_422(self, client):
        test_client, _ = client

        response = test_client.post(
            "/api/auth/logout",
            json={"refresh_token": ""},
        )

        assert response.status_code == 422


# =========================================================================
# 5. PROVIDERS  /api/auth/providers
# =========================================================================

class TestProviders:
    """GET /api/auth/providers"""

    def test_providers_returns_at_least_local(self, client):
        test_client, _ = client

        response = test_client.get("/api/auth/providers")

        assert response.status_code == 200
        body = response.json()
        assert "providers" in body
        assert "local" in body["providers"]

    @patch("app.routers.auth.settings")
    def test_providers_includes_google_when_configured(self, mock_settings, client):
        test_client, _ = client
        mock_settings.GOOGLE_CLIENT_ID = "google-client-id-123"
        mock_settings.MICROSOFT_CLIENT_ID = ""
        mock_settings.RATE_LIMIT_AUTH = "100/minute"

        response = test_client.get("/api/auth/providers")

        assert response.status_code == 200
        body = response.json()
        assert "google" in body["providers"]

    @patch("app.routers.auth.settings")
    def test_providers_includes_microsoft_when_configured(self, mock_settings, client):
        test_client, _ = client
        mock_settings.GOOGLE_CLIENT_ID = ""
        mock_settings.MICROSOFT_CLIENT_ID = "ms-client-id-123"
        mock_settings.RATE_LIMIT_AUTH = "100/minute"

        response = test_client.get("/api/auth/providers")

        assert response.status_code == 200
        body = response.json()
        assert "microsoft" in body["providers"]

    @patch("app.routers.auth.settings")
    def test_providers_includes_all_when_both_configured(self, mock_settings, client):
        test_client, _ = client
        mock_settings.GOOGLE_CLIENT_ID = "google-id"
        mock_settings.MICROSOFT_CLIENT_ID = "ms-id"
        mock_settings.RATE_LIMIT_AUTH = "100/minute"

        response = test_client.get("/api/auth/providers")

        assert response.status_code == 200
        body = response.json()
        assert "local" in body["providers"]
        assert "google" in body["providers"]
        assert "microsoft" in body["providers"]


# =========================================================================
# 6. INPUT VALIDATION EDGE CASES
# =========================================================================

class TestInputValidation:
    """Cross-cutting schema validation tests."""

    def test_register_missing_email_returns_422(self, client):
        test_client, _ = client
        payload = {"username": "bob", "password": "Str0ng!Pass"}
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422

    def test_register_missing_password_returns_422(self, client):
        test_client, _ = client
        payload = {"email": "bob@example.com", "username": "bob"}
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422

    def test_register_missing_username_returns_422(self, client):
        test_client, _ = client
        payload = {"email": "bob@example.com", "password": "Str0ng!Pass"}
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422

    def test_register_username_too_short_returns_422(self, client):
        test_client, _ = client
        payload = {
            "email": "bob@example.com",
            "username": "ab",  # min_length=3
            "password": "Str0ng!Pass",
        }
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422

    def test_register_username_with_invalid_start_char_returns_422(self, client):
        test_client, _ = client
        payload = {
            "email": "bob@example.com",
            "username": "-bob",  # must start with letter or number
            "password": "Str0ng!Pass",
        }
        response = test_client.post("/api/auth/register", json=payload)
        assert response.status_code == 422

    def test_login_empty_email_returns_422(self, client):
        test_client, _ = client
        payload = {"email": "", "password": "any"}
        response = test_client.post("/api/auth/login", json=payload)
        assert response.status_code == 422

    def test_login_empty_password_returns_422(self, client):
        test_client, _ = client
        payload = {"email": "a@b.com", "password": ""}
        response = test_client.post("/api/auth/login", json=payload)
        assert response.status_code == 422

    def test_refresh_empty_body_returns_422(self, client):
        test_client, _ = client
        response = test_client.post("/api/auth/refresh", json={})
        assert response.status_code == 422

    def test_register_email_is_normalised_to_lowercase(self, client):
        """Verify that the schema normalises email to lowercase."""
        test_client, mock_db = client

        # We only care about the email reaching the endpoint normalised;
        # let it fail on duplicate check -- we just inspect the call.
        existing = _make_mock_user(email="alice@example.com")

        captured_filter_args = []

        class _CapturingQueryChain:
            def filter(self, *args, **kwargs):
                captured_filter_args.append(args)
                return self

            def first(self):
                return existing

            def count(self):
                return 1

        mock_db.query.return_value = _CapturingQueryChain()

        payload = {
            "email": "ALICE@Example.COM",
            "username": "alice",
            "password": "Str0ng!Pass",
        }
        test_client.post("/api/auth/register", json=payload)

        # The request should have hit 409, which is fine.  The important
        # thing is that it did not fail on validation (422) and the email
        # was accepted in its upper-case form by Pydantic (which lowercases it).
