"""Enable RLS + grant app_runtime on ai_credentials.

Revision ID: 0033_ai_credentials_rls
Revises: 0032_add_ai_credentials
Create Date: 2026-05-18

Why:
    Migration 0032 created `ai_credentials` as a tenant-scoped table but
    omitted the RLS bootstrap + GRANT pattern that every other tenant
    table received in 0017 / 0025. Consequences when FastAPI runs as
    `app_runtime` (the intended prod config):

      * `get_credential()` returns None for every tenant because the
        SELECT has no privilege → every AI endpoint replies HTTP 412.
      * `set_credential()` raises `permission denied for table
        ai_credentials` → HTTP 500.

    If the deployment is mis-wired to a superuser/`service_role` account,
    the encrypted keys are accessible cross-tenant via integer-ID
    enumeration, mitigated only by the application-layer client_id
    filter in `routers/ai.py:130-156`.

    This migration is additive: same DO-block guards as 0025 so it is a
    no-op on fresh Postgres instances that pre-date the app_runtime role.
"""
from alembic import op


revision = "0033_ai_credentials_rls"
down_revision = "0032_add_ai_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Guard the ENABLE/FORCE inside the same app_runtime check so this
    # migration is a no-op on fresh dev databases that pre-date migration
    # 0017 (where `app_runtime` is created). Without the guard, FORCE RLS
    # applies even to the table owner and every CRUD on ai_credentials
    # returns zero rows because no policy is created in this branch.
    op.execute("""
    DO $do$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
            EXECUTE 'ALTER TABLE ai_credentials ENABLE ROW LEVEL SECURITY';
            EXECUTE 'ALTER TABLE ai_credentials FORCE ROW LEVEL SECURITY';
        END IF;
    END $do$;
    """)

    op.execute("""
    DO $do$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
            EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON ai_credentials';
            EXECUTE $policy$
            CREATE POLICY tenant_isolation ON ai_credentials
            AS PERMISSIVE FOR ALL TO app_runtime
            USING (
                client_id = NULLIF(current_setting('app.current_client_id', true), '')::int
            )
            WITH CHECK (
                client_id = NULLIF(current_setting('app.current_client_id', true), '')::int
            )
            $policy$;
        END IF;
    END $do$;
    """)

    op.execute("""
    DO $do$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime')
           AND EXISTS (
               SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
               WHERE n.nspname = 'public' AND p.proname = 'is_cross_client_eligible'
           ) THEN
            EXECUTE 'DROP POLICY IF EXISTS cross_client_view ON ai_credentials';
            EXECUTE $policy$
            CREATE POLICY cross_client_view ON ai_credentials
            AS PERMISSIVE FOR SELECT TO app_runtime
            USING (
                current_setting('app.cross_client_mode', true) = 'true'
                AND current_setting('app.user_id', true) IS NOT NULL
                AND current_setting('app.user_id', true) != ''
                AND is_cross_client_eligible(
                    current_setting('app.user_id', true)::int
                )
            )
            $policy$;
        END IF;
    END $do$;
    """)

    op.execute("""
    DO $do$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
            EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON ai_credentials TO app_runtime';
            EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE ai_credentials_id_seq TO app_runtime';
        END IF;
    END $do$;
    """)


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON ai_credentials;")
    op.execute("DROP POLICY IF EXISTS cross_client_view ON ai_credentials;")
    # Mirror the upgrade guard: only NO FORCE / DISABLE RLS on databases
    # that had app_runtime (i.e., where upgrade actually enabled RLS).
    op.execute("""
    DO $do$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
            EXECUTE 'ALTER TABLE ai_credentials NO FORCE ROW LEVEL SECURITY';
            EXECUTE 'ALTER TABLE ai_credentials DISABLE ROW LEVEL SECURITY';
            EXECUTE 'REVOKE ALL ON ai_credentials FROM app_runtime';
            EXECUTE 'REVOKE ALL ON SEQUENCE ai_credentials_id_seq FROM app_runtime';
        END IF;
    END $do$;
    """)
