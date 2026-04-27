"""RLS isolation tests — Phase 9 CLIENT-04 zero-leakage merge gate.

These tests MUST run as the `app_runtime` role (non-owner, non-BYPASSRLS).
A green test means PostgreSQL RLS policies correctly block cross-client reads.
"""

import pytest
from sqlalchemy import text


pytestmark = pytest.mark.integration


def test_no_cross_client_leakage(db_as_app_runtime, client_a, client_b):
    """Setting tenant context to client_a returns ZERO client_b rows.

    Maps to: CLIENT-04 (zero cross-client leakage). MERGE GATE.
    """
    from app.compliance.models.notice import ComplianceNotice
    # Seed: 10 notices in client_a, 10 in client_b
    for client in (client_a, client_b):
        for i in range(10):
            db_as_app_runtime.execute(
                text("SELECT set_config('app.current_client_id', :cid, true)"),
                {"cid": str(client.id)},
            )
            n = ComplianceNotice(
                client_id=client.id,
                notice_number=f"NTC-{client.id}-{i}",
                authority="GST",
                status="received",
            )
            db_as_app_runtime.add(n)
        db_as_app_runtime.commit()

    # Switch to client_a context
    db_as_app_runtime.execute(
        text("SELECT set_config('app.current_client_id', :cid, true)"),
        {"cid": str(client_a.id)},
    )
    notices = db_as_app_runtime.query(ComplianceNotice).all()
    assert len(notices) == 10
    assert all(n.client_id == client_a.id for n in notices)

    # Try explicit WHERE bypass — RLS still filters
    rows = db_as_app_runtime.execute(
        text("SELECT * FROM compliance_notices WHERE client_id = :other"),
        {"other": client_b.id},
    ).all()
    assert rows == [], "RLS leaked client_b rows when context was client_a"


def test_unset_tenant_returns_empty(db_as_app_runtime, client_a):
    """When app.current_client_id is NOT set, RLS returns no rows (fail-closed)."""
    from app.compliance.models.notice import ComplianceNotice
    # Seed in client_a
    db_as_app_runtime.execute(
        text("SELECT set_config('app.current_client_id', :cid, true)"),
        {"cid": str(client_a.id)},
    )
    n = ComplianceNotice(
        client_id=client_a.id,
        notice_number="NTC-A-1",
        authority="GST",
        status="received",
    )
    db_as_app_runtime.add(n)
    db_as_app_runtime.commit()

    # Reset session — no tenant set
    db_as_app_runtime.execute(text("SELECT set_config('app.current_client_id', '', true)"))
    rows = db_as_app_runtime.query(ComplianceNotice).all()
    assert rows == [], "RLS leaked rows when tenant context was unset"


def test_all_client_tables_have_force_rls(db_as_app_runtime):
    """Every client-scoped table has FORCE ROW LEVEL SECURITY (CI grep guard)."""
    expected_tables = [
        "compliance_clients",
        "compliance_client_registrations",
        "compliance_client_memberships",
        "compliance_notices",
        "compliance_notice_activity",
        "compliance_notice_tags",
    ]
    rows = db_as_app_runtime.execute(
        text(
            """
            SELECT relname, relrowsecurity, relforcerowsecurity
            FROM pg_class
            WHERE relname = ANY(:tables) AND relkind = 'r'
            """
        ),
        {"tables": expected_tables},
    ).all()
    for relname, rls, force in rows:
        assert rls is True, f"{relname} missing ENABLE ROW LEVEL SECURITY"
        assert force is True, f"{relname} missing FORCE ROW LEVEL SECURITY"


def test_cross_client_mode_eligible(db_as_app_runtime, client_a, client_b):
    """'All Clients' mode returns rows from all clients for eligible roles."""
    from app.compliance.models.notice import ComplianceNotice
    # Seed both
    for client in (client_a, client_b):
        db_as_app_runtime.execute(
            text("SELECT set_config('app.current_client_id', :cid, true)"),
            {"cid": str(client.id)},
        )
        db_as_app_runtime.add(
            ComplianceNotice(
                client_id=client.id,
                notice_number=f"NTC-{client.id}",
                authority="GST",
                status="received",
            )
        )
    db_as_app_runtime.commit()

    # Enable cross-client mode + simulate compliance_head user
    db_as_app_runtime.execute(text("SELECT set_config('app.cross_client_mode', 'true', true)"))
    db_as_app_runtime.execute(text("SELECT set_config('app.user_id', '1', true)"))
    # NOTE: User 1 must have compliance_head membership for this test to pass —
    # fixture wires this in Plan 03.

    rows = db_as_app_runtime.query(ComplianceNotice).all()
    assert len(rows) >= 2, "Cross-client mode should return rows from all eligible clients"


def test_cross_client_mode_rejected_for_ineligible_roles(db_as_app_runtime, client_a, client_b):
    """'All Clients' mode is REJECTED for Staff/Auditor/Legal/Finance — they see no rows."""
    from app.compliance.models.notice import ComplianceNotice
    db_as_app_runtime.execute(
        text("SELECT set_config('app.current_client_id', :cid, true)"),
        {"cid": str(client_a.id)},
    )
    db_as_app_runtime.add(
        ComplianceNotice(
            client_id=client_a.id,
            notice_number="NTC-A",
            authority="GST",
            status="received",
        )
    )
    db_as_app_runtime.commit()

    # Enable cross-client mode but as a Staff user (ineligible per D-23)
    db_as_app_runtime.execute(text("SELECT set_config('app.cross_client_mode', 'true', true)"))
    db_as_app_runtime.execute(text("SELECT set_config('app.user_id', '999', true)"))
    # User 999 has Staff role only — NOT eligible for cross-client mode
    rows = db_as_app_runtime.query(ComplianceNotice).all()
    assert rows == [], "Ineligible role granted cross-client visibility"
