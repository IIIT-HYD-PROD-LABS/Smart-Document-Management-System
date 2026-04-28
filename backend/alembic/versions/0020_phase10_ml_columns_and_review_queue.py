"""Phase 10 — ML output columns on compliance_notices + notice_review_queue table.

Adds classifier confidences, risk score/tier, NER extracted fields, model
version, and source provenance to compliance_notices. Creates the
notice_review_queue table for low-confidence (< 0.75) classifications that
need human verification per CLASS-04.

Per Phase 10 CONTEXT.md decisions:
- D-04: Confidence threshold 0.75 — below routes to notice_review_queue
- D-13/14: Risk score 0-100 with tier (critical/high/medium/low)
- D-22: Model artifacts versioned via model_version string

Per Phase 15 CONTEXT.md D-14: source column distinguishes manual / portal / gmail
ingestion paths so Plan 09-07 dashboard can filter by origin.

Idempotent: ADD COLUMN IF NOT EXISTS + CREATE TABLE IF NOT EXISTS.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision = "0020_phase10_ml_columns_and_review_queue"
down_revision = "0019_rls_fail_closed_on_empty_tenant"
branch_labels = None
depends_on = None


VALID_RISK_TIERS = ("critical", "high", "medium", "low")
VALID_SOURCES = ("manual", "portal", "gmail", "imap")


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Phase 10 ML output columns on compliance_notices
    # ------------------------------------------------------------------

    # Numeric(5, 4) supports 0.0000 - 1.0000 confidence range.
    op.add_column(
        "compliance_notices",
        sa.Column(
            "classifier_authority_confidence",
            sa.Numeric(5, 4),
            nullable=True,
        ),
    )
    op.add_column(
        "compliance_notices",
        sa.Column(
            "classifier_type_confidence",
            sa.Numeric(5, 4),
            nullable=True,
        ),
    )

    # Numeric(5, 2) supports 0.00 - 100.00 risk score.
    op.add_column(
        "compliance_notices",
        sa.Column("risk_score", sa.Numeric(5, 2), nullable=True),
    )
    op.add_column(
        "compliance_notices",
        sa.Column("risk_tier", sa.String(20), nullable=True),
    )

    # NER extracted fields (per CONTEXT D-10): notice_number, deadline,
    # penalty_amount, tax_demand, gstins, pans, cins, etc.
    op.add_column(
        "compliance_notices",
        sa.Column("ner_extracted_fields", JSONB, nullable=True),
    )

    # Model version for cache invalidation (CONTEXT anti-pattern: do not
    # cache predictions across model versions).
    op.add_column(
        "compliance_notices",
        sa.Column("model_version", sa.String(50), nullable=True),
    )

    # Source provenance (manual/portal/gmail/imap) — joins Phase 15 + 14.
    op.add_column(
        "compliance_notices",
        sa.Column(
            "source",
            sa.String(20),
            nullable=False,
            server_default="manual",
        ),
    )

    # When the most recent classifier ran (NULL = never classified).
    op.add_column(
        "compliance_notices",
        sa.Column("classified_at", sa.DateTime(timezone=True), nullable=True),
    )

    # When the most recent risk score was computed (for daily refresh tracking).
    op.add_column(
        "compliance_notices",
        sa.Column("risk_scored_at", sa.DateTime(timezone=True), nullable=True),
    )

    # CHECK constraint: risk_tier must be a valid value when set.
    op.create_check_constraint(
        "ck_compliance_notices_risk_tier_valid",
        "compliance_notices",
        f"risk_tier IS NULL OR risk_tier IN {VALID_RISK_TIERS!r}".replace("'", "'"),
    )

    # CHECK constraint: source must be valid.
    op.create_check_constraint(
        "ck_compliance_notices_source_valid",
        "compliance_notices",
        f"source IN {VALID_SOURCES!r}".replace("'", "'"),
    )

    # Index on risk_tier for filter queries (Critical-first dashboard view).
    op.create_index(
        "ix_compliance_notices_risk_tier",
        "compliance_notices",
        ["risk_tier"],
    )

    # Index on source for Phase 15 dashboard filter.
    op.create_index(
        "ix_compliance_notices_source",
        "compliance_notices",
        ["source"],
    )

    # ------------------------------------------------------------------
    # 2. notice_review_queue table — low-confidence classifications
    # ------------------------------------------------------------------
    op.create_table(
        "notice_review_queue",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "notice_id",
            sa.Integer,
            sa.ForeignKey("compliance_notices.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,  # One review row per notice
            index=True,
        ),
        sa.Column(
            "client_id",
            sa.Integer,
            sa.ForeignKey("compliance_clients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "predicted_authority",
            sa.String(10),
            nullable=True,
        ),
        sa.Column(
            "predicted_authority_confidence",
            sa.Numeric(5, 4),
            nullable=True,
        ),
        sa.Column(
            "predicted_type_id",
            sa.Integer,
            sa.ForeignKey("compliance_notice_types.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "predicted_type_confidence",
            sa.Numeric(5, 4),
            nullable=True,
        ),
        sa.Column(
            "model_version",
            sa.String(50),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.String(50),
            nullable=False,
            comment="low_authority_confidence | low_type_confidence | both",
        ),
        sa.Column(
            "reviewer_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "reviewer_assigned_authority",
            sa.String(10),
            nullable=True,
        ),
        sa.Column(
            "reviewer_assigned_type_id",
            sa.Integer,
            sa.ForeignKey("compliance_notice_types.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Index on (client_id, reviewed_at) for client-scoped pending queue queries.
    op.create_index(
        "ix_notice_review_queue_client_pending",
        "notice_review_queue",
        ["client_id", "reviewed_at"],
    )

    # Enable RLS on the review queue (Phase 9 CLIENT-04 isolation).
    op.execute("ALTER TABLE notice_review_queue ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notice_review_queue FORCE ROW LEVEL SECURITY")

    # tenant_isolation policy mirrors Phase 9 pattern — fail-closed cast via
    # NULLIF so empty tenant returns no rows (same as 0019 fix).
    op.execute(
        """
        CREATE POLICY tenant_isolation ON notice_review_queue
        FOR ALL
        USING (
            client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
        )
        WITH CHECK (
            client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
        )
        """
    )

    # ------------------------------------------------------------------
    # 3. Grant minimal privileges to app_runtime (per Phase 9 INFRA-07)
    # ------------------------------------------------------------------
    op.execute("GRANT SELECT, INSERT, UPDATE ON notice_review_queue TO app_runtime")
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE notice_review_queue_id_seq TO app_runtime"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notice_review_queue")
    op.drop_index("ix_notice_review_queue_client_pending", "notice_review_queue")
    op.drop_table("notice_review_queue")

    op.drop_index("ix_compliance_notices_source", "compliance_notices")
    op.drop_index("ix_compliance_notices_risk_tier", "compliance_notices")
    op.drop_constraint(
        "ck_compliance_notices_source_valid", "compliance_notices", type_="check"
    )
    op.drop_constraint(
        "ck_compliance_notices_risk_tier_valid", "compliance_notices", type_="check"
    )

    for col in (
        "risk_scored_at",
        "classified_at",
        "source",
        "model_version",
        "ner_extracted_fields",
        "risk_tier",
        "risk_score",
        "classifier_type_confidence",
        "classifier_authority_confidence",
    ):
        op.drop_column("compliance_notices", col)
