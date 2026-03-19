"""Add highlighted_text column to documents table.

Revision ID: 0008_add_highlighted_text
Revises: 0007_add_oauth_fields
Create Date: 2026-03-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_add_highlighted_text"
down_revision = "0007_add_oauth_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("highlighted_text", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "highlighted_text")
