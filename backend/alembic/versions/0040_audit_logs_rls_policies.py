"""Add RLS INSERT/SELECT policies for audit_logs under app_runtime.

Why:
    audit_logs had RLS ENABLED (relrowsecurity=true) but ZERO policies. When
    FastAPI runs as the non-owner app_runtime role (DB_ENFORCE_RLS=true), RLS
    default-denies every operation that lacks a permissive policy. Result: every
    audit write (notice_ai_extract, the per-field accept-extraction rows,
    response approvals, etc.) failed with "new row violates row-level security
    policy for table audit_logs", fell to the dead-letter file, and the
    per-field retry loop added ~30s to a single notice save. The regulatory
    audit trail recorded nothing. The RLS activation (0038) granted privileges
    on audit_logs but never created its policies.

    audit_logs is append-only and NOT client-scoped (no client_id column; reads
    are gated at the API layer). The correct policies are therefore a permissive
    INSERT and SELECT for app_runtime. UPDATE/DELETE intentionally get NO policy,
    so they stay denied and the append-only immutability holds (alongside the
    existing immutability trigger).

    Additive + idempotent (DROP POLICY IF EXISTS + app_runtime guard), so it is a
    no-op on fresh dev databases that pre-date the app_runtime role.
"""
from alembic import op


revision = "0040_audit_logs_rls_policies"
down_revision = "0039_rls_self_membership_policy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    DO $do$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
            EXECUTE 'ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY';
            EXECUTE 'DROP POLICY IF EXISTS audit_logs_insert ON audit_logs';
            EXECUTE 'CREATE POLICY audit_logs_insert ON audit_logs '
                    'AS PERMISSIVE FOR INSERT TO app_runtime WITH CHECK (true)';
            EXECUTE 'DROP POLICY IF EXISTS audit_logs_select ON audit_logs';
            EXECUTE 'CREATE POLICY audit_logs_select ON audit_logs '
                    'AS PERMISSIVE FOR SELECT TO app_runtime USING (true)';
        END IF;
    END $do$;
    """)


def downgrade() -> None:
    op.execute("""
    DO $do$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
            EXECUTE 'DROP POLICY IF EXISTS audit_logs_insert ON audit_logs';
            EXECUTE 'DROP POLICY IF EXISTS audit_logs_select ON audit_logs';
        END IF;
    END $do$;
    """)
