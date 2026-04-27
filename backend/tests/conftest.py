"""Shared test fixtures for backend tests."""

import json
import os
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


@pytest.fixture()
def mock_settings(tmp_path):
    """Provide a Settings-like object with MODEL_DIR pointing to tmp_path."""
    settings_mock = MagicMock()
    settings_mock.MODEL_DIR = str(tmp_path / "models")
    settings_mock.SECRET_KEY = "test-secret-key-that-is-long-enough-for-validation-1234567890"
    settings_mock.ALGORITHM = "HS256"
    settings_mock.ACCESS_TOKEN_EXPIRE_MINUTES = 30
    settings_mock.DATABASE_URL = "sqlite:///test.db"
    settings_mock.DEBUG = True
    return settings_mock


@pytest.fixture()
def evaluation_report_data():
    """Sample evaluation report matching the structure produced by train.py."""
    return {
        "data_source": "combined",
        "total_samples": 1210,
        "train_size": 847,
        "val_size": 181,
        "test_size": 182,
        "best_model": "Logistic Regression",
        "test_accuracy": 0.85,
        "cv_mean": 0.84,
        "cv_std": 0.02,
        "vocabulary_size": 4392,
        "classification_report": {
            "bank": {"precision": 0.73, "recall": 0.73, "f1-score": 0.73, "support": 30},
            "bills": {"precision": 0.57, "recall": 0.57, "f1-score": 0.57, "support": 30},
            "invoices": {"precision": 0.67, "recall": 0.67, "f1-score": 0.67, "support": 30},
            "tax": {"precision": 0.95, "recall": 0.95, "f1-score": 0.95, "support": 30},
            "tickets": {"precision": 1.00, "recall": 1.00, "f1-score": 1.00, "support": 30},
            "upi": {"precision": 1.00, "recall": 1.00, "f1-score": 1.00, "support": 32},
        },
        "confusion_matrix": [
            [22, 3, 5, 0, 0, 0],
            [4, 17, 6, 2, 1, 0],
            [3, 5, 20, 2, 0, 0],
            [0, 1, 0, 28, 1, 0],
            [0, 0, 0, 0, 30, 0],
            [0, 0, 0, 0, 0, 32],
        ],
        "categories": ["bank", "bills", "invoices", "tax", "tickets", "upi"],
    }


@pytest.fixture()
def evaluation_report_file(tmp_path, evaluation_report_data):
    """Create a temporary evaluation_report.json and return its parent dir."""
    eval_dir = tmp_path / "models" / "evaluation"
    eval_dir.mkdir(parents=True)
    report_path = eval_dir / "evaluation_report.json"
    report_path.write_text(json.dumps(evaluation_report_data))
    return tmp_path / "models"


@pytest.fixture()
def mock_current_user():
    """Return a mock user object for authenticated requests."""
    user = MagicMock()
    user.id = 1
    user.email = "test@example.com"
    user.username = "testuser"
    user.is_active = True
    return user


