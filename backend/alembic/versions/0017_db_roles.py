"""Create DB roles app_migrator (owner) and app_runtime (subject to RLS).

Revision ID: 0017_db_roles
Revises: 0016_regulatory_calendar_seed (re-chained in Task 5 — initially set to 0012 to keep migration tree valid before 0013-0016 land)
Create Date: 2026-04-27

Per 09-RESEARCH.md Pattern 1 — app_migrator has BYPASSRLS implicit (owner);
app_runtime is the FastAPI process role and is subject to RLS policies.

Passwords are read from env vars APP_MIGRATOR_PASSWORD and APP_RUNTIME_PASSWORD.
Operators set these in .env before running alembic upgrade head.
"""

import os
from alembic import op

revision = "0017_db_roles"
down_revision = "0012_add_early_access_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    migrator_pwd = os.environ.get("APP_MIGRATOR_PASSWORD", "smartdocs_migrator_dev")
    runtime_pwd = os.environ.get("APP_RUNTIME_PASSWORD", "smartdocs_runtime_dev")

    # Idempotent role creation — safe to re-run
    op.execute(f"""
        DO $$
        BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_migrator') THEN
            CREATE ROLE app_migrator WITH LOGIN PASSWORD '{migrator_pwd}' CREATEDB;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
            CREATE ROLE app_runtime WITH LOGIN PASSWORD '{runtime_pwd}';
          END IF;
        END $$;
    """)
    op.execute("GRANT CONNECT ON DATABASE postgres TO app_runtime;")
    # Grant on existing schema; tables created in 0013 will receive their grants there
    op.execute("GRANT USAGE ON SCHEMA public TO app_runtime;")

    # CRITICAL: app_runtime needs SELECT on already-existing v1.0 tables for cross-domain queries
    # but the v1.0 tables (users, documents) are NOT under RLS per CONTEXT D-21
    op.execute("""
        GRANT SELECT, INSERT, UPDATE, DELETE ON
          users, documents, audit_logs, refresh_tokens, document_permissions,
          document_versions, early_access_requests
        TO app_runtime;
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_runtime;
    """)


def downgrade() -> None:
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_runtime;")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM app_runtime;")
    op.execute("REVOKE USAGE ON SCHEMA public FROM app_runtime;")
    op.execute("REVOKE CONNECT ON DATABASE postgres FROM app_runtime;")
    op.execute("DROP ROLE IF EXISTS app_runtime;")
    op.execute("DROP ROLE IF EXISTS app_migrator;")
