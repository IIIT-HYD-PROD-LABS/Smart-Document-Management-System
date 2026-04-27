"""Compliance RLS policies — FORCE RLS + tenant_isolation + cross_client_view.

Revision ID: 0015_compliance_rls_policies
Revises: 0014_audit_log_immutability
Create Date: 2026-04-27

For each of the 6 client-scoped compliance tables:
  1. ALTER TABLE ... ENABLE row-level-security
  2. ALTER TABLE ... FORCE row-level-security (Pitfall 1: avoid owner bypass)
  3. GRANT SELECT, INSERT, UPDATE, DELETE TO app_runtime
  4. CREATE POLICY tenant_isolation FOR ALL TO app_runtime
       USING / WITH CHECK on app.current_client_id current_setting
  5. CREATE POLICY cross_client_view FOR SELECT TO app_runtime
       (Pattern A — single role, dual policy; permissive ON top of tenant_isolation)
       USING app.cross_client_mode='true' AND user is in eligible role membership

Tables WITHOUT direct client_id (notice_activity, notice_tags) join through
compliance_notices. compliance_clients filters on its own `id` column.

Eligible roles for cross_client_view per CONTEXT D-23: compliance_head,
ca_consultant, cfo. Auditor / Legal / Finance / Staff are NOT eligible.
"""
from alembic import op

