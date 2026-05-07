"""Phase 15: Gmail MCP integration — credentials, filter rules, fetch log, message log, bills, documents.source_email_id.

Revision ID: 0025_phase15_gmail_mcp
Revises: 0024_supabase_security_advisor_fixes
Create Date: 2026-05-07

Wave 1 DB foundations for Phase 15. Creates 5 new tables + adds
documents.source_email_id FK column. RLS-enabled per Phase 9 Plan 04
pattern (tenant_isolation PERMISSIVE FOR ALL TO app_runtime, plus
cross_client_view PERMISSIVE FOR SELECT for compliance_head/ca_consultant/cfo).

Tables created (in dependency order):
  - gmail_credentials       (scoped by client_id; Fernet-encrypted refresh_token)
  - gmail_filter_rules      (scoped via credential_id; priority column)
  - gmail_message_log       (composite UNIQUE (credential_id, gmail_message_id))
  - gmail_fetch_log         (three-state CHECK on status)
  - bills                   (hybrid model, partial UNIQUE recurrence index)

Plus:
  - documents.source_email_id BIGINT FK -> gmail_message_log.id (nullable, SET NULL)

Portability:
  Supabase-only role grants (anon/authenticated/service_role) wrapped in
  DO $$ IF EXISTS $$ blocks (mirrors 0024). app_runtime is conditional
  too — although Phase 9 migration 0017 creates it, we follow the
  defensive pattern so the migration runs on fresh CI Postgres without
  Phase 9 chain.
"""
from alembic import op
import sqlalchemy as sa


revision = "0025_phase15_gmail_mcp"
down_revision = "0024_supabase_security_advisor_fixes"
branch_labels = None
depends_on = None


# Tables created by this migration. Used in RLS bootstrap loops.
_NEW_TABLES = (
    "gmail_credentials",
    "gmail_filter_rules",
    "gmail_message_log",
    "gmail_fetch_log",
    "bills",
)

# Tables that carry client_id directly (tenant_isolation filters on client_id).
_CLIENT_SCOPED_TABLES = ("gmail_credentials", "bills")

