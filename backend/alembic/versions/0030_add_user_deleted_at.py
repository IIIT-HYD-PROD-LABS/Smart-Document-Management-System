"""Add users.deleted_at for admin soft-delete with PII anonymization.

Revision ID: 0030_add_user_deleted_at
Revises: 0029_apscheduler_disable_rls
Create Date: 2026-05-08

Why soft-delete and not a hard ``DELETE FROM users``:

The Phase 6 audit trail (migration 0010) and the Phase 9 immutability
hardening (migration 0014) installed a ``BEFORE UPDATE OR DELETE`` trigger
on ``audit_logs`` that raises ``EXCEPTION 'audit_logs is append-only — %
is forbidden'`` on any modification. ``audit_logs.user_id`` has
``ON DELETE SET NULL``, which Postgres implements as an UPDATE on the
referencing row. That UPDATE fires the immutability trigger, raises
EXCEPTION, and aborts the parent ``DELETE FROM users``.

The cleanest production-safe answer — and the one that matches the
existing security model — is to keep the row, anonymize its PII, mark
``deleted_at``, revoke refresh tokens, and let the FK CASCADE handle
documents + own document_permissions. ``audit_logs`` is never touched,
so the trigger never fires; audit history points at an anonymized row
instead of a missing one (forensically still valid).

This migration only adds the column + a partial index. The anonymization
logic lives in ``app/routers/admin.py:delete_user`` (added in the same
plan that introduces this migration).

The index is partial (``WHERE deleted_at IS NOT NULL``) because
soft-deleted users are the minority — admin-list filtering wants to skip
them quickly without paying a full B-tree per row.
"""
from alembic import op
import sqlalchemy as sa


revision = "0030_add_user_deleted_at"
down_revision = "0029_apscheduler_disable_rls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_users_deleted_at "
        "ON users (deleted_at) WHERE deleted_at IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_users_deleted_at")
    op.drop_column("users", "deleted_at")
