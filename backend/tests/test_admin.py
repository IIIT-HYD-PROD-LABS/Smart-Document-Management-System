"""Tests for Admin API endpoints.

All tests run without a real database. Dependencies (require_admin, get_async_db)
are overridden via FastAPI dependency_overrides and the rate limiter is
patched out so no Redis connection is needed.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.database import get_async_db
from app.main import app
from app.utils.security import require_admin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_user(
    user_id=1,
    email="admin@example.com",
    username="adminuser",
    full_name="Admin User",
    role="admin",
    is_active=True,
    auth_provider="local",
    created_at=None,
    updated_at=None,
):
    """Build a MagicMock that looks like a User ORM instance."""
    user = MagicMock()
    user.id = user_id
    user.email = email
    user.username = username
    user.full_name = full_name
    user.role = role
    user.is_active = is_active
    user.auth_provider = auth_provider
    user.created_at = created_at or datetime(2025, 1, 1, tzinfo=timezone.utc)
    user.updated_at = updated_at or datetime(2025, 6, 1, tzinfo=timezone.utc)
    return user


def _make_mock_db():
    """Return a MagicMock that stands in for an AsyncSession."""
    db = MagicMock()
    db.execute = AsyncMock()
    db.scalar = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.refresh = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def admin_user():
    return _make_mock_user()


@pytest.fixture()
def mock_db():
    return _make_mock_db()


@pytest.fixture()
def client(admin_user, mock_db):
    """TestClient with require_admin and get_async_db overridden, rate limiter disabled."""
    app.dependency_overrides[require_admin] = lambda: admin_user
    app.dependency_overrides[get_async_db] = lambda: mock_db

    with patch("app.routers.admin.limiter") as mock_limiter:
        # Make the limiter decorator a pass-through
        mock_limiter.limit.return_value = lambda f: f
        yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


@pytest.fixture()
def non_admin_client(mock_db):
    """TestClient where require_admin raises 403 (simulates a non-admin user)."""
    def _deny():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    app.dependency_overrides[require_admin] = _deny
    app.dependency_overrides[get_async_db] = lambda: mock_db

    with patch("app.routers.admin.limiter") as mock_limiter:
        mock_limiter.limit.return_value = lambda f: f
        yield TestClient(app, raise_server_exceptions=False)

    app.dependency_overrides.clear()


# =========================================================================
# 1. Non-admin access -- all endpoints return 403
# =========================================================================

class TestNonAdminAccess:
    """Verify that every admin endpoint rejects non-admin users."""

    def test_list_users_returns_403(self, non_admin_client):
        resp = non_admin_client.get("/api/admin/users")
        assert resp.status_code == 403

    def test_get_user_detail_returns_403(self, non_admin_client):
        resp = non_admin_client.get("/api/admin/users/1")
        assert resp.status_code == 403

    def test_update_role_returns_403(self, non_admin_client):
        resp = non_admin_client.patch(
            "/api/admin/users/2/role", json={"role": "viewer"}
        )
        assert resp.status_code == 403

    def test_update_status_returns_403(self, non_admin_client):
        resp = non_admin_client.patch(
            "/api/admin/users/2/status", json={"is_active": False}
        )
        assert resp.status_code == 403

    def test_admin_stats_returns_403(self, non_admin_client):
        resp = non_admin_client.get("/api/admin/stats")
        assert resp.status_code == 403

    def test_audit_logs_returns_403(self, non_admin_client):
        resp = non_admin_client.get("/api/admin/audit")
        assert resp.status_code == 403

    def test_delete_user_returns_403(self, non_admin_client):
        resp = non_admin_client.delete("/api/admin/users/2")
        assert resp.status_code == 403


# =========================================================================
# 2. List users
# =========================================================================

class TestListUsers:
    """Tests for GET /api/admin/users."""

    def _setup_list_query(self, mock_db, users_with_counts, total=None):
        """Wire up the mock_db for list_users.

        The endpoint does:
          total = await db.scalar(select(func.count())...)
          result = await db.execute(select(User, doc_count)...outerjoin...)
          users_with_counts = result.all()
        """
        if total is None:
            total = len(users_with_counts)

        mock_db.scalar = AsyncMock(return_value=total)

        result = MagicMock()
        result.all.return_value = users_with_counts
        mock_db.execute = AsyncMock(return_value=result)

    def test_returns_paginated_list(self, client, mock_db):
        user1 = _make_mock_user(user_id=1, email="alice@example.com", username="alice")
        user2 = _make_mock_user(user_id=2, email="bob@example.com", username="bob")
        self._setup_list_query(mock_db, [(user1, 5), (user2, 3)], total=2)

        resp = client.get("/api/admin/users?page=1&per_page=20")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        assert body["page"] == 1
        assert body["per_page"] == 20
        assert len(body["users"]) == 2
        assert body["users"][0]["email"] == "alice@example.com"
        assert body["users"][0]["document_count"] == 5
        assert body["users"][1]["email"] == "bob@example.com"
        assert body["users"][1]["document_count"] == 3

    def test_search_filter_is_applied(self, client, mock_db):
        user = _make_mock_user(user_id=3, email="search@example.com", username="found")
        self._setup_list_query(mock_db, [(user, 0)], total=1)

        resp = client.get("/api/admin/users?search=found")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["users"][0]["username"] == "found"

    def test_empty_result(self, client, mock_db):
        self._setup_list_query(mock_db, [], total=0)

        resp = client.get("/api/admin/users")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["users"] == []

    def test_page_must_be_at_least_1(self, client, mock_db):
        resp = client.get("/api/admin/users?page=0")
        assert resp.status_code == 422

    def test_per_page_must_be_at_least_1(self, client, mock_db):
        resp = client.get("/api/admin/users?per_page=0")
        assert resp.status_code == 422

    def test_per_page_cannot_exceed_100(self, client, mock_db):
        resp = client.get("/api/admin/users?per_page=101")
        assert resp.status_code == 422


# =========================================================================
# 3. Get user detail
# =========================================================================

class TestGetUserDetail:
    """Tests for GET /api/admin/users/{user_id}."""

    def _setup_detail_query(self, mock_db, user, doc_count=0):
        """Wire mock_db for the get_user_detail endpoint.

        The endpoint does:
          1. (await db.execute(select(User)...)).scalar_one_or_none() -> user
          2. await db.scalar(select(func.count(Document.id))...)     -> doc_count
        """
        result = MagicMock()
        result.scalar_one_or_none.return_value = user
        mock_db.execute = AsyncMock(return_value=result)
        mock_db.scalar = AsyncMock(return_value=doc_count)

    def test_returns_user_when_found(self, client, mock_db):
        target = _make_mock_user(user_id=42, email="target@example.com", username="target")
        self._setup_detail_query(mock_db, target, doc_count=7)

        resp = client.get("/api/admin/users/42")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == 42
        assert body["email"] == "target@example.com"
        assert body["document_count"] == 7

    def test_returns_404_when_user_not_found(self, client, mock_db):
        self._setup_detail_query(mock_db, user=None)

        resp = client.get("/api/admin/users/999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_rejects_non_positive_user_id(self, client, mock_db):
        resp = client.get("/api/admin/users/0")
        assert resp.status_code == 422


# =========================================================================
# 4. Update role
# =========================================================================

class TestUpdateRole:
    """Tests for PATCH /api/admin/users/{user_id}/role."""

    def _setup_role_query(self, mock_db, target_user, admin_count=2):
        """Wire mock_db for the update_user_role endpoint.

        The endpoint does:
          1. (await db.execute(select(User)...)).scalar_one_or_none() -> target_user
          2. (conditional) await db.scalar(select(func.count(User.id))...) -> admin_count
          3. await db.commit()
        """
        result = MagicMock()
        result.scalar_one_or_none.return_value = target_user
        mock_db.execute = AsyncMock(return_value=result)
        mock_db.scalar = AsyncMock(return_value=admin_count)

    def test_valid_role_change_succeeds(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="editor")
        self._setup_role_query(mock_db, target)

        resp = client.patch("/api/admin/users/2/role", json={"role": "viewer"})
        assert resp.status_code == 200
        body = resp.json()
        assert "updated" in body["detail"].lower()
        assert body["user_id"] == 2
        mock_db.commit.assert_called_once()

    def test_self_role_change_rejected(self, client, admin_user, mock_db):
        # admin_user.id is 1, so trying to change user_id=1 role should fail
        resp = client.patch("/api/admin/users/1/role", json={"role": "viewer"})
        assert resp.status_code == 400
        assert "own role" in resp.json()["detail"].lower()

    def test_invalid_role_rejected(self, client, mock_db):
        resp = client.patch("/api/admin/users/2/role", json={"role": "superuser"})
        assert resp.status_code == 422

    def test_user_not_found_returns_404(self, client, mock_db):
        self._setup_role_query(mock_db, target_user=None)

        resp = client.patch("/api/admin/users/999/role", json={"role": "viewer"})
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_last_admin_cannot_be_demoted(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="admin")
        self._setup_role_query(mock_db, target, admin_count=1)

        resp = client.patch("/api/admin/users/2/role", json={"role": "editor"})
        assert resp.status_code == 400
        assert "last admin" in resp.json()["detail"].lower()

    def test_admin_demotion_allowed_when_multiple_admins(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="admin")
        self._setup_role_query(mock_db, target, admin_count=3)

        resp = client.patch("/api/admin/users/2/role", json={"role": "editor"})
        assert resp.status_code == 200
        mock_db.commit.assert_called_once()

    def test_promote_to_admin_succeeds(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="viewer")
        self._setup_role_query(mock_db, target)

        resp = client.patch("/api/admin/users/2/role", json={"role": "admin"})
        assert resp.status_code == 200
        assert target.role == "admin"


# =========================================================================
# 5. Update status
# =========================================================================

class TestUpdateStatus:
    """Tests for PATCH /api/admin/users/{user_id}/status."""

    def _setup_status_query(self, mock_db, target_user, admin_count=2):
        """Wire mock_db for the update_user_status endpoint.

        The endpoint does:
          1. (await db.execute(select(User)...)).scalar_one_or_none() -> target_user
          2. (conditional) await db.scalar(select(func.count(User.id))...) -> admin_count
          3. (conditional) await db.execute(update(RefreshToken)...)
          4. await db.commit()
        """
        result = MagicMock()
        result.scalar_one_or_none.return_value = target_user
        mock_db.execute = AsyncMock(return_value=result)
        mock_db.scalar = AsyncMock(return_value=admin_count)

    def test_deactivation_succeeds(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="editor", is_active=True)
        self._setup_status_query(mock_db, target)

        resp = client.patch("/api/admin/users/2/status", json={"is_active": False})
        assert resp.status_code == 200
        body = resp.json()
        assert "deactivated" in body["detail"].lower()
        assert body["user_id"] == 2
        assert target.is_active is False
        mock_db.commit.assert_called_once()

    def test_deactivation_revokes_refresh_tokens(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="editor", is_active=True)
        self._setup_status_query(mock_db, target)

        resp = client.patch("/api/admin/users/2/status", json={"is_active": False})
        assert resp.status_code == 200
        # db.execute is called for the user lookup and the RefreshToken bulk update.
        assert mock_db.execute.call_count >= 2

    def test_activation_succeeds(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="editor", is_active=False)
        # For activation, no admin count check or token revocation happens
        result = MagicMock()
        result.scalar_one_or_none.return_value = target
        mock_db.execute = AsyncMock(return_value=result)

        resp = client.patch("/api/admin/users/2/status", json={"is_active": True})
        assert resp.status_code == 200
        body = resp.json()
        assert "activated" in body["detail"].lower()
        assert target.is_active is True

    def test_self_deactivation_rejected(self, client, admin_user, mock_db):
        resp = client.patch("/api/admin/users/1/status", json={"is_active": False})
        assert resp.status_code == 400
        assert "own status" in resp.json()["detail"].lower()

    def test_self_activation_rejected(self, client, admin_user, mock_db):
        resp = client.patch("/api/admin/users/1/status", json={"is_active": True})
        assert resp.status_code == 400
        assert "own status" in resp.json()["detail"].lower()

    def test_last_admin_cannot_be_deactivated(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="admin", is_active=True)
        self._setup_status_query(mock_db, target, admin_count=1)

        resp = client.patch("/api/admin/users/2/status", json={"is_active": False})
        assert resp.status_code == 400
        assert "last admin" in resp.json()["detail"].lower()

    def test_admin_deactivation_allowed_when_multiple_admins(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="admin", is_active=True)
        self._setup_status_query(mock_db, target, admin_count=3)

        resp = client.patch("/api/admin/users/2/status", json={"is_active": False})
        assert resp.status_code == 200
        assert target.is_active is False

    def test_user_not_found_returns_404(self, client, mock_db):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=result)

        resp = client.patch("/api/admin/users/999/status", json={"is_active": False})
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


# =========================================================================
# 6. Admin stats
# =========================================================================

class TestAdminStats:
    """Tests for GET /api/admin/stats."""

    def _setup_stats_query(
        self,
        mock_db,
        total_users=10,
        active_users=8,
        role_rows=None,
        total_documents=50,
        status_rows=None,
    ):
        """Wire mock_db for the get_admin_stats endpoint.

        The endpoint does:
          1. await db.scalar(...) -> total_users
          2. await db.scalar(...) -> active_users
          3. (await db.execute(...)).all() -> role_rows
          4. await db.scalar(...) -> total_documents
          5. (await db.execute(...)).all() -> status_rows
        """
        if role_rows is None:
            role_rows = [("admin", 2), ("editor", 5), ("viewer", 3)]
        if status_rows is None:
            # Document.status is an enum, mock its .value attribute
            status_rows = []
            for s, c in [("uploaded", 20), ("classified", 25), ("processed", 5)]:
                mock_status = MagicMock()
                mock_status.value = s
                status_rows.append((mock_status, c))

        mock_db.scalar = AsyncMock(side_effect=[total_users, active_users, total_documents])

        role_result = MagicMock()
        role_result.all.return_value = role_rows
        status_result = MagicMock()
        status_result.all.return_value = status_rows
        mock_db.execute = AsyncMock(side_effect=[role_result, status_result])

    def test_returns_expected_keys(self, client, mock_db):
        self._setup_stats_query(mock_db)

        resp = client.get("/api/admin/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_users" in body
        assert "active_users" in body
        assert "users_by_role" in body
        assert "total_documents" in body
        assert "documents_by_status" in body

    def test_returns_correct_values(self, client, mock_db):
        self._setup_stats_query(
            mock_db,
            total_users=15,
            active_users=12,
            role_rows=[("admin", 1), ("editor", 10), ("viewer", 4)],
            total_documents=100,
        )

        resp = client.get("/api/admin/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_users"] == 15
        assert body["active_users"] == 12
        assert body["users_by_role"] == {"admin": 1, "editor": 10, "viewer": 4}
        assert body["total_documents"] == 100

    def test_empty_system_returns_zeros(self, client, mock_db):
        self._setup_stats_query(
            mock_db,
            total_users=0,
            active_users=0,
            role_rows=[],
            total_documents=0,
            status_rows=[],
        )

        resp = client.get("/api/admin/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_users"] == 0
        assert body["active_users"] == 0
        assert body["users_by_role"] == {}
        assert body["total_documents"] == 0
        assert body["documents_by_status"] == {}

    def test_documents_by_status_populated(self, client, mock_db):
        uploaded = MagicMock()
        uploaded.value = "uploaded"
        classified = MagicMock()
        classified.value = "classified"

        self._setup_stats_query(
            mock_db,
            status_rows=[(uploaded, 30), (classified, 70)],
        )

        resp = client.get("/api/admin/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert body["documents_by_status"]["uploaded"] == 30
        assert body["documents_by_status"]["classified"] == 70


# =========================================================================
# 7. Delete user (soft-delete + anonymize)
# =========================================================================


class TestDeleteUser:
    """Tests for DELETE /api/admin/users/{user_id}.

    Soft-delete behavior:
      - PII fields (email, username, full_name, oauth_id, hashed_password) are anonymized
      - is_active flips to False, deleted_at gets set
      - Active refresh tokens are revoked
      - audit_logs.user_id is left intact (the row exists, just anonymized)
    """

    def _setup_delete_query(self, mock_db, target_user, admin_count=2):
        """Wire mock_db for the delete_user endpoint.

        The endpoint does:
          1. (await db.execute(select(User)...)).scalar_one_or_none() -> target_user
          2. (only if target is admin) await db.scalar(...) -> admin_count
          3. await db.execute(update(RefreshToken)...)
          4. await db.commit()
        """
        result = MagicMock()
        result.scalar_one_or_none.return_value = target_user
        mock_db.execute = AsyncMock(return_value=result)
        mock_db.scalar = AsyncMock(return_value=admin_count)

    def test_delete_succeeds(self, client, mock_db):
        target = _make_mock_user(
            user_id=2, email="alice@example.com", username="alice", role="editor"
        )
        self._setup_delete_query(mock_db, target)

        resp = client.delete("/api/admin/users/2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == 2
        assert "deleted" in body["detail"].lower()
        mock_db.commit.assert_called_once()

    def test_delete_anonymizes_pii(self, client, mock_db):
        target = _make_mock_user(
            user_id=2,
            email="alice@example.com",
            username="alice",
            full_name="Alice Wonderland",
            role="editor",
        )
        # Give the mock an oauth_id and hashed_password to verify they are nulled
        target.oauth_id = "google-oauth-id-123"
        target.hashed_password = "$2b$12$bcrypt..."
        target.deleted_at = None
        self._setup_delete_query(mock_db, target)

        resp = client.delete("/api/admin/users/2")
        assert resp.status_code == 200

        # PII overwritten
        assert target.email != "alice@example.com"
        assert target.email.startswith("deleted-2-")
        assert target.email.endswith("@deleted.local")
        assert target.username != "alice"
        assert target.username.startswith("deleted_2_")
        assert target.full_name is None
        assert target.oauth_id is None
        assert target.hashed_password is None
        assert target.is_active is False
        assert target.deleted_at is not None

    def test_delete_self_rejected(self, client, admin_user, mock_db):
        # admin_user.id is 1
        resp = client.delete("/api/admin/users/1")
        assert resp.status_code == 400
        assert "own account" in resp.json()["detail"].lower()
        mock_db.commit.assert_not_called()

    def test_delete_user_not_found_returns_404(self, client, mock_db):
        self._setup_delete_query(mock_db, target_user=None)

        resp = client.delete("/api/admin/users/999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
        mock_db.commit.assert_not_called()

    def test_delete_last_admin_rejected(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="admin")
        self._setup_delete_query(mock_db, target, admin_count=1)

        resp = client.delete("/api/admin/users/2")
        assert resp.status_code == 400
        assert "last admin" in resp.json()["detail"].lower()
        mock_db.commit.assert_not_called()

    def test_delete_admin_allowed_when_multiple_admins(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="admin")
        self._setup_delete_query(mock_db, target, admin_count=3)

        resp = client.delete("/api/admin/users/2")
        assert resp.status_code == 200
        assert target.is_active is False

    def test_delete_revokes_refresh_tokens(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="editor")
        self._setup_delete_query(mock_db, target)

        resp = client.delete("/api/admin/users/2")
        assert resp.status_code == 200
        # db.execute is called for the user lookup and the RefreshToken bulk update.
        assert mock_db.execute.call_count >= 2

    def test_delete_rejects_non_positive_user_id(self, client, mock_db):
        resp = client.delete("/api/admin/users/0")
        assert resp.status_code == 422
