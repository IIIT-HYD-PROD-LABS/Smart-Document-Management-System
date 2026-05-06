"""Phase 12 — notice response workflow tables.

Adds four tables for the response drafting + multi-stage approval +
evidence linking workflow:

  - notice_responses             current draft pointer + status per notice
  - notice_response_versions     immutable version snapshots of body
  - notice_response_approvals    immutable per-stage approve/reject log
  - notice_evidence_attachments  ComplianceNotice ↔ Document join

Per Phase 12 RESEARCH-FINAL §2: the 4-stage state machine is enforced
server-side (Drafter → Reviewer → Legal → CFO). Approval rows are
append-only (no UPDATE grant on app_runtime mirroring AUDIT-02).

Versions are append-only too: rollback writes a NEW row pointing at the
older content rather than mutating an existing version.

All four tables RLS-scoped per Phase 9 client_id pattern.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0022_phase12_response_workflow"
down_revision = "0021_phase11_alert_tables"
branch_labels = None
depends_on = None


VALID_RESPONSE_STATUSES = (
    "draft",
    "reviewer_pending",
    "legal_pending",
    "cfo_pending",
    "approved",
    "rejected",
    "withdrawn",
)

VALID_APPROVAL_STAGES = (
    "reviewer",
    "legal",
    "cfo",
)

VALID_APPROVAL_DECISIONS = (
    "approved",
    "rejected",
)


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────────
    # 1. notice_responses — one row per notice (UNIQUE notice_id)
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "notice_responses",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "notice_id",
            sa.Integer,
            sa.ForeignKey("compliance_notices.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
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
            "current_version_id",
            sa.Integer,
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"status IN {VALID_RESPONSE_STATUSES!r}".replace("'", "'"),
            name="ck_notice_responses_status",
        ),
    )

    op.execute("ALTER TABLE notice_responses ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notice_responses FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON notice_responses
        FOR ALL
        USING (
            client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
        )
        WITH CHECK (
            client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
        )
        """
    )

    # ──────────────────────────────────────────────────────────────────
    # 2. notice_response_versions — append-only version snapshots
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "notice_response_versions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "response_id",
            sa.Integer,
            sa.ForeignKey("notice_responses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "client_id",
            sa.Integer,
            sa.ForeignKey("compliance_clients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body_markdown", sa.Text, nullable=False, server_default=""),
        sa.Column("recipient", sa.String(500), nullable=True),
        sa.Column("response_date", sa.Date, nullable=True),
        sa.Column("metadata_json", JSONB, nullable=True),
        sa.Column(
            "rolled_back_from_version_id",
            sa.Integer,
            nullable=True,
            comment="If non-null, this version was created by rolling back to that version",
        ),
        sa.Column(
            "created_by_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "response_id", "version_no",
            name="uq_response_versions_no",
        ),
    )

    op.execute("ALTER TABLE notice_response_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notice_response_versions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON notice_response_versions
        FOR ALL
        USING (
            client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
        )
        WITH CHECK (
            client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
        )
        """
    )

    # Now that the table exists, add the FK from notice_responses to it.
    op.create_foreign_key(
        "fk_notice_responses_current_version",
        "notice_responses",
        "notice_response_versions",
        ["current_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ──────────────────────────────────────────────────────────────────
    # 3. notice_response_approvals — append-only per-stage decisions
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "notice_response_approvals",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "response_id",
            sa.Integer,
            sa.ForeignKey("notice_responses.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "version_id",
            sa.Integer,
            sa.ForeignKey("notice_response_versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "client_id",
            sa.Integer,
            sa.ForeignKey("compliance_clients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("stage", sa.String(20), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column(
            "actor_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            f"stage IN {VALID_APPROVAL_STAGES!r}".replace("'", "'"),
            name="ck_response_approvals_stage",
        ),
        sa.CheckConstraint(
            f"decision IN {VALID_APPROVAL_DECISIONS!r}".replace("'", "'"),
            name="ck_response_approvals_decision",
        ),
    )

    op.execute("ALTER TABLE notice_response_approvals ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notice_response_approvals FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON notice_response_approvals
        FOR ALL
        USING (
            client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
        )
        WITH CHECK (
            client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
        )
        """
    )

    # ──────────────────────────────────────────────────────────────────
    # 4. notice_evidence_attachments — ComplianceNotice ↔ Document join
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "notice_evidence_attachments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "notice_id",
            sa.Integer,
            sa.ForeignKey("compliance_notices.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "document_id",
            sa.Integer,
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "client_id",
            sa.Integer,
            sa.ForeignKey("compliance_clients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column(
            "added_by_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "notice_id", "document_id",
            name="uq_evidence_notice_document",
        ),
    )

    op.execute("ALTER TABLE notice_evidence_attachments ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notice_evidence_attachments FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON notice_evidence_attachments
        FOR ALL
        USING (
            client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
        )
        WITH CHECK (
            client_id = NULLIF(current_setting('app.current_client_id', true), '')::integer
        )
        """
    )

    # ──────────────────────────────────────────────────────────────────
    # 5. Grants — append-only on approvals + versions; CRUD on responses + evidence
    # ──────────────────────────────────────────────────────────────────
    op.execute("GRANT SELECT, INSERT, UPDATE ON notice_responses TO app_runtime")
    op.execute("GRANT USAGE, SELECT ON SEQUENCE notice_responses_id_seq TO app_runtime")
    # versions are append-only at app layer; no UPDATE grant
    op.execute("GRANT SELECT, INSERT ON notice_response_versions TO app_runtime")
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE notice_response_versions_id_seq TO app_runtime"
    )
    # approvals are immutable per AUDIT-02 pattern
    op.execute("GRANT SELECT, INSERT ON notice_response_approvals TO app_runtime")
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE notice_response_approvals_id_seq TO app_runtime"
    )
    op.execute("GRANT SELECT, INSERT, DELETE ON notice_evidence_attachments TO app_runtime")
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE notice_evidence_attachments_id_seq TO app_runtime"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notice_evidence_attachments")
    op.drop_table("notice_evidence_attachments")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notice_response_approvals")
    op.drop_table("notice_response_approvals")

    op.drop_constraint(
        "fk_notice_responses_current_version",
        "notice_responses",
        type_="foreignkey",
    )
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notice_response_versions")
    op.drop_table("notice_response_versions")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notice_responses")
    op.drop_table("notice_responses")
