"""Audit immutability tests — Phase 9 AUDIT-01 / INFRA-07 merge gate.

The audit_logs table MUST reject UPDATE/DELETE at two layers:
  1. PostgreSQL trigger raises EXCEPTION ON BEFORE UPDATE OR DELETE.
  2. REVOKE UPDATE, DELETE on app_runtime — privilege-level block.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import InternalError, ProgrammingError


pytestmark = pytest.mark.integration


def test_update_raises(db_as_app_runtime, audit_log_row):
    """UPDATE on audit_logs raises 'append-only' exception (trigger fires)."""
    with pytest.raises((InternalError, ProgrammingError)) as exc_info:
        db_as_app_runtime.execute(
            text("UPDATE audit_logs SET action = 'tampered' WHERE id = :id"),
            {"id": audit_log_row.id},
        )
        db_as_app_runtime.commit()
    msg = str(exc_info.value).lower()
    assert "append-only" in msg or "permission denied" in msg, (
        f"Expected append-only/permission denied error, got: {exc_info.value}"
    )


def test_delete_raises(db_as_app_runtime, audit_log_row):
    """DELETE on audit_logs raises 'append-only' exception."""
    with pytest.raises((InternalError, ProgrammingError)) as exc_info:
        db_as_app_runtime.execute(
            text("DELETE FROM audit_logs WHERE id = :id"),
            {"id": audit_log_row.id},
        )
        db_as_app_runtime.commit()
    msg = str(exc_info.value).lower()
    assert "append-only" in msg or "permission denied" in msg


def test_app_role_lacks_privilege(db_as_app_runtime):
    """REVOKE check — app_runtime grants do not include UPDATE/DELETE on audit_logs.

    Defense in depth: even if a future migration accidentally restored
    the trigger-protected behaviour, REVOKE blocks at the privilege layer.
    """
    rows = db_as_app_runtime.execute(
        text(
            """
            SELECT privilege_type FROM information_schema.role_table_grants
            WHERE table_name = 'audit_logs' AND grantee = 'app_runtime'
            """
        )
    ).all()
    privs = {r[0] for r in rows}
    assert 'UPDATE' not in privs, "app_runtime has UPDATE on audit_logs (must be REVOKEd)"
    assert 'DELETE' not in privs, "app_runtime has DELETE on audit_logs (must be REVOKEd)"
    # INSERT must remain — application logs new audit entries
    assert 'INSERT' in privs, "app_runtime missing INSERT — cannot log audit events"


def test_trigger_present(db_as_app_runtime):
    """The audit_logs_immutability trigger exists on the audit_logs table.

    Pitfall 2: routine migrations can drop triggers as side-effect. This is
    the smoke test that fires on every test run.
    """
    rows = db_as_app_runtime.execute(
        text(
            """
            SELECT tgname FROM pg_trigger
            WHERE tgrelid = 'audit_logs'::regclass
              AND tgname = 'audit_logs_immutability'
            """
        )
    ).all()
    assert len(rows) == 1, (
        "audit_logs_immutability trigger missing — was it dropped by a migration?"
    )


def test_clock_timestamp_default(db_as_app_runtime):
    """audit_logs.created_at default is clock_timestamp() (wall clock), not now().

    Plan 02 migration switches the default. Two audit rows in the same
    transaction must have different timestamps.
    """
    from app.models.audit_log import AuditLog
    a = AuditLog(action="t1", resource_type="X", details={})
    b = AuditLog(action="t2", resource_type="X", details={})
    db_as_app_runtime.add_all([a, b])
    db_as_app_runtime.flush()
    # If created_at default is now() (transaction start), a.created_at == b.created_at
    # If clock_timestamp(), they differ by microseconds.
    assert a.created_at < b.created_at, (
        "audit_logs.created_at appears to use now() — expected clock_timestamp()"
    )
    db_as_app_runtime.rollback()
