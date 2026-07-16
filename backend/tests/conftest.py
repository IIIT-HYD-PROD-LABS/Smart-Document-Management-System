"""Shared test fixtures for backend tests."""

import json
import os
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(autouse=True)
def _reset_tenant_context_vars():
    """Isolate the request-scoped tenant ContextVars across tests.

    get_current_user (security.py) and the tenant middleware call
    current_user_id_var.set(...). A test that mocks SessionLocal sets it to a
    MagicMock user_id; without a reset that value leaks into a LATER test in the
    same process (the whole suite runs in one pytest process in CI), which is
    why test_tenant_middleware_userid passed in isolation but failed in the full
    run. Reset to defaults before every test so each starts from a clean
    context regardless of what ran before.
    """
    from app.compliance.middleware.tenant_context import (
        cross_client_mode_var,
        current_client_id_var,
        current_user_id_var,
    )

    current_user_id_var.set(None)
    current_client_id_var.set(None)
    cross_client_mode_var.set(False)
    yield


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

    DB prerequisite (2026-05-25): the connecting role must be a member of
    `app_runtime` WITH SET TRUE. On Supabase that means running
    `GRANT app_runtime TO postgres` once from the project owner; on PG 16+
    the GRANT also needs `WITH SET TRUE` for SET ROLE to work. Without
    this, every fixture that touches RLS will error with
    `permission denied to set role "app_runtime"`. Auto-skip below
    detects that case and reports cleanly instead of dumping 100
    identical fixture tracebacks.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    engine = create_engine(url, pool_pre_ping=True)
    # Probe SET ROLE eligibility once at session start. Cheaper than
    # discovering it 100 times via fixture failures.
    try:
        with engine.connect() as probe:
            probe.execute(text("SET ROLE app_runtime"))
            probe.execute(text("RESET ROLE"))
    except Exception as exc:  # noqa: BLE001 — any failure means the role can't be assumed
        pytest.skip(
            f"Cannot SET ROLE app_runtime: {exc}. Grant it via "
            f"'GRANT app_runtime TO <conn_user> WITH SET TRUE' on the DB."
        )
    yield engine
    engine.dispose()


def _set_tenant_context(session, *, client_id: int = 0, user_id: int = 1):
    """Helper: install the per-request tenant context expected by RLS policies.

    Plan 04 lands the HTTP middleware that wires these via ContextVars +
    SQLAlchemy before_cursor_execute listener for production. In the test
    environment we set the same PG session vars directly so the test body
    is subjected to the same RLS policies as production.

    Uses is_local=false (session scope) — matches the Plan 04 middleware's
    listener (set_config(..., false) for durability across commits) so that
    test transactions which commit mid-body do not lose the tenant context.
    """
    session.execute(
        text("SELECT set_config('app.current_client_id', :cid, false)"),
        {"cid": str(client_id)},
    )
    session.execute(
        text("SELECT set_config('app.user_id', :uid, false)"),
        {"uid": str(user_id)},
    )


@pytest.fixture()
def db_as_app_runtime(app_runtime_engine):
    """Test session bound to the local DB.

    Default state is the postgres superuser (RLS-bypassed) so simple
    model-layer exercise tests (test_client_management, test_jsonb_query,
    test_regulatory_calendar) can INSERT/SELECT compliance tables without
    needing to wire tenant context first.

    RLS-aware fixtures (`client_a`, `client_b`, `auditor_membership`,
    `client_with_membership`) explicitly RESET ROLE to bypass RLS while
    creating fixture data, then SET LOCAL ROLE app_runtime + set_config
    tenant context so the test body is subjected to RLS.

    test_rls_isolation tests use those fixtures, so the RLS coverage
    contract is preserved. Tests not using those fixtures are exercising
    the ORM/service layer rather than the RLS policy layer.
    """
    SessionAR = sessionmaker(
        bind=app_runtime_engine, autoflush=False, autocommit=False
    )
    session = SessionAR()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="session")
