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


def test_no_rls_table_lacks_force(db_as_app_runtime):
    """Catalog-derived guard: any table with RLS ENABLED must also be FORCEd,
    otherwise a table-owner-ish role silently bypasses it. Catches the
    'enabled but not forced' gap on tables added after the original six without
    hardcoding the (growing) client-scoped table list."""
    rows = db_as_app_runtime.execute(
        text(
            "SELECT relname FROM pg_class "
            "WHERE relkind = 'r' AND relrowsecurity AND NOT relforcerowsecurity"
        )
    ).all()
    offenders = [r[0] for r in rows]
    # Intentionally RLS-enabled-but-not-FORCEd globals: the v1.0 tables
    # users/documents/refresh_tokens carry a permissive `app_runtime_full`
    # USING(true) passthrough policy (0024, added to satisfy the Supabase
    # advisor's "RLS disabled" flag) — they are NOT client-scoped, so FORCE is
    # irrelevant; app-layer user_id filtering is their isolation. alembic_version
    # is owner-only migration metadata. audit_logs (0040) is the append-only
    # regulatory ledger: NOT client-scoped (no client_id; reads are API-gated),
    # with permissive INSERT+SELECT policies for app_runtime and no UPDATE/DELETE
    # policy so immutability holds — FORCE is irrelevant for it too.
    # No CLIENT-scoped table may appear here.
    allowed = {"alembic_version", "users", "documents", "refresh_tokens", "audit_logs"}
    unexpected = [t for t in offenders if t not in allowed]
    assert not unexpected, f"client-scoped table RLS enabled but not FORCEd: {unexpected}"


def test_app_runtime_can_read_non_rls_lookup_tables(db_as_app_runtime):
    """0038 grant gap: the two lookup tables forgotten by every prior migration
    (compliance_notice_types, compliance_regulatory_calendar) must be SELECTable
    by app_runtime, or every notice-type / calendar lookup 500s under RLS."""
    db_as_app_runtime.execute(text("RESET ROLE"))
    db_as_app_runtime.execute(text("SET LOCAL ROLE app_runtime"))
    for table in ("compliance_notice_types", "compliance_regulatory_calendar"):
        # Must not raise 'permission denied for table ...'.
        db_as_app_runtime.execute(text(f"SELECT count(*) FROM {table}"))


def test_self_membership_view_policy(db_as_app_runtime, client_a):
    """0039: with only app.user_id set (no client context — the client-switcher
    discovery path), a user reads their OWN membership rows and no others."""
    from app.compliance.models.membership import ClientMembership

    db_as_app_runtime.execute(text("RESET ROLE"))
    db_as_app_runtime.execute(text("SET LOCAL ROLE app_runtime"))
    db_as_app_runtime.execute(
        text("SELECT set_config('app.current_client_id', '', true)")
    )
    db_as_app_runtime.execute(text("SELECT set_config('app.cross_client_mode', 'false', true)"))
    # client_a created a compliance_head membership for user_id=1.
    db_as_app_runtime.execute(text("SELECT set_config('app.user_id', '1', true)"))
    own = db_as_app_runtime.query(ClientMembership).all()
    assert own, "user 1 should see their own membership via self_membership_view"
    assert all(m.user_id == 1 for m in own)

    # A different user sees none of user 1's memberships.
    db_as_app_runtime.execute(text("SELECT set_config('app.user_id', '999', true)"))
    others = db_as_app_runtime.query(ClientMembership).all()
    assert all(m.user_id == 999 for m in others)


def test_cross_client_mode_eligible(db_as_app_runtime, client_a, client_b):
    """'All Clients' mode returns rows from all clients for eligible roles."""
    from app.compliance.models.notice import ComplianceNotice
    # Seed both. Flush after each add so the per-iteration set_config is in
    # effect when the INSERT actually runs against RLS WITH CHECK; otherwise
    # SQLAlchemy buffers all adds and only the LAST set_config is in effect
    # at commit-time flush.
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
        db_as_app_runtime.flush()
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
