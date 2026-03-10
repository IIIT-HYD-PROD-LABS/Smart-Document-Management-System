"""Add full-text search vector column, GIN indexes, trigger, and pg_trgm extension.

Revision ID: 0003_add_fts_and_trgm
Revises: 0002
Create Date: 2026-03-11

Adds to the documents table:
- pg_trgm extension (for fuzzy/trigram search)
- search_vector TSVECTOR column (stored, populated by trigger)
- idx_documents_search_vector GIN index on search_vector (for FTS)
- idx_documents_trgm GIN index on extracted_text with gin_trgm_ops (for fuzzy matching)
- documents_search_vector_trigger BEFORE INSERT OR UPDATE trigger

Backfills search_vector for all existing completed documents.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR


# revision identifiers, used by Alembic.
revision: str = "0003_add_fts_and_trgm"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # 1. Enable pg_trgm extension (cluster-scoped; IF NOT EXISTS is safe on re-run)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # 2. Add stored tsvector column (nullable: trigger populates on next INSERT/UPDATE)
    op.add_column("documents", sa.Column("search_vector", TSVECTOR(), nullable=True))

    # 3. Backfill existing completed documents
    op.execute("""
        UPDATE documents
        SET search_vector = to_tsvector('english',
            COALESCE(extracted_text, '') || ' ' || COALESCE(original_filename, ''))
        WHERE status = 'completed'
    """)

    # 4. GIN index for FTS — use op.execute() to avoid Alembic tsvector index false-diff bug (issue #1390)
    op.execute("""
        CREATE INDEX idx_documents_search_vector
        ON documents USING GIN (search_vector)
    """)

    # 5. GIN trigram index on extracted_text for fuzzy/typo matching
    op.execute("""
        CREATE INDEX idx_documents_trgm
        ON documents USING GIN (extracted_text gin_trgm_ops)
    """)

    # 6. Trigger function: keeps search_vector in sync on INSERT and UPDATE
    op.execute("""
        CREATE OR REPLACE FUNCTION documents_search_vector_update()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' OR
               NEW.extracted_text IS DISTINCT FROM OLD.extracted_text OR
               NEW.original_filename IS DISTINCT FROM OLD.original_filename THEN
                NEW.search_vector := to_tsvector('english',
                    COALESCE(NEW.extracted_text, '') || ' ' ||
                    COALESCE(NEW.original_filename, ''));
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # 7. Attach trigger to table
    op.execute("""
        CREATE TRIGGER documents_search_vector_trigger
        BEFORE INSERT OR UPDATE ON documents
        FOR EACH ROW EXECUTE FUNCTION documents_search_vector_update();
    """)


def downgrade() -> None:
    # Remove in reverse order: trigger -> function -> indexes -> column -> extension
    op.execute("DROP TRIGGER IF EXISTS documents_search_vector_trigger ON documents")
    op.execute("DROP FUNCTION IF EXISTS documents_search_vector_update")
    op.execute("DROP INDEX IF EXISTS idx_documents_trgm")
    op.execute("DROP INDEX IF EXISTS idx_documents_search_vector")
    op.drop_column("documents", "search_vector")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