async def app_runtime_async_engine():
    """Async counterpart of app_runtime_engine.

    Same DATABASE_URL (owner role, SET ROLE-eligible) as the sync fixture,
    rewritten to the asyncpg dialect via app.database's own helpers so the
    connect_args match production exactly (timeout vs sslmode naming differs
    between psycopg2 and asyncpg — see app/database.py's
    _async_connect_args_for). Session-scoped to match
    asyncio_default_fixture_loop_scope="session" in pyproject.toml; a
    function-scoped async engine would attempt to bind connections across
    event loops between tests.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL not set")
    from app.database import _async_connect_args_for, _async_url_for

    async_url = _async_url_for(url)
    engine = create_async_engine(
        async_url, pool_pre_ping=True, connect_args=_async_connect_args_for(async_url)
    )
    try:
        async with engine.connect() as probe:
            await probe.execute(text("SET ROLE app_runtime"))
            await probe.execute(text("RESET ROLE"))
    except Exception as exc:  # noqa: BLE001 — any failure means the role can't be assumed
        await engine.dispose()
        pytest.skip(
            f"Cannot SET ROLE app_runtime: {exc}. Grant it via "
            f"'GRANT app_runtime TO <conn_user> WITH SET TRUE' on the DB."
        )
    yield engine
    await engine.dispose()


async def _set_tenant_context_async(session, *, client_id: int = 0, user_id: int = 1):
    """Async counterpart of _set_tenant_context — same is_local=false choreography."""
    await session.execute(
        text("SELECT set_config('app.current_client_id', :cid, false)"),
        {"cid": str(client_id)},
    )
    await session.execute(
        text("SELECT set_config('app.user_id', :uid, false)"),
        {"uid": str(user_id)},
    )


@pytest.fixture()
async def db_as_app_runtime_async(app_runtime_async_engine):
    """Async counterpart of db_as_app_runtime. Same default state (postgres
    superuser, RLS-bypassed) unless a factory fixture below re-subjects it."""
    SessionAR = async_sessionmaker(
        bind=app_runtime_async_engine, autoflush=False, expire_on_commit=False
    )
    session = SessionAR()
    yield session
    await session.rollback()
    await session.close()


async def _create_client_with_rls_bypass_async(db, name: str):
    """Async counterpart of _create_client_with_rls_bypass — identical
    RESET ROLE / SET ROLE choreography and sequencing rationale (capture
    client_id into a local int before switching roles)."""
    from app.compliance.models.client import Client
    from app.compliance.models.membership import ClientMembership

    await db.execute(text("RESET ROLE"))
    c = Client(name=name, client_type="pvt_ltd")
    db.add(c)
    await db.flush()
    m = ClientMembership(user_id=1, client_id=c.id, compliance_role="compliance_head")
    db.add(m)
    await db.commit()
    await db.refresh(c)  # eagerly reload attrs while still bypassing RLS
    client_id = c.id
    await db.execute(text("SET ROLE app_runtime"))
    await _set_tenant_context_async(db, client_id=client_id, user_id=1)
    return c


async def _delete_with_rls_bypass_async(db, *objs):
    """Async counterpart of _delete_with_rls_bypass."""
    await db.rollback()  # clear any failed-test state
    await db.execute(text("RESET ROLE"))
    for obj in objs:
        try:
            await db.delete(obj)
        except Exception:
            pass
    try:
        await db.commit()
    except Exception:
        await db.rollback()
    await db.execute(text("SET ROLE app_runtime"))


@pytest.fixture()
async def client_a_async(db_as_app_runtime_async):
    """Async counterpart of client_a."""
    try:
        from app.compliance.models.client import Client  # noqa: F401
    except ImportError:
        pytest.skip("Client model not yet created — Plan 03")
    c = await _create_client_with_rls_bypass_async(db_as_app_runtime_async, "Test Client A (async)")
    yield c
    await _delete_with_rls_bypass_async(db_as_app_runtime_async, c)


@pytest.fixture()
async def client_b_async(db_as_app_runtime_async):
    """Async counterpart of client_b."""
    try:
        from app.compliance.models.client import Client  # noqa: F401
    except ImportError:
        pytest.skip("Client model not yet created — Plan 03")
    c = await _create_client_with_rls_bypass_async(db_as_app_runtime_async, "Test Client B (async)")
    yield c
    await _delete_with_rls_bypass_async(db_as_app_runtime_async, c)


@pytest.fixture()
async def auditor_membership_async(db_as_app_runtime_async, client_a_async):
    """Async counterpart of auditor_membership."""
    try:
        from app.compliance.models.membership import ClientMembership
        from app.models.user import User
    except ImportError:
        pytest.skip("ClientMembership not yet created — Plan 03")
    # Capture client_a_async.id BEFORE any role/commit cycle expires its attrs.
    client_a_id = client_a_async.id
    await db_as_app_runtime_async.execute(text("RESET ROLE"))
    existing = (
        await db_as_app_runtime_async.execute(select(User).where(User.id == 2))
    ).scalar_one_or_none()
    if existing is None:
        db_as_app_runtime_async.add(
            User(
                id=2,
                email="phase9-auditor-async@example.com",
                username="phase9_auditor_async",
                hashed_password="x",
                role="viewer",
            )
        )
        await db_as_app_runtime_async.commit()
    m = ClientMembership(
        user_id=2,
        client_id=client_a_id,
        compliance_role="auditor",
        access_start=None,
        access_end=None,
    )
    db_as_app_runtime_async.add(m)
    await db_as_app_runtime_async.commit()
    await db_as_app_runtime_async.refresh(m)
    await db_as_app_runtime_async.execute(text("SET ROLE app_runtime"))
    await _set_tenant_context_async(db_as_app_runtime_async, client_id=client_a_id, user_id=2)
    yield m
    await _delete_with_rls_bypass_async(db_as_app_runtime_async, m)


@pytest.fixture()
async def client_with_membership_async(db_as_app_runtime_async):
    """Async counterpart of client_with_membership — factory fixture."""
    try:
        from app.compliance.models.client import Client
        from app.compliance.models.membership import ClientMembership
        from app.models.user import User
    except ImportError:
        pytest.skip("Phase 9 models not yet created — Plan 03")
    created = []

    async def _factory(compliance_role: str):
        await db_as_app_runtime_async.execute(text("RESET ROLE"))
        u = User(
            email=f"test-{compliance_role}-async@example.com",
            username=f"u_{compliance_role}_async",
            hashed_password="x",
            role="editor",
        )
        db_as_app_runtime_async.add(u)
        await db_as_app_runtime_async.flush()
        c = Client(name=f"Client for {compliance_role} (async)", client_type="pvt_ltd")
        db_as_app_runtime_async.add(c)
        await db_as_app_runtime_async.flush()
        m = ClientMembership(
            user_id=u.id,
            client_id=c.id,
            compliance_role=compliance_role,
        )
        db_as_app_runtime_async.add(m)
        await db_as_app_runtime_async.commit()
        await db_as_app_runtime_async.execute(text("SET ROLE app_runtime"))
        await _set_tenant_context_async(db_as_app_runtime_async, client_id=c.id, user_id=u.id)
        created.extend([u, c, m])
        return u

    yield _factory
    await _delete_with_rls_bypass_async(db_as_app_runtime_async, *reversed(created))


def _create_client_with_rls_bypass(db, name: str):
    """Insert a Client row + compliance_head membership for user_id=1
    bypassing RLS, then re-subject session to RLS with the new client's
    id pinned as the tenant context.

    Why a membership: after migration 0018, the tenant_isolation policy
    on compliance_clients requires user_has_client_membership(user_id, id)
    to satisfy SELECT/UPDATE/DELETE. Tests that look up Client rows under
    app_runtime role (e.g. report_service.generate_health_summary)
    need the test user (id=1) to have a membership on the fixture client.

    Why compliance_head: it's listed in is_cross_client_eligible() so
    cross-client mode tests (test_rls_isolation::test_cross_client_mode_*)
    work without an additional fixture.

    SEQUENCING NOTE: capture c.id into a local int BEFORE switching roles.
    SQLAlchemy expires all attributes on commit, so accessing `c.id` after
    `SET LOCAL ROLE app_runtime` would trigger an attribute reload SELECT
    while RLS is enabled but `app.current_client_id` is not yet set,
    causing ObjectDeletedError. The local-int avoids that race.
    """
    from app.compliance.models.client import Client
    from app.compliance.models.membership import ClientMembership

    db.execute(text("RESET ROLE"))
    c = Client(name=name, client_type="pvt_ltd")
    db.add(c)
    db.flush()
    m = ClientMembership(
        user_id=1, client_id=c.id, compliance_role="compliance_head"
    )
    db.add(m)
    db.commit()
    db.refresh(c)  # eagerly reload attrs while still bypassing RLS
    client_id = c.id
    db.execute(text("SET ROLE app_runtime"))
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
    db.execute(text("SET ROLE app_runtime"))


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

    NOTE: client_a's _create_client_with_rls_bypass creates a compliance_head
    membership for user_id=1 (so the test session can satisfy the
    tenant_isolation policy on compliance_clients). To avoid the
    uq_client_membership_user_client unique constraint on (user_id, client_id),
    this fixture uses a DIFFERENT user (id=2) for the auditor membership.
    User 2 is created on demand if missing.
    """
    try:
        from app.compliance.models.membership import ClientMembership
        from app.models.user import User
    except ImportError:
        pytest.skip("ClientMembership not yet created — Plan 03")
    # Capture client_a.id BEFORE any role/commit cycle expires its attrs.
    # Subsequent attribute access under app_runtime would force a refresh
    # SELECT against compliance_clients which RLS may block.
    client_a_id = client_a.id
    db_as_app_runtime.execute(text("RESET ROLE"))
    if db_as_app_runtime.query(User).filter(User.id == 2).first() is None:
        db_as_app_runtime.add(
            User(
                id=2,
                email="phase9-auditor@example.com",
                username="phase9_auditor",
                hashed_password="x",
                role="viewer",
            )
        )
        db_as_app_runtime.commit()
    m = ClientMembership(
        user_id=2,
        client_id=client_a_id,
        compliance_role="auditor",
        access_start=None,
        access_end=None,
    )
    db_as_app_runtime.add(m)
    db_as_app_runtime.commit()
    db_as_app_runtime.refresh(m)
    db_as_app_runtime.execute(text("SET ROLE app_runtime"))
    _set_tenant_context(db_as_app_runtime, client_id=client_a_id, user_id=2)
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
        db_as_app_runtime.execute(text("SET ROLE app_runtime"))
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
        # Explicit id=1 inserts do NOT advance the serial sequence. Without this
        # resync, the next plain User() insert tries id=1 and CI fails with
        # UniqueViolation on users_pkey (seen in test_async_pilot_rls_integration).
        try:
            s.execute(
                text(
                    "SELECT setval("
                    "pg_get_serial_sequence('users', 'id'), "
                    "GREATEST((SELECT COALESCE(MAX(id), 1) FROM users), 1))"
                )
            )
            s.commit()
        except Exception:
            s.rollback()
    finally:
        s.close()
    yield
