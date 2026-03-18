"""Add OAuth fields to users table.

Revision ID: 0007
Revises: 0006_add_document_permissions
Create Date: 2026-03-18
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_add_oauth_fields"
down_revision = "0006_add_document_permissions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add auth_provider column
    op.add_column(
        "users",
        sa.Column("auth_provider", sa.String(20), server_default="local", nullable=False),
    )
    # Add oauth_id column (unique, nullable for local auth users)
    op.add_column(
        "users",
        sa.Column("oauth_id", sa.String(255), nullable=True),
    )
    op.create_index("idx_users_oauth_id", "users", ["oauth_id"], unique=True)

    # Make hashed_password nullable (OAuth users don't have passwords)
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(255),
        nullable=True,
    )


def downgrade() -> None:
    # Set placeholder password for OAuth users before making column NOT NULL
    op.execute("UPDATE users SET hashed_password = 'OAUTH_ACCOUNT_NO_PASSWORD' WHERE hashed_password IS NULL")
    # Make hashed_password non-nullable again
    op.alter_column(
        "users",
        "hashed_password",
        existing_type=sa.String(255),
        nullable=False,
    )
    op.drop_index("idx_users_oauth_id", table_name="users")
    op.drop_column("users", "oauth_id")
    op.drop_column("users", "auth_provider")
