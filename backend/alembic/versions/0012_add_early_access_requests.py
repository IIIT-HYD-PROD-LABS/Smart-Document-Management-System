"""Add early_access_requests table.

Revision ID: 0007_add_early_access_requests
Revises: 0006_add_document_permissions
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa

revision = "0012_add_early_access_requests"
down_revision = "0011_fix_datetime_timezone"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "early_access_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("company", sa.String(200), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("invitation_token", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_early_access_requests_id", "early_access_requests", ["id"])
    op.create_index("ix_early_access_requests_email", "early_access_requests", ["email"])
    op.create_index("ix_early_access_requests_status", "early_access_requests", ["status"])
    op.create_index("ix_early_access_email_status", "early_access_requests", ["email", "status"])


def downgrade() -> None:
    op.drop_index("ix_early_access_email_status", table_name="early_access_requests")
    op.drop_index("ix_early_access_requests_status", table_name="early_access_requests")
    op.drop_index("ix_early_access_requests_email", table_name="early_access_requests")
    op.drop_index("ix_early_access_requests_id", table_name="early_access_requests")
    op.drop_table("early_access_requests")
