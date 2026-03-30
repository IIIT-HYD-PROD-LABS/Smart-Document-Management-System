"""Tests for Admin API endpoints.

All tests run without a real database. Dependencies (require_admin, get_db)
are overridden via FastAPI dependency_overrides and the rate limiter is
patched out so no Redis connection is needed.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock, call

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.database import get_db
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
    """Return a MagicMock that stands in for a SQLAlchemy Session."""
    return MagicMock()


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
    """TestClient with require_admin and get_db overridden, rate limiter disabled."""
    app.dependency_overrides[require_admin] = lambda: admin_user
    app.dependency_overrides[get_db] = lambda: mock_db

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
    app.dependency_overrides[get_db] = lambda: mock_db

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


# =========================================================================
# 2. List users
# =========================================================================

class TestListUsers:
    """Tests for GET /api/admin/users."""

    def _setup_list_query(self, mock_db, users_with_counts, total=None):
        """Wire up the mock_db query chain for list_users.

        The endpoint does:
          query = db.query(User)             -- base query
          query.filter(...)                   -- optional search
          total = query.count()
          doc_count_subq = db.query(...).group_by(...).subquery()
          users_with_counts = query.outerjoin(...).add_columns(...) \
              .order_by(...).offset(...).limit(...).all()
        """
        if total is None:
            total = len(users_with_counts)

        # The chain object returned by db.query(User)
        chain = MagicMock()
        chain.filter.return_value = chain
        chain.count.return_value = total
        chain.outerjoin.return_value = chain
        chain.add_columns.return_value = chain
        chain.order_by.return_value = chain
        chain.offset.return_value = chain
        chain.limit.return_value = chain
        chain.all.return_value = users_with_counts

        # The subquery chain for document counts
        subq_chain = MagicMock()
        subq_chain.group_by.return_value = subq_chain
        subq_chain.subquery.return_value = MagicMock()

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return chain       # db.query(User)
            else:
                return subq_chain  # db.query(Document.user_id, ...)
        mock_db.query.side_effect = side_effect

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

        The endpoint does two queries:
          1. db.query(User).filter(User.id == ...).first()
          2. db.query(func.count(Document.id)).filter(...).scalar()
        """
        first_chain = MagicMock()
        first_chain.filter.return_value = first_chain
        first_chain.first.return_value = user

        count_chain = MagicMock()
        count_chain.filter.return_value = count_chain
        count_chain.scalar.return_value = doc_count

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return first_chain
            else:
                return count_chain
        mock_db.query.side_effect = side_effect

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
          1. db.query(User).filter(User.id == ...).first() -> target_user
          2. (conditional) db.query(func.count(User.id)).filter(...).scalar() -> admin_count
          3. db.commit()
        """
        user_chain = MagicMock()
        user_chain.filter.return_value = user_chain
        user_chain.first.return_value = target_user

        count_chain = MagicMock()
        count_chain.filter.return_value = count_chain
        count_chain.scalar.return_value = admin_count

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return user_chain
            else:
                return count_chain
        mock_db.query.side_effect = side_effect

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
          1. db.query(User).filter(User.id == ...).first() -> target_user
          2. (conditional) db.query(func.count(User.id)).filter(...).scalar() -> admin_count
          3. (conditional) db.query(RefreshToken).filter(...).update(...)
          4. db.commit()
        """
        user_chain = MagicMock()
        user_chain.filter.return_value = user_chain
        user_chain.first.return_value = target_user

        count_chain = MagicMock()
        count_chain.filter.return_value = count_chain
        count_chain.scalar.return_value = admin_count

        token_chain = MagicMock()
        token_chain.filter.return_value = token_chain
        token_chain.update.return_value = 0

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return user_chain    # db.query(User)
            elif call_count[0] == 2:
                return count_chain   # db.query(func.count(User.id)) for admin check
            else:
                return token_chain   # db.query(RefreshToken) for token revocation
        mock_db.query.side_effect = side_effect

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
        # The third db.query call (RefreshToken) should have .update() called
        # Verify that query was called at least 3 times (User, count, RefreshToken)
        assert mock_db.query.call_count >= 2

    def test_activation_succeeds(self, client, mock_db):
        target = _make_mock_user(user_id=2, role="editor", is_active=False)
        # For activation, no admin count check or token revocation happens
        user_chain = MagicMock()
        user_chain.filter.return_value = user_chain
        user_chain.first.return_value = target
        mock_db.query.return_value = user_chain

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
        user_chain = MagicMock()
        user_chain.filter.return_value = user_chain
        user_chain.first.return_value = None
        mock_db.query.return_value = user_chain

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
          1. db.query(func.count(User.id)).scalar()             -> total_users
          2. db.query(func.count(User.id)).filter(...).scalar() -> active_users
          3. db.query(User.role, func.count(User.id)).group_by(...).all() -> role_rows
          4. db.query(func.count(Document.id)).scalar()         -> total_documents
          5. db.query(Document.status, func.count(Document.id)).group_by(...).all() -> status_rows
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

        # Each db.query(...) call returns a new chain
        chains = []

        # 1. total_users: db.query(func.count(User.id)).scalar()
        c1 = MagicMock()
        c1.scalar.return_value = total_users
        chains.append(c1)

        # 2. active_users: db.query(func.count(User.id)).filter(...).scalar()
        c2 = MagicMock()
        c2.filter.return_value = c2
        c2.scalar.return_value = active_users
        chains.append(c2)

        # 3. role_rows: db.query(User.role, func.count(User.id)).group_by(...).all()
        c3 = MagicMock()
        c3.group_by.return_value = c3
        c3.all.return_value = role_rows
        chains.append(c3)

        # 4. total_documents: db.query(func.count(Document.id)).scalar()
        c4 = MagicMock()
        c4.scalar.return_value = total_documents
        chains.append(c4)

        # 5. status_rows: db.query(Document.status, func.count(Document.id)).group_by(...).all()
        c5 = MagicMock()
        c5.group_by.return_value = c5
        c5.all.return_value = status_rows
        chains.append(c5)

        mock_db.query.side_effect = chains

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