# Tables scoped via credential_id -> gmail_credentials.client_id (subquery RLS).
_CREDENTIAL_SCOPED_TABLES = (
    "gmail_filter_rules",
    "gmail_message_log",
    "gmail_fetch_log",
)


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────────
    # 1. gmail_credentials
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "gmail_credentials",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "client_id",
            sa.Integer,
            sa.ForeignKey("compliance_clients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("google_account_email", sa.String(254), nullable=True),
        sa.Column("refresh_token_enc", sa.LargeBinary, nullable=False),
        sa.Column("scopes", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_history_id", sa.String(64), nullable=True),
        sa.Column(
            "cadence_minutes",
            sa.Integer,
            nullable=False,
            server_default="15",
        ),
        sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint(
            "user_id",
            "client_id",
            name="uq_gmail_credentials_user_client",
        ),
        sa.CheckConstraint(
            "status IN ('active','revoked','disabled')",
            name="ck_gmail_credentials_status",
        ),
        sa.CheckConstraint(
            "cadence_minutes BETWEEN 5 AND 1440",
            name="ck_gmail_credentials_cadence",
        ),
    )

    # ──────────────────────────────────────────────────────────────────
    # 2. gmail_filter_rules
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "gmail_filter_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "credential_id",
            sa.Integer,
            sa.ForeignKey("gmail_credentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Integer,
            nullable=False,
            server_default="100",
        ),
        sa.Column("sender_pattern", sa.String(255), nullable=True),
        sa.Column("subject_pattern", sa.String(255), nullable=True),
        sa.Column("label_include", sa.String(255), nullable=True),
        sa.Column("label_exclude", sa.String(255), nullable=True),
        sa.Column("route_to", sa.String(20), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "route_to IN ('compliance_notice','bill','dms_only','ignore')",
            name="ck_gmail_filter_rules_route_to",
        ),
    )
    op.create_index(
        "ix_gmail_filter_rules_credential_priority",
        "gmail_filter_rules",
        ["credential_id", "priority"],
    )

    # ──────────────────────────────────────────────────────────────────
    # 3. gmail_message_log
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "gmail_message_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "credential_id",
            sa.Integer,
            sa.ForeignKey("gmail_credentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gmail_message_id", sa.String(255), nullable=False),
        sa.Column("gmail_thread_id", sa.String(255), nullable=True),
        sa.Column("sender_domain", sa.String(254), nullable=True),
        sa.Column("body_sha256", sa.String(64), nullable=True),
        sa.Column("route_taken", sa.String(20), nullable=False),
        sa.Column(
            "processed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "credential_id",
            "gmail_message_id",
            name="uq_gmail_message_log_dedup",
        ),
        sa.CheckConstraint(
            "route_taken IN ('compliance_notice','bill','dms_only','ignore')",
            name="ck_gmail_message_log_route_taken",
        ),
    )

    # ──────────────────────────────────────────────────────────────────
    # 4. gmail_fetch_log
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "gmail_fetch_log",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "credential_id",
            sa.Integer,
            sa.ForeignKey("gmail_credentials.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column(
            "messages_processed",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('SUCCESS_EMPTY','SUCCESS_WITH_RESULTS','FETCH_FAILED')",
            name="ck_gmail_fetch_log_status",
        ),
    )
    op.create_index(
        "ix_gmail_fetch_log_credential_started",
        "gmail_fetch_log",
        ["credential_id", sa.text("started_at DESC")],
    )

    # ──────────────────────────────────────────────────────────────────
    # 5. bills (D-19 hybrid model: source_document_id nullable for
    #            text-only bills with no PDF attachment)
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "bills",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "client_id",
            sa.Integer,
            sa.ForeignKey("compliance_clients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("biller_name", sa.String(255), nullable=False),
        sa.Column(
            "biller_name_normalized",
            sa.String(255),
            nullable=False,
            index=True,
        ),
        sa.Column("biller_category", sa.String(30), nullable=False),
        sa.Column("amount_due", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "currency",
            sa.String(3),
            nullable=False,
            server_default="INR",
        ),
        sa.Column("due_date", sa.Date, nullable=True),
        sa.Column("account_number_last4", sa.String(4), nullable=True),
        sa.Column(
            "payment_status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "is_recurring",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("recurrence_period", sa.String(20), nullable=True),
        sa.Column(
            "parent_bill_id",
            sa.Integer,
            sa.ForeignKey("bills.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_document_id",
            sa.Integer,
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_email_id",
            sa.BigInteger,
            sa.ForeignKey("gmail_message_log.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("payment_date", sa.Date, nullable=True),
        sa.Column("payment_reference", sa.String(255), nullable=True),
        sa.Column("payment_method", sa.String(20), nullable=True),
        sa.Column("extraction_prompt_rev", sa.String(20), nullable=True),
        sa.Column(
            "reminder_count",
            sa.Integer,
            nullable=False,
            server_default="0",
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
            "biller_category IN ('utility','telecom','credit_card','subscription','other')",
            name="ck_bills_biller_category",
        ),
        sa.CheckConstraint(
            "payment_status IN ('pending','paid','overdue')",
            name="ck_bills_payment_status",
        ),
        sa.CheckConstraint(
            "recurrence_period IS NULL OR recurrence_period IN ('monthly','quarterly','annual')",
            name="ck_bills_recurrence_period",
        ),
        sa.CheckConstraint(
            "payment_method IS NULL OR payment_method IN "
            "('upi','netbanking','card','cash','cheque','autopay','other')",
            name="ck_bills_payment_method",
        ),
    )
    # Partial UNIQUE index per Pitfall 8 — recurrence dedup only when
    # account_number_last4 is known. Bills without last4 may legitimately
    # collide on (client, biller_name_normalized).
    op.create_index(
        "ux_bills_recurrence_key",
        "bills",
        ["client_id", "biller_name_normalized", "account_number_last4"],
        unique=True,
        postgresql_where=sa.text("account_number_last4 IS NOT NULL"),
    )

    # ──────────────────────────────────────────────────────────────────
    # 6. documents.source_email_id (FK to gmail_message_log) — added AFTER
    #    gmail_message_log exists so the FK can be inline
    # ──────────────────────────────────────────────────────────────────
    op.add_column(
        "documents",
        sa.Column(
            "source_email_id",
            sa.BigInteger,
            sa.ForeignKey("gmail_message_log.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_documents_source_email_id",
        "documents",
        ["source_email_id"],
    )

    # ──────────────────────────────────────────────────────────────────
    # 7. RLS bootstrap — enable + force on all 5 new tables, then create
    #    tenant_isolation + cross_client_view policies. Wrapped in DO
    #    blocks where app_runtime is referenced so the migration runs on
    #    fresh Postgres without the Phase 9 role chain.
    # ──────────────────────────────────────────────────────────────────
    for tbl in _NEW_TABLES:
        op.execute(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY;")

    # Client-id-scoped tables: direct USING / WITH CHECK on client_id.
    for tbl in _CLIENT_SCOPED_TABLES:
        op.execute(f"""
        DO $do$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
                EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {tbl}';
                EXECUTE $policy$
                CREATE POLICY tenant_isolation ON {tbl}
                AS PERMISSIVE FOR ALL TO app_runtime
                USING (
                    client_id = NULLIF(current_setting('app.current_client_id', true), '')::int
                )
                WITH CHECK (
                    client_id = NULLIF(current_setting('app.current_client_id', true), '')::int
                )
                $policy$;
            END IF;
        END $do$;
        """)

    # Credential-scoped tables: filter via gmail_credentials.client_id subquery.
    for tbl in _CREDENTIAL_SCOPED_TABLES:
        op.execute(f"""
        DO $do$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
                EXECUTE 'DROP POLICY IF EXISTS tenant_isolation ON {tbl}';
                EXECUTE $policy$
                CREATE POLICY tenant_isolation ON {tbl}
                AS PERMISSIVE FOR ALL TO app_runtime
                USING (
                    credential_id IN (
                        SELECT id FROM gmail_credentials
                        WHERE client_id = NULLIF(current_setting('app.current_client_id', true), '')::int
                    )
                )
                WITH CHECK (
                    credential_id IN (
                        SELECT id FROM gmail_credentials
                        WHERE client_id = NULLIF(current_setting('app.current_client_id', true), '')::int
                    )
                )
                $policy$;
            END IF;
        END $do$;
        """)

    # cross_client_view: PERMISSIVE FOR SELECT TO app_runtime when caller
    # is in cross_client_mode AND eligible role (compliance_head, ca_consultant,
    # cfo). is_cross_client_eligible() created in Phase 9 migration 0018.
    for tbl in _NEW_TABLES:
        op.execute(f"""
        DO $do$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime')
               AND EXISTS (
                   SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
                   WHERE n.nspname = 'public' AND p.proname = 'is_cross_client_eligible'
               ) THEN
                EXECUTE 'DROP POLICY IF EXISTS cross_client_view ON {tbl}';
                EXECUTE $policy$
                CREATE POLICY cross_client_view ON {tbl}
                AS PERMISSIVE FOR SELECT TO app_runtime
                USING (
                    current_setting('app.cross_client_mode', true) = 'true'
                    AND current_setting('app.user_id', true) IS NOT NULL
                    AND current_setting('app.user_id', true) != ''
                    AND is_cross_client_eligible(
                        current_setting('app.user_id', true)::int
                    )
                )
                $policy$;
            END IF;
        END $do$;
        """)

    # ──────────────────────────────────────────────────────────────────
    # 8. Grants — wrapped in DO blocks for portability
    # ──────────────────────────────────────────────────────────────────
    for tbl in _NEW_TABLES:
        op.execute(f"""
        DO $do$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_runtime') THEN
                EXECUTE 'GRANT SELECT, INSERT, UPDATE, DELETE ON {tbl} TO app_runtime';
                EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE {tbl}_id_seq TO app_runtime';
            END IF;
        END $do$;
        """)


def downgrade() -> None:
    # Reverse order: drop policies, disable RLS, drop FK column on
    # documents, drop tables in dependency-reverse order.

    # 1. Drop cross_client_view + tenant_isolation on all tables
    for tbl in _NEW_TABLES:
        op.execute(f"DROP POLICY IF EXISTS cross_client_view ON {tbl};")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {tbl};")

    # 2. Disable RLS on all tables
    for tbl in _NEW_TABLES:
        op.execute(f"ALTER TABLE {tbl} DISABLE ROW LEVEL SECURITY;")

    # 3. Drop documents.source_email_id (index first, then column)
    op.drop_index("ix_documents_source_email_id", "documents")
    op.drop_column("documents", "source_email_id")

    # 4. Drop tables in reverse dependency order
    op.drop_index("ux_bills_recurrence_key", "bills")
    op.drop_table("bills")
    op.drop_index("ix_gmail_fetch_log_credential_started", "gmail_fetch_log")
    op.drop_table("gmail_fetch_log")
    op.drop_table("gmail_message_log")
    op.drop_index(
        "ix_gmail_filter_rules_credential_priority", "gmail_filter_rules"
    )
    op.drop_table("gmail_filter_rules")
    op.drop_table("gmail_credentials")
