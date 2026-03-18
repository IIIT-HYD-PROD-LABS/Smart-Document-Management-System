"""Add user role column.

Revision ID: 0005
Revises: 0004_add_ai_extraction_fields
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_add_user_role"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("role", sa.String(20), server_default="editor", nullable=False),
    )
    op.create_index("idx_users_role", "users", ["role"])
    op.execute(
        "UPDATE users SET role = 'admin' WHERE id = (SELECT MIN(id) FROM users)"
    )


def downgrade() -> None:
    op.drop_index("idx_users_role", table_name="users")
    op.drop_column("users", "role")
