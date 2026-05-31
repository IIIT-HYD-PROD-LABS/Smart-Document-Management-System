"""RLS activation: comprehensive app_runtime grants.

Revision ID: 0038_rls_activation_grants
Revises: 0037_dedup_constraints_and_drop_cross_client_ai
Create Date: 2026-06-01

Closes the grant gap so the FastAPI process can connect as the non-owner
``app_runtime`` role (DATABASE_URL_RUNTIME + DB_ENFORCE_RLS=true) and have the
RLS policies enforced WITHOUT hitting permission-denied on tables, sequences, or
functions added by migrations after 0017 (alerts, response workflow, gmail,
ai_credentials, mfa, etc., several of which never granted app_runtime).

Migration 0017 granted only a fixed set of v1.0 tables plus the compliance
tables granted in their own migrations; this blanket-grants everything in the
public schema and sets default privileges so future migration-created objects
inherit the grant too.

Granting DML does NOT bypass RLS — Postgres still filters rows on every table
that has ENABLE/FORCE ROW LEVEL SECURITY. This migration only provides the
underlying object privileges RLS needs in order to apply. EXECUTE on functions
is required because the RLS policies call ``user_has_client_membership(...)``
(migration 0018); without it the policy check itself raises permission-denied.

This migration is safe to run at any time (idempotent GRANTs, owner-only,
no behavior change until DB_ENFORCE_RLS is flipped). Run it against the target
database BEFORE setting DB_ENFORCE_RLS=true.
"""
from alembic import op


revision = "0038_rls_activation_grants"
down_revision = "0037_dedup_constraints_and_drop_cross_client_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT USAGE ON SCHEMA public TO app_runtime;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
        "TO app_runtime;"
    )
    op.execute(
        "GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO app_runtime;"
    )
    op.execute("GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO app_runtime;")
    # Future migration-created objects inherit the same grants (the migration
    # owner is the creating role, so default privileges apply to them).
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_runtime;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO app_runtime;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "GRANT EXECUTE ON FUNCTIONS TO app_runtime;"
    )

    # Re-narrow two boundaries the blanket grant above widened. We deliberately
    # do NOT re-revoke the response-workflow tables: the app legitimately
    # UPDATEs notice_responses.status, review-queue claim/resolve, and alert
    # dispatch rows, so a blanket "append-only" revoke there would break the
    # workflow. RLS still scopes those rows per tenant.
    #
    # audit_logs is append-only (0014 revoked UPDATE/DELETE + an immutability
    # trigger). Keep the grant boundary aligned with the trigger as defense in
    # depth — the app only ever INSERTs and SELECTs audit rows.
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM app_runtime;")
    # alembic_version is owner-only migration metadata; the app never writes it.
    op.execute(
        "REVOKE INSERT, UPDATE, DELETE ON alembic_version FROM app_runtime;"
    )


def downgrade() -> None:
    # Only undo the default-privilege rules added here. Table/sequence grants
    # are intentionally left in place: 0017 and later migrations granted
    # specific objects, and a blanket REVOKE would over-revoke beyond this
    # migration's additions and could break a DB still running under the owner.
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM app_runtime;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM app_runtime;"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        "REVOKE EXECUTE ON FUNCTIONS FROM app_runtime;"
    )
