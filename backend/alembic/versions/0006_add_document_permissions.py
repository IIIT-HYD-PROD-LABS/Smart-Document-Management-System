"""Add document_permissions table for document sharing.

Revision ID: 0006
Revises: 0005_add_user_role
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_add_document_permissions"
down_revision = "0005_add_user_role"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_permissions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("permission", sa.String(20), nullable=False, server_default="view"),
        sa.Column("granted_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "user_id", name="uq_document_user_permission"),
    )
    op.create_index("idx_doc_permissions_user", "document_permissions", ["user_id"])
    op.create_index("idx_doc_permissions_document", "document_permissions", ["document_id"])


def downgrade() -> None:
    op.drop_index("idx_doc_permissions_document", table_name="document_permissions")
    op.drop_index("idx_doc_permissions_user", table_name="document_permissions")
    op.drop_table("document_permissions")
