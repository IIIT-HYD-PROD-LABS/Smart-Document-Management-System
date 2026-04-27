"""Phase 9 Plan 04: tenant_isolation policies fail-closed on empty tenant context.

Bug uncovered while running test_rls_isolation::test_unset_tenant_returns_empty:

    ``client_id = current_setting('app.current_client_id', true)::integer``

When current_setting returns an empty string (e.g. after the connection
checkin listener resets it via ``set_config(..., '', false)``, or when no
middleware has set it on a fresh connection), PostgreSQL raises
``invalid input syntax for type integer: ""`` instead of evaluating the
policy to NULL/false.

The merge gate test asserts ``rows == []`` (fail-closed). A raised
exception is technically also fail-closed but breaks the contract — and
worse, surfaces an unhandled DB error to the route handler.

Fix: wrap the cast with ``NULLIF(..., '')`` so empty string yields NULL,
the cast on NULL is NULL, and ``client_id = NULL`` evaluates to NULL
(treated as false by RLS — no rows visible).

Affected tables (5):
  - compliance_client_registrations
  - compliance_client_memberships
  - compliance_notices
  - compliance_notice_activity
  - compliance_notice_tags

NOT affected:
  - compliance_clients — its tenant_isolation was already rewritten in
    0018 to use the SECURITY DEFINER helper user_has_client_membership.

Idempotent: DROP POLICY IF EXISTS + CREATE POLICY on each table.
"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "0019_rls_fail_closed_on_empty_tenant"
down_revision = "0018_fix_rls_cross_client_recursion"
branch_labels = None
depends_on = None


# Tables whose tenant_isolation has direct client_id column (USING + WITH CHECK)
TABLES_WITH_DIRECT_CLIENT_ID = [
    "compliance_client_registrations",
    "compliance_client_memberships",
    "compliance_notices",
]

# Tables whose tenant_isolation joins through compliance_notices.client_id
TABLES_JOINED_VIA_NOTICE = [
    "compliance_notice_activity",
    "compliance_notice_tags",
]


def upgrade() -> None:
    # 1) Direct-client-id tables: USING + WITH CHECK against NULLIF(...)
    for table in TABLES_WITH_DIRECT_CLIENT_ID:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            FOR ALL
            TO app_runtime
            USING (
                client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
            )
            WITH CHECK (
                client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
            );
            """
        )

    # 2) Join-via-notice tables: same NULLIF pattern, IN (SELECT...) form
    #    matching the existing 0015 policy structure on these tables.
    for table in TABLES_JOINED_VIA_NOTICE:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            FOR ALL
            TO app_runtime
            USING (
                notice_id IN (
                    SELECT id FROM compliance_notices
                    WHERE client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
                )
            )
            WITH CHECK (
                notice_id IN (
                    SELECT id FROM compliance_notices
                    WHERE client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
                )
            );
            """
        )


def downgrade() -> None:
    # Restore the original (broken-on-empty) policies from 0015 / 0018.
    # Direct-client-id tables.
    for table in TABLES_WITH_DIRECT_CLIENT_ID:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            FOR ALL
            TO app_runtime
            USING (
                client_id = (current_setting('app.current_client_id', true))::integer
            )
            WITH CHECK (
                client_id = (current_setting('app.current_client_id', true))::integer
            );
            """
        )

    # Join-via-notice tables.
    for table in TABLES_JOINED_VIA_NOTICE:
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            FOR ALL
            TO app_runtime
            USING (
                notice_id IN (
                    SELECT id FROM compliance_notices
                    WHERE client_id = (current_setting('app.current_client_id', true))::integer
                )
            )
            WITH CHECK (
                notice_id IN (
                    SELECT id FROM compliance_notices
                    WHERE client_id = (current_setting('app.current_client_id', true))::integer
                )
            );
            """
        )
