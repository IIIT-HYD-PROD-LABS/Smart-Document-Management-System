"""Fix RLS infinite recursion + compliance_clients tenant-isolation circularity.

Revision ID: 0018_fix_rls_cross_client_recursion
Revises: 0016_regulatory_calendar_seed
Create Date: 2026-04-27

Two bugs in the RLS policies created by 0015 surface as soon as Plan 03's
ORM models try to write to client-scoped tables:

Bug 1: Infinite recursion in cross_client_view

    The cross_client_view policies created in 0015 contain an EXISTS
    subquery against compliance_client_memberships. When evaluated on
    compliance_client_memberships itself (or on any table whose policy
    references memberships), PostgreSQL re-applies the SAME policy to
    the inner SELECT — yielding "infinite recursion detected in policy
    for relation 'compliance_client_memberships'".

    The recursion is triggered by INSERT ... RETURNING on
    compliance_clients (which fires SELECT-style RLS for the RETURNING
    clause), which evaluates compliance_clients.cross_client_view, which
    queries compliance_client_memberships, which evaluates
    compliance_client_memberships.cross_client_view, which queries
    compliance_client_memberships again — infinite loop.

Bug 2: tenant_isolation on compliance_clients is unsatisfiable for INSERT

    The 0015 tenant_isolation USING/WITH CHECK on compliance_clients is
    ``id = current_setting('app.current_client_id')::int``. Because the
    primary key is auto-generated, the WITH CHECK clause is unsatisfiable
    on INSERT — the row's id does not exist before the INSERT completes.

    The policy is also semantically wrong even for SELECT: a CA/Compliance
    Head should be able to LIST all clients they have a membership on,
    not just one at a time gated by a single tenant context. tenant_isolation
    on this parent table should be membership-based, not tenant-id-based.

Fix:

    1. SECURITY DEFINER helpers — `is_cross_client_eligible(user_id)` and
       `user_has_client_membership(user_id, client_id)` — run as the
       function owner (postgres) and therefore bypass RLS on the
       membership lookup. The function signatures are stable so the
       policies can call them without further recursion risk.

    2. cross_client_view on all 6 client-scoped tables drops the inline
       EXISTS and calls is_cross_client_eligible() instead.

    3. tenant_isolation on compliance_clients drops the
       ``id = current_client_id`` rule and uses
       user_has_client_membership(current_user_id, id) instead. This makes
       INSERTs work (writer must have a membership on the new client OR
       be running with app.cross_client_mode='true' as an eligible role
       which is the admin onboarding path).

Backwards compatibility: tenant_isolation policies on the OTHER 5 tables
(registrations, memberships, notices, activity, tags) are untouched —
their ``client_id = current_client_id`` rule works correctly because
client_id is supplied by the caller, not auto-generated.
"""
from alembic import op


revision = "0018_fix_rls_cross_client_recursion"
down_revision = "0016_regulatory_calendar_seed"
branch_labels = None
depends_on = None


CROSS_CLIENT_TABLES = (
    "compliance_clients",
    "compliance_client_registrations",
    "compliance_client_memberships",
    "compliance_notices",
    "compliance_notice_activity",
    "compliance_notice_tags",
)