# ──────────────────────────────────────────────────────────────────────────
# Phase 9 — Compliance Foundation fixtures
#
# These fixtures support the Wave 0 test infrastructure for Phase 9.
# They reference modules (`app.compliance.*`) that do NOT yet exist —
# Plans 02–05 land them. Tests using these fixtures will pytest.skip()
# until then. This is the intentional Wave 0 RED state.
# ──────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def app_runtime_engine():
    """Engine connected to the local DB with credentials that can SET ROLE.

    Plan 09-03 update: the engine intentionally uses DATABASE_URL (postgres
    superuser) rather than DATABASE_URL_RUNTIME so that test fixtures can
    `RESET ROLE` to bypass RLS while creating fixture data, then
    `SET LOCAL ROLE app_runtime` to subject the test body to RLS.

    DATABASE_URL_RUNTIME (= literal app_runtime user) cannot RESET to a
    higher-privilege role; once subjected to FORCE RLS without a tenant
    context, INSERTs into client-scoped tables fail unconditionally.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    engine = create_engine(url, pool_pre_ping=True)
    yield engine
    engine.dispose()


def _set_tenant_context(session, *, client_id: int = 0, user_id: int = 1):
    """Helper: install the per-request tenant context expected by RLS policies.

    Plan 04 will land an HTTP middleware that calls these set_config()s on
    every request. Until then, fixtures call this helper directly.
    """
    session.execute(
        text("SELECT set_config('app.current_client_id', :cid, true)"),
        {"cid": str(client_id)},
    )
    session.execute(
        text("SELECT set_config('app.user_id', :uid, true)"),
        {"uid": str(user_id)},
    )


@pytest.fixture()
def db_as_app_runtime(app_runtime_engine):
    """Session subjected to RLS as app_runtime.

    Pattern: connect as postgres (RLS-bypassing owner), SET ROLE
    app_runtime so subsequent statements ARE subject to RLS. Fixtures
    that need to bootstrap data temporarily RESET ROLE — see client_a
    / client_b / auditor_membership fixtures below.
    """
    SessionAR = sessionmaker(
        bind=app_runtime_engine, autoflush=False, autocommit=False
    )
    session = SessionAR()
    try:
        session.execute(text("SET LOCAL ROLE app_runtime"))
    except Exception:
        pass
    yield session
    session.rollback()
    session.close()


def _create_client_with_rls_bypass(db, name: str):
    """Insert a Client row bypassing RLS, then re-subject session to RLS
    with the new client's id pinned as the tenant context.

    `db` is the pytest-yielded session; we toggle role within the same
    session so the test body sees the inserted row through normal
    tenant_isolation policy evaluation.

    SEQUENCING NOTE: capture c.id into a local int BEFORE switching roles.
    SQLAlchemy expires all attributes on commit, so accessing `c.id` after
    `SET LOCAL ROLE app_runtime` would trigger an attribute reload SELECT
    while RLS is enabled but `app.current_client_id` is not yet set,
    causing ObjectDeletedError. The local-int avoids that race.
    """
    from app.compliance.models.client import Client

    db.execute(text("RESET ROLE"))
    c = Client(name=name, client_type="pvt_ltd")
    db.add(c)
    db.commit()  # commit so id is materialised
    db.refresh(c)  # eagerly reload attrs while still bypassing RLS
    client_id = c.id
    db.execute(text("SET LOCAL ROLE app_runtime"))
    _set_tenant_context(db, client_id=client_id, user_id=1)
    return c


def _delete_with_rls_bypass(db, *objs):
    """Counterpart cleanup that bypasses RLS to delete fixture rows."""
    db.rollback()  # clear any failed-test state
    db.execute(text("RESET ROLE"))
    for obj in objs:
        try:
            db.delete(obj)
        except Exception:
            pass
    try:
        db.commit()
    except Exception:
        db.rollback()
    db.execute(text("SET LOCAL ROLE app_runtime"))


@pytest.fixture()
def client_a(db_as_app_runtime):
    """First test client.

    Inserts via RESET ROLE to bypass RLS (analogous to admin/onboarding
    flow), then sets tenant context so subsequent app_runtime queries
    can read and write rows for this client.
    """
    try:
        from app.compliance.models.client import Client  # noqa: F401
    except ImportError:
        pytest.skip("Client model not yet created — Plan 03")
    c = _create_client_with_rls_bypass(db_as_app_runtime, "Test Client A")
    yield c
    _delete_with_rls_bypass(db_as_app_runtime, c)


@pytest.fixture()
def client_b(db_as_app_runtime):
    """Second test client for cross-tenant leakage tests."""
    try:
        from app.compliance.models.client import Client  # noqa: F401
    except ImportError:
        pytest.skip("Client model not yet created — Plan 03")
    c = _create_client_with_rls_bypass(db_as_app_runtime, "Test Client B")
    yield c
    _delete_with_rls_bypass(db_as_app_runtime, c)


@pytest.fixture()
def audit_log_row(db_as_app_runtime):
    """Create a single AuditLog row for immutability tests."""
    from app.models.audit_log import AuditLog
    row = AuditLog(
        user_id=None,
        action="test_action",
        resource_type="TestResource",
        resource_id=1,
        details={"test": True},
    )
    db_as_app_runtime.add(row)
    db_as_app_runtime.commit()
    yield row


@pytest.fixture()
def auditor_membership(db_as_app_runtime, client_a):
    """ClientMembership with compliance_role=auditor.

    Caller adjusts access_start / access_end attributes after fixture
    yields. Created with RLS bypass because the membership row references
    a fresh client id; tenant_isolation requires the row's client_id to
    match app.current_client_id which is enforced by the surrounding
    client_a fixture.
    """
    try:
        from app.compliance.models.membership import ClientMembership
    except ImportError:
        pytest.skip("ClientMembership not yet created — Plan 03")
    db_as_app_runtime.execute(text("RESET ROLE"))
    m = ClientMembership(
        user_id=1,
        client_id=client_a.id,
        compliance_role="auditor",
        access_start=None,
        access_end=None,
    )
    db_as_app_runtime.add(m)
    db_as_app_runtime.commit()
    db_as_app_runtime.execute(text("SET LOCAL ROLE app_runtime"))
    _set_tenant_context(db_as_app_runtime, client_id=client_a.id, user_id=1)
    yield m
    _delete_with_rls_bypass(db_as_app_runtime, m)


@pytest.fixture()
def client_with_membership(db_as_app_runtime):
    """Factory: create a user with a given compliance_role on a fresh client."""
    try:
        from app.compliance.models.client import Client
        from app.compliance.models.membership import ClientMembership
        from app.models.user import User
    except ImportError:
        pytest.skip("Phase 9 models not yet created — Plan 03")
    created = []

    def _factory(compliance_role: str):
        db_as_app_runtime.execute(text("RESET ROLE"))
        u = User(
            email=f"test-{compliance_role}@example.com",
            username=f"u_{compliance_role}",
            hashed_password="x",
            role="editor",
        )
        db_as_app_runtime.add(u)
        db_as_app_runtime.flush()
        c = Client(name=f"Client for {compliance_role}", client_type="pvt_ltd")
        db_as_app_runtime.add(c)
        db_as_app_runtime.flush()
        m = ClientMembership(
            user_id=u.id,
            client_id=c.id,
            compliance_role=compliance_role,
        )
        db_as_app_runtime.add(m)
        db_as_app_runtime.commit()
        db_as_app_runtime.execute(text("SET LOCAL ROLE app_runtime"))
        _set_tenant_context(db_as_app_runtime, client_id=c.id, user_id=u.id)
        created.extend([u, c, m])
        return u

    yield _factory
    _delete_with_rls_bypass(db_as_app_runtime, *reversed(created))


@pytest.fixture(autouse=True)
def _ensure_phase9_test_user(app_runtime_engine):
    """Phase 9 FK fixture: guarantee a User row with id=1 exists.

    Many Phase 9 fixtures + tests pass user_id=1 (matching the v1.0
    `mock_current_user` MagicMock id) to FK columns like
    NoticeActivity.user_id, AuditLog.user_id, ClientMembership.user_id.
    Without an actual users.id=1 row those FKs raise IntegrityError on
    insert. This autouse fixture creates the row once and leaves it in
    place across the test session.
    """
    try:
        from app.models.user import User
    except ImportError:
        return  # v1.0-only test run
    SessionFactory = sessionmaker(
        bind=app_runtime_engine, autoflush=False, autocommit=False
    )
    s = SessionFactory()
    try:
        # Bypass RLS — users table may have its own access controls but the
        # postgres role can always insert.
        s.execute(text("RESET ROLE"))
        if s.query(User).filter(User.id == 1).first() is None:
            s.add(
                User(
                    id=1,
                    email="phase9-fixture@example.com",
                    username="phase9_fixture_user",
                    hashed_password="x",
                    role="editor",
                )
            )
            try:
                s.commit()
            except Exception:
                s.rollback()
    finally:
        s.close()
    yield
