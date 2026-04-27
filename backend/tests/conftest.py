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
    """Engine connected as app_runtime (non-owner, non-BYPASSRLS) DB role.

    Wave 0: this fixture references env var DATABASE_URL_RUNTIME which Plan 02
    will populate. For Wave 0, if the env var is unset, fall back to
    DATABASE_URL with a SET ROLE app_runtime preamble. The role itself does
    not exist until Plan 02 migration runs.
    """
    url = os.environ.get("DATABASE_URL_RUNTIME") or os.environ.get("DATABASE_URL")
    if not url:
        pytest.skip("DATABASE_URL or DATABASE_URL_RUNTIME not set")
    engine = create_engine(url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_as_app_runtime(app_runtime_engine):
    """Session that runs as app_runtime role (subject to RLS, no BYPASSRLS)."""
    SessionAR = sessionmaker(bind=app_runtime_engine, autoflush=False, autocommit=False)
    session = SessionAR()
    # Switch to app_runtime if connected as owner/migrator
    try:
        session.execute(text("SET LOCAL ROLE app_runtime"))
    except Exception:
        # Plan 02 migration has not run yet — test will fail with clear message
        pass
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def client_a(db_as_app_runtime):
    """First test client. Skipped until Plan 03 creates Client model."""
    try:
        from app.compliance.models.client import Client
    except ImportError:
        pytest.skip("Client model not yet created — Plan 03")
    c = Client(name="Test Client A", client_type="pvt_ltd")
    db_as_app_runtime.add(c)
    db_as_app_runtime.commit()
    yield c
    db_as_app_runtime.delete(c)
    db_as_app_runtime.commit()


@pytest.fixture()
def client_b(db_as_app_runtime):
    """Second test client for cross-tenant leakage tests. Skipped until Plan 03."""
    try:
        from app.compliance.models.client import Client
    except ImportError:
        pytest.skip("Client model not yet created — Plan 03")
    c = Client(name="Test Client B", client_type="pvt_ltd")
    db_as_app_runtime.add(c)
    db_as_app_runtime.commit()
    yield c
    db_as_app_runtime.delete(c)
    db_as_app_runtime.commit()


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
    """ClientMembership with compliance_role=auditor. Skipped until Plan 03.

    Caller adjusts access_start / access_end attributes after fixture yields.
    """
    try:
        from app.compliance.models.membership import ClientMembership
    except ImportError:
        pytest.skip("ClientMembership not yet created — Plan 03")
    m = ClientMembership(
        user_id=1,
        client_id=client_a.id,
        compliance_role="auditor",
        access_start=None,
        access_end=None,
    )
    db_as_app_runtime.add(m)
    db_as_app_runtime.commit()
    yield m
    db_as_app_runtime.delete(m)
    db_as_app_runtime.commit()


@pytest.fixture()
def client_with_membership(db_as_app_runtime):
    """Factory: create a user with a given compliance_role on a fresh client.

    Skipped until Plan 03 creates membership model.
    """
    try:
        from app.compliance.models.client import Client
        from app.compliance.models.membership import ClientMembership
        from app.models.user import User
    except ImportError:
        pytest.skip("Phase 9 models not yet created — Plan 03")
    created = []

    def _factory(compliance_role: str):
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
        created.extend([u, c, m])
        return u

    yield _factory
    for obj in reversed(created):
        db_as_app_runtime.delete(obj)
    db_as_app_runtime.commit()