def upgrade() -> None:
    # 1) Helper functions — SECURITY DEFINER bypasses RLS on the inner lookup.
    op.execute("""
        CREATE OR REPLACE FUNCTION is_cross_client_eligible(p_user_id int)
        RETURNS boolean
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        SET search_path = public, pg_temp
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM compliance_client_memberships m
                WHERE m.user_id = p_user_id
                  AND m.compliance_role IN
                      ('compliance_head', 'ca_consultant', 'cfo')
                  AND (m.access_end IS NULL OR m.access_end > now())
            );
        $$;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION user_has_client_membership(
            p_user_id int, p_client_id int
        )
        RETURNS boolean
        LANGUAGE sql
        SECURITY DEFINER
        STABLE
        SET search_path = public, pg_temp
        AS $$
            SELECT EXISTS (
                SELECT 1 FROM compliance_client_memberships m
                WHERE m.user_id = p_user_id
                  AND m.client_id = p_client_id
                  AND (m.access_end IS NULL OR m.access_end > now())
            );
        $$;
    """)
    op.execute(
        "GRANT EXECUTE ON FUNCTION is_cross_client_eligible(int) TO app_runtime;"
    )
    op.execute(
        "GRANT EXECUTE ON FUNCTION user_has_client_membership(int, int) "
        "TO app_runtime;"
    )

    # 2) Re-create cross_client_view on all 6 client-scoped tables using the
    #    SECURITY DEFINER helper.
    for table in (
        "compliance_clients",
        "compliance_client_registrations",
        "compliance_client_memberships",
        "compliance_notices",
        "compliance_notice_activity",
        "compliance_notice_tags",
    ):
        op.execute(f"DROP POLICY IF EXISTS cross_client_view ON {table};")
        op.execute(f"""
            CREATE POLICY cross_client_view ON {table}
              FOR SELECT TO app_runtime
              USING (
                current_setting('app.cross_client_mode', true) = 'true'
                AND current_setting('app.user_id', true) IS NOT NULL
                AND current_setting('app.user_id', true) != ''
                AND is_cross_client_eligible(
                    current_setting('app.user_id', true)::int
                )
              );
        """)

    # 3) Replace tenant_isolation on compliance_clients with a
    #    membership-based rule. INSERT/UPDATE/DELETE rows where the actor
    #    has membership; SELECT same. The cross_client_view policy already
    #    handles the "All Clients" cross-tenant read path.
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON compliance_clients;")
    op.execute("""
        CREATE POLICY tenant_isolation ON compliance_clients
          FOR ALL TO app_runtime
          USING (
            current_setting('app.user_id', true) IS NOT NULL
            AND current_setting('app.user_id', true) != ''
            AND user_has_client_membership(
                current_setting('app.user_id', true)::int, id
            )
          )
          WITH CHECK (
            current_setting('app.user_id', true) IS NOT NULL
            AND current_setting('app.user_id', true) != ''
            AND user_has_client_membership(
                current_setting('app.user_id', true)::int, id
            )
          );
    """)
    # Onboarding insert path: the row being created cannot satisfy the
    # membership check (no membership exists yet). We add a permissive
    # INSERT policy that allows the bootstrap insert when the actor is
    # eligible for cross_client_mode (admin role). Application code is
    # responsible for setting app.cross_client_mode='true' for the
    # onboarding endpoint.
    op.execute("""
        CREATE POLICY onboarding_insert ON compliance_clients
          AS PERMISSIVE
          FOR INSERT TO app_runtime
          WITH CHECK (
            current_setting('app.cross_client_mode', true) = 'true'
            AND current_setting('app.user_id', true) IS NOT NULL
            AND current_setting('app.user_id', true) != ''
            AND is_cross_client_eligible(
                current_setting('app.user_id', true)::int
            )
          );
    """)


def downgrade() -> None:
    # Drop the onboarding policy added in upgrade.
    op.execute("DROP POLICY IF EXISTS onboarding_insert ON compliance_clients;")

    # Restore the original (buggy) tenant_isolation on compliance_clients.
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON compliance_clients;")
    op.execute("""
        CREATE POLICY tenant_isolation ON compliance_clients
          FOR ALL TO app_runtime
          USING (id = current_setting('app.current_client_id', true)::int)
          WITH CHECK (id = current_setting('app.current_client_id', true)::int);
    """)

    # Restore inline EXISTS cross_client_view policies (the original buggy
    # form). Acceptable for downgrade — production never used the buggy
    # form at runtime (this fix landed before any cross-client read path
    # was wired in middleware).
    for table in (
        "compliance_notice_tags",
        "compliance_notice_activity",
        "compliance_notices",
        "compliance_client_memberships",
        "compliance_client_registrations",
        "compliance_clients",
    ):
        op.execute(f"DROP POLICY IF EXISTS cross_client_view ON {table};")
        op.execute(f"""
            CREATE POLICY cross_client_view ON {table}
              FOR SELECT TO app_runtime
              USING (
                current_setting('app.cross_client_mode', true) = 'true'
                AND current_setting('app.user_id', true) IS NOT NULL
                AND current_setting('app.user_id', true) != ''
                AND EXISTS (
                  SELECT 1 FROM compliance_client_memberships m
                  WHERE m.user_id = current_setting('app.user_id', true)::int
                    AND m.compliance_role IN
                        ('compliance_head', 'ca_consultant', 'cfo')
                    AND (m.access_end IS NULL OR m.access_end > now())
                )
              );
        """)

    op.execute(
        "REVOKE EXECUTE ON FUNCTION user_has_client_membership(int, int) "
        "FROM app_runtime;"
    )
    op.execute(
        "DROP FUNCTION IF EXISTS user_has_client_membership(int, int);"
    )
    op.execute(
        "REVOKE EXECUTE ON FUNCTION is_cross_client_eligible(int) FROM app_runtime;"
    )
    op.execute("DROP FUNCTION IF EXISTS is_cross_client_eligible(int);")