revision = "0015_compliance_rls_policies"
down_revision = "0014_audit_log_immutability"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==================================================================
    # 1) compliance_clients (filter on `id`, not `client_id`)
    # ==================================================================
    op.execute("""
        ALTER TABLE compliance_clients ENABLE ROW LEVEL SECURITY;
        ALTER TABLE compliance_clients FORCE ROW LEVEL SECURITY;
        GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_clients TO app_runtime;

        CREATE POLICY tenant_isolation ON compliance_clients
          FOR ALL TO app_runtime
          USING (id = current_setting('app.current_client_id', true)::int)
          WITH CHECK (id = current_setting('app.current_client_id', true)::int);

        CREATE POLICY cross_client_view ON compliance_clients
          FOR SELECT TO app_runtime
          USING (
            current_setting('app.cross_client_mode', true) = 'true'
            AND current_setting('app.user_id', true) IS NOT NULL
            AND current_setting('app.user_id', true) != ''
            AND EXISTS (
              SELECT 1 FROM compliance_client_memberships m
              WHERE m.user_id = current_setting('app.user_id', true)::int
                AND m.compliance_role IN ('compliance_head', 'ca_consultant', 'cfo')
                AND (m.access_end IS NULL OR m.access_end > now())
            )
          );
    """)

    # ==================================================================
    # 2) compliance_client_registrations (filter on client_id)
    # ==================================================================
    op.execute("""
        ALTER TABLE compliance_client_registrations ENABLE ROW LEVEL SECURITY;
        ALTER TABLE compliance_client_registrations FORCE ROW LEVEL SECURITY;
        GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_client_registrations TO app_runtime;

        CREATE POLICY tenant_isolation ON compliance_client_registrations
          FOR ALL TO app_runtime
          USING (client_id = current_setting('app.current_client_id', true)::int)
          WITH CHECK (client_id = current_setting('app.current_client_id', true)::int);

        CREATE POLICY cross_client_view ON compliance_client_registrations
          FOR SELECT TO app_runtime
          USING (
            current_setting('app.cross_client_mode', true) = 'true'
            AND current_setting('app.user_id', true) IS NOT NULL
            AND current_setting('app.user_id', true) != ''
            AND EXISTS (
              SELECT 1 FROM compliance_client_memberships m
              WHERE m.user_id = current_setting('app.user_id', true)::int
                AND m.compliance_role IN ('compliance_head', 'ca_consultant', 'cfo')
                AND (m.access_end IS NULL OR m.access_end > now())
            )
          );
    """)

    # ==================================================================
    # 3) compliance_client_memberships (filter on client_id)
    # ==================================================================
    op.execute("""
        ALTER TABLE compliance_client_memberships ENABLE ROW LEVEL SECURITY;
        ALTER TABLE compliance_client_memberships FORCE ROW LEVEL SECURITY;
        GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_client_memberships TO app_runtime;

        CREATE POLICY tenant_isolation ON compliance_client_memberships
          FOR ALL TO app_runtime
          USING (client_id = current_setting('app.current_client_id', true)::int)
          WITH CHECK (client_id = current_setting('app.current_client_id', true)::int);

        CREATE POLICY cross_client_view ON compliance_client_memberships
          FOR SELECT TO app_runtime
          USING (
            current_setting('app.cross_client_mode', true) = 'true'
            AND current_setting('app.user_id', true) IS NOT NULL
            AND current_setting('app.user_id', true) != ''
            AND EXISTS (
              SELECT 1 FROM compliance_client_memberships m
              WHERE m.user_id = current_setting('app.user_id', true)::int
                AND m.compliance_role IN ('compliance_head', 'ca_consultant', 'cfo')
                AND (m.access_end IS NULL OR m.access_end > now())
            )
          );
    """)

    # ==================================================================
    # 4) compliance_notices (filter on client_id)
    # ==================================================================
    op.execute("""
        ALTER TABLE compliance_notices ENABLE ROW LEVEL SECURITY;
        ALTER TABLE compliance_notices FORCE ROW LEVEL SECURITY;
        GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_notices TO app_runtime;

        CREATE POLICY tenant_isolation ON compliance_notices
          FOR ALL TO app_runtime
          USING (client_id = current_setting('app.current_client_id', true)::int)
          WITH CHECK (client_id = current_setting('app.current_client_id', true)::int);

        CREATE POLICY cross_client_view ON compliance_notices
          FOR SELECT TO app_runtime
          USING (
            current_setting('app.cross_client_mode', true) = 'true'
            AND current_setting('app.user_id', true) IS NOT NULL
            AND current_setting('app.user_id', true) != ''
            AND EXISTS (
              SELECT 1 FROM compliance_client_memberships m
              WHERE m.user_id = current_setting('app.user_id', true)::int
                AND m.compliance_role IN ('compliance_head', 'ca_consultant', 'cfo')
                AND (m.access_end IS NULL OR m.access_end > now())
            )
          );
    """)

    # ==================================================================
    # 5) compliance_notice_activity (no client_id; JOIN via notice_id)
    # ==================================================================
    op.execute("""
        ALTER TABLE compliance_notice_activity ENABLE ROW LEVEL SECURITY;
        ALTER TABLE compliance_notice_activity FORCE ROW LEVEL SECURITY;
        GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_notice_activity TO app_runtime;

        CREATE POLICY tenant_isolation ON compliance_notice_activity
          FOR ALL TO app_runtime
          USING (notice_id IN (
            SELECT id FROM compliance_notices
            WHERE client_id = current_setting('app.current_client_id', true)::int
          ))
          WITH CHECK (notice_id IN (
            SELECT id FROM compliance_notices
            WHERE client_id = current_setting('app.current_client_id', true)::int
          ));

        CREATE POLICY cross_client_view ON compliance_notice_activity
          FOR SELECT TO app_runtime
          USING (
            current_setting('app.cross_client_mode', true) = 'true'
            AND current_setting('app.user_id', true) IS NOT NULL
            AND current_setting('app.user_id', true) != ''
            AND EXISTS (
              SELECT 1 FROM compliance_client_memberships m
              WHERE m.user_id = current_setting('app.user_id', true)::int
                AND m.compliance_role IN ('compliance_head', 'ca_consultant', 'cfo')
                AND (m.access_end IS NULL OR m.access_end > now())
            )
          );
    """)

    # ==================================================================
    # 6) compliance_notice_tags (no client_id; JOIN via notice_id)
    # ==================================================================
    op.execute("""
        ALTER TABLE compliance_notice_tags ENABLE ROW LEVEL SECURITY;
        ALTER TABLE compliance_notice_tags FORCE ROW LEVEL SECURITY;
        GRANT SELECT, INSERT, UPDATE, DELETE ON compliance_notice_tags TO app_runtime;

        CREATE POLICY tenant_isolation ON compliance_notice_tags
          FOR ALL TO app_runtime
          USING (notice_id IN (
            SELECT id FROM compliance_notices
            WHERE client_id = current_setting('app.current_client_id', true)::int
          ))
          WITH CHECK (notice_id IN (
            SELECT id FROM compliance_notices
            WHERE client_id = current_setting('app.current_client_id', true)::int
          ));

        CREATE POLICY cross_client_view ON compliance_notice_tags
          FOR SELECT TO app_runtime
          USING (
            current_setting('app.cross_client_mode', true) = 'true'
            AND current_setting('app.user_id', true) IS NOT NULL
            AND current_setting('app.user_id', true) != ''
            AND EXISTS (
              SELECT 1 FROM compliance_client_memberships m
              WHERE m.user_id = current_setting('app.user_id', true)::int
                AND m.compliance_role IN ('compliance_head', 'ca_consultant', 'cfo')
                AND (m.access_end IS NULL OR m.access_end > now())
            )
          );
    """)


def downgrade() -> None:
    # Reverse order: drop policies, then DISABLE+UN-FORCE RLS, then REVOKE.
    for table in (
        "compliance_notice_tags",
        "compliance_notice_activity",
        "compliance_notices",
        "compliance_client_memberships",
        "compliance_client_registrations",
        "compliance_clients",
    ):
        op.execute(f"DROP POLICY IF EXISTS cross_client_view ON {table};")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(f"ALTER TABLE {table} NO FORCE row level security;")
        op.execute(f"ALTER TABLE {table} DISABLE row level security;")
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM app_runtime;")
