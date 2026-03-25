"""Add audit_logs table.

Revision ID: 0010_add_audit_logs
Revises: 0009_add_document_versions
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_add_audit_logs"
down_revision = "0009_add_document_versions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.Integer(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_user_id", "audit_logs", ["user_id"])
    op.create_index("idx_audit_action", "audit_logs", ["action"])
    op.create_index("idx_audit_created_at", "audit_logs", ["created_at"])
    op.create_index("idx_audit_action_created", "audit_logs", ["action", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_audit_action_created", table_name="audit_logs")
    op.drop_index("idx_audit_created_at", table_name="audit_logs")
    op.drop_index("idx_audit_action", table_name="audit_logs")
    op.drop_index("idx_audit_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
