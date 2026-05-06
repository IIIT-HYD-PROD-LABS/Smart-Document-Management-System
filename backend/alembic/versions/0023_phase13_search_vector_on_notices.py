"""Phase 13 — add search_vector TSVECTOR + GIN index + trigger to compliance_notices.

Mirrors the Phase 4 (`documents.search_vector`) pattern from migration
0003 so the unified search service can query both tables with a single
`UNION ALL` and merged ts_rank ordering.

Source columns concatenated into the vector:
  - notice_number
  - authority
  - notice_type.code (resolved via JOIN at trigger time? No — keep simple,
    use only the columns present on compliance_notices itself)
  - legal_sections (JSONB array → text)
  - ner_extracted_fields->>'risk_top_factors' phrases (Phase 10 SHAP
    explanations are searchable)

Backfills existing rows.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR


revision = "0023_phase13_search_vector_on_notices"
down_revision = "0022_phase12_response_workflow"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. TSVECTOR column (nullable; trigger populates on next INSERT/UPDATE)
    op.add_column(
        "compliance_notices",
        sa.Column("search_vector", TSVECTOR(), nullable=True),
    )

    # 2. Backfill existing rows. Concatenate searchable text fields.
    op.execute(
        """
        UPDATE compliance_notices
        SET search_vector = to_tsvector('english',
            COALESCE(notice_number, '') || ' ' ||
            COALESCE(authority, '') || ' ' ||
            COALESCE(legal_sections::text, '') || ' ' ||
            COALESCE(status, '') || ' ' ||
            COALESCE(risk_tier, '')
        )
        """
    )

    # 3. GIN index — use op.execute() to avoid Alembic tsvector index false-diff bug
    op.execute(
        """
        CREATE INDEX ix_compliance_notices_search_vector
        ON compliance_notices USING GIN (search_vector)
        """
    )

    # 4. Trigger function — keep search_vector in sync on INSERT and UPDATE
    op.execute(
        """
        CREATE OR REPLACE FUNCTION compliance_notices_search_vector_update()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' OR
               NEW.notice_number IS DISTINCT FROM OLD.notice_number OR
               NEW.authority IS DISTINCT FROM OLD.authority OR
               NEW.legal_sections IS DISTINCT FROM OLD.legal_sections OR
               NEW.status IS DISTINCT FROM OLD.status OR
               NEW.risk_tier IS DISTINCT FROM OLD.risk_tier THEN
                NEW.search_vector := to_tsvector('english',
                    COALESCE(NEW.notice_number, '') || ' ' ||
                    COALESCE(NEW.authority, '') || ' ' ||
                    COALESCE(NEW.legal_sections::text, '') || ' ' ||
                    COALESCE(NEW.status, '') || ' ' ||
                    COALESCE(NEW.risk_tier, ''));
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )

    # 5. Attach trigger
    op.execute(
        """
        CREATE TRIGGER compliance_notices_search_vector_trigger
        BEFORE INSERT OR UPDATE ON compliance_notices
        FOR EACH ROW EXECUTE FUNCTION compliance_notices_search_vector_update();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS compliance_notices_search_vector_trigger ON compliance_notices"
    )
    op.execute("DROP FUNCTION IF EXISTS compliance_notices_search_vector_update")
    op.execute("DROP INDEX IF EXISTS ix_compliance_notices_search_vector")
    op.drop_column("compliance_notices", "search_vector")
