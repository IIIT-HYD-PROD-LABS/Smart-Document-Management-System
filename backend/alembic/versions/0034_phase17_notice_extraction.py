"""Phase 17 — AI notice field extraction artefact columns.

Revision ID: 0034_phase17_notice_extraction
Revises: 0033_ai_credentials_rls
Create Date: 2026-05-22

Adds five additive columns to compliance_notices to hold the LLM-based
field-extraction artefact (Phase 17, D-10):

    * extracted_fields        jsonb        envelope per D-03
    * extraction_confidence   numeric(3,2) post-validation D-06 average
    * extracted_by_provider   text         "anthropic:claude-sonnet-..." etc.
    * extracted_at            timestamptz  when the extractor ran
    * extraction_status       text         pending|completed|failed|accepted|superseded

Why a NEW column and not reuse of ner_extracted_fields:
    ner_extracted_fields (added in Phase 10) stores regex hits + SHAP risk
    top factors with the shape {notice_number, dates, amounts, risk_top_factors}.
    Phase 17's artefact is the D-03 envelope shape
    {fields: {<field>: {value, confidence, source_span}}, average_confidence,
    model, tokens_in, tokens_out, latency_ms}. Cohabiting two shapes in one
    column would force every reader to branch on a discriminator. See
    .planning/phases/17-ai-notice-extraction/17-CONTEXT.md D-10a.

Why no RLS bootstrap:
    compliance_notices is already RLS-enabled (migration 0017) and FORCED
    (0018). Adding columns inherits both the tenant_isolation and
    cross_client_view policies automatically. No new GRANT needed.

Idempotency:
    All adds use IF NOT EXISTS guards so the migration is safe to re-run.
"""
from alembic import op


revision = "0034_phase17_notice_extraction"
down_revision = "0033_ai_credentials_rls"
branch_labels = None
depends_on = None


_ALLOWED_STATUSES = ("pending", "completed", "failed", "accepted", "superseded")


def upgrade() -> None:
    op.execute(
        "ALTER TABLE compliance_notices "
        "ADD COLUMN IF NOT EXISTS extracted_fields jsonb"
    )
    op.execute(
        "ALTER TABLE compliance_notices "
        "ADD COLUMN IF NOT EXISTS extraction_confidence numeric(3,2)"
    )
    op.execute(
        "ALTER TABLE compliance_notices "
        "ADD COLUMN IF NOT EXISTS extracted_by_provider text"
    )
    op.execute(
        "ALTER TABLE compliance_notices "
        "ADD COLUMN IF NOT EXISTS extracted_at timestamptz"
    )
    op.execute(
        "ALTER TABLE compliance_notices "
        "ADD COLUMN IF NOT EXISTS extraction_status text"
    )

    statuses_sql = ", ".join(f"'{s}'" for s in _ALLOWED_STATUSES)
    op.execute(
        "ALTER TABLE compliance_notices "
        "DROP CONSTRAINT IF EXISTS ck_compliance_notices_extraction_status"
    )
    op.execute(
        "ALTER TABLE compliance_notices "
        "ADD CONSTRAINT ck_compliance_notices_extraction_status "
        "CHECK (extraction_status IS NULL OR extraction_status IN "
        f"({statuses_sql}))"
    )

    # Constrain confidence to [0, 1] inclusive. Cheap CHECK; catches a
    # whole class of bugs where the extractor mistakenly returns a 0-100
    # scale.
    op.execute(
        "ALTER TABLE compliance_notices "
        "DROP CONSTRAINT IF EXISTS ck_compliance_notices_extraction_confidence"
    )
    op.execute(
        "ALTER TABLE compliance_notices "
        "ADD CONSTRAINT ck_compliance_notices_extraction_confidence "
        "CHECK (extraction_confidence IS NULL OR "
        "(extraction_confidence >= 0 AND extraction_confidence <= 1))"
    )

    # Index for the review-queue UI's "show me notices needing review by
    # extraction status" filter. Partial because the vast majority of
    # rows will end up at 'accepted' or NULL, leaving 'pending' /
    # 'failed' as the small working set worth indexing.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_compliance_notices_extraction_status "
        "ON compliance_notices (extraction_status) "
        "WHERE extraction_status IN ('pending', 'failed')"
    )


def downgrade() -> None:
    op.execute(
        "DROP INDEX IF EXISTS ix_compliance_notices_extraction_status"
    )
    op.execute(
        "ALTER TABLE compliance_notices "
        "DROP CONSTRAINT IF EXISTS ck_compliance_notices_extraction_confidence"
    )
    op.execute(
        "ALTER TABLE compliance_notices "
        "DROP CONSTRAINT IF EXISTS ck_compliance_notices_extraction_status"
    )
    op.execute("ALTER TABLE compliance_notices DROP COLUMN IF EXISTS extraction_status")
    op.execute("ALTER TABLE compliance_notices DROP COLUMN IF EXISTS extracted_at")
    op.execute("ALTER TABLE compliance_notices DROP COLUMN IF EXISTS extracted_by_provider")
    op.execute("ALTER TABLE compliance_notices DROP COLUMN IF EXISTS extraction_confidence")
    op.execute("ALTER TABLE compliance_notices DROP COLUMN IF EXISTS extracted_fields")
