"""Add MFA (TOTP) + per-account lockout columns to users.

Revision ID: 0036_add_mfa_and_lockout_columns
Revises: 0035_cross_client_view_on_notice_tables
Create Date: 2026-05-26

Additive only: six nullable/defaulted columns on the existing ``users`` table.
``users`` is a non-RLS table and migration 0017 already granted ``app_runtime``
full CRUD on it, so the new columns inherit those grants. No GRANT or RLS
policy change is needed (contrast 0033, which had to grant a brand-new table).

  mfa_enabled          BOOLEAN NOT NULL DEFAULT false
  totp_secret_enc      BYTEA   (Fernet-encrypted base32 TOTP shared secret)
  mfa_backup_codes_enc BYTEA   (Fernet-encrypted JSON list of SHA-256 backup-code hashes)
  mfa_enrolled_at      TIMESTAMPTZ
  failed_login_count   INTEGER NOT NULL DEFAULT 0
  locked_until         TIMESTAMPTZ (account brute-force lock expiry)

server_default on the two NOT NULL columns backfills existing rows in the same
statement, so the migration is safe to run against a populated users table.
"""
from alembic import op
import sqlalchemy as sa


revision = "0036_add_mfa_and_lockout_columns"
down_revision = "0035_cross_client_view_on_notice_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("users", sa.Column("totp_secret_enc", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("mfa_backup_codes_enc", sa.LargeBinary(), nullable=True))
    op.add_column("users", sa.Column("mfa_enrolled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "locked_until")
    op.drop_column("users", "failed_login_count")
    op.drop_column("users", "mfa_enrolled_at")
    op.drop_column("users", "mfa_backup_codes_enc")
    op.drop_column("users", "totp_secret_enc")
    op.drop_column("users", "mfa_enabled")
