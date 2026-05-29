"""Create DB roles app_migrator (owner) and app_runtime (subject to RLS).

Revision ID: 0017_db_roles
Revises: 0013_compliance_foundation_schema
Create Date: 2026-04-27

Per 09-RESEARCH.md Pattern 1 — app_migrator has BYPASSRLS implicit (owner);
app_runtime is the FastAPI process role and is subject to RLS policies.

Passwords are read from env vars APP_MIGRATOR_PASSWORD and APP_RUNTIME_PASSWORD.
Operators set these in .env before running alembic upgrade head.

CHAIN ORDER (deviation from plan):
  Plan specified 0012 -> 0013 -> 0014 -> 0015 -> 0016 -> 0017.
  But 0014 (REVOKE on app_runtime) and 0015 (CREATE POLICY ... TO app_runtime)
  fail when app_runtime does not yet exist. CREATE POLICY does NOT have an
  IF NOT EXISTS / DO block escape hatch for the role reference.
  Therefore 0017 (role creation) must run BEFORE 0014/0015.
  Final working chain: 0012 -> 0013 -> 0017 -> 0014 -> 0015 -> 0016.
  Head is 0016_regulatory_calendar_seed.
"""

import os
from alembic import op

revision = "0017_db_roles"
down_revision = "0013_compliance_foundation_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Escape single quotes so a quote in the password can't break out of the SQL literal
    migrator_pwd = os.environ.get("APP_MIGRATOR_PASSWORD", "smartdocs_migrator_dev").replace("'", "''")
    runtime_pwd = os.environ.get("APP_RUNTIME_PASSWORD", "smartdocs_runtime_dev").replace("'", "''")

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
