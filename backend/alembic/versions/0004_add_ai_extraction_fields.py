"""Add AI extraction columns to documents and user_llm_settings table.

Revision ID: 0004_add_ai_extraction_fields
Revises: 0003_add_fts_and_trgm
Create Date: 2026-03-17

Adds to the documents table:
- ai_summary (Text, nullable) -- AI-generated one-paragraph summary
- ai_extracted_data (JSON, nullable) -- structured extraction from LLM
- extraction_status (String(50), nullable) -- pending/processing/completed/failed/None

Creates the user_llm_settings table:
- id (PK), user_id (FK unique), llm_provider, api_key_encrypted, model_name,
  ollama_base_url, created_at, updated_at
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004_add_ai_extraction_fields"
down_revision: Union[str, None] = "0003_add_fts_and_trgm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add AI extraction columns to documents table
    op.add_column("documents", sa.Column("ai_summary", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("ai_extracted_data", sa.JSON(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("extraction_status", sa.String(50), nullable=True),
    )

    # 2. Create user_llm_settings table
    op.create_table(
        "user_llm_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("llm_provider", sa.String(50), nullable=False, server_default="gemini"),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(100), nullable=True),
        sa.Column("ollama_base_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )

    # 3. Unique constraint on user_id (use op.execute to keep consistent with project pattern)
    op.execute("""
        CREATE UNIQUE INDEX uq_user_llm_settings_user_id
        ON user_llm_settings (user_id)
    """)

    # 4. Index on user_id for FK lookups
    op.execute("""
        CREATE INDEX ix_user_llm_settings_id
        ON user_llm_settings (id)
    """)


def downgrade() -> None:
    # Remove in reverse order
    op.execute("DROP INDEX IF EXISTS ix_user_llm_settings_id")
    op.execute("DROP INDEX IF EXISTS uq_user_llm_settings_user_id")
    op.drop_table("user_llm_settings")
    op.drop_column("documents", "extraction_status")
    op.drop_column("documents", "ai_extracted_data")
    op.drop_column("documents", "ai_summary")
