"""Audit log immutability — DB-level enforcement.

Revision ID: 0014_audit_log_immutability
Revises: 0013_compliance_foundation_schema
Create Date: 2026-04-27

Hardens the existing audit_logs table (created in migration 0010) with:
  1. Trigger raising EXCEPTION on UPDATE or DELETE (BEFORE UPDATE OR DELETE).
  2. REVOKE UPDATE, DELETE on app_runtime — privilege-level block.
  3. created_at default switched from now() to clock_timestamp() so two rows
     in the same transaction get distinct timestamps.

No schema change, no data migration. Existing audit_logs rows are preserved.
"""
from alembic import op

revision = "0014_audit_log_immutability"
down_revision = "0013_compliance_foundation_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION reject_audit_log_modification()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only — % is forbidden', TG_OP
                USING ERRCODE = 'insufficient_privilege';
        END;
        $$ LANGUAGE plpgsql;

        DROP TRIGGER IF EXISTS audit_logs_immutability ON audit_logs;
        CREATE TRIGGER audit_logs_immutability
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION reject_audit_log_modification();

        REVOKE UPDATE, DELETE ON audit_logs FROM app_runtime;
        REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC;

        ALTER TABLE audit_logs
            ALTER COLUMN created_at SET DEFAULT clock_timestamp();
    """)


def downgrade() -> None:
    op.execute("""
        DROP TRIGGER IF EXISTS audit_logs_immutability ON audit_logs;
        DROP FUNCTION IF EXISTS reject_audit_log_modification();
        GRANT UPDATE, DELETE ON audit_logs TO app_runtime;
        ALTER TABLE audit_logs
            ALTER COLUMN created_at SET DEFAULT now();
    """)
