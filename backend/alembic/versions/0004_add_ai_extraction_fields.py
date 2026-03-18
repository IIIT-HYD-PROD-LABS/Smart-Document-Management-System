"""Add AI/LLM extraction fields to documents.

Revision ID: 0004
Revises: 0003_add_fts_and_trgm
Create Date: 2026-03-18

Adds columns for Phase 5 LLM Smart Extraction:
- ai_summary: one-paragraph AI-generated summary
- ai_extracted_fields: structured JSON of extracted fields with confidence scores
- ai_extraction_status: pending, completed, failed, skipped
- ai_provider: which LLM provider generated the extraction
- ai_error: error message if extraction failed
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003_add_fts_and_trgm"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("ai_summary", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("ai_extracted_fields", sa.JSON(), nullable=True))
    op.add_column("documents", sa.Column("ai_extraction_status", sa.String(20), nullable=True))
    op.add_column("documents", sa.Column("ai_provider", sa.String(50), nullable=True))
    op.add_column("documents", sa.Column("ai_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "ai_error")
    op.drop_column("documents", "ai_provider")
    op.drop_column("documents", "ai_extraction_status")
    op.drop_column("documents", "ai_extracted_fields")
    op.drop_column("documents", "ai_summary")
