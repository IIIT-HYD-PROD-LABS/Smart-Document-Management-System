"""Compliance foundation schema — Phase 9.

Revision ID: 0013_compliance_foundation_schema
Revises: 0012_add_early_access_requests
Create Date: 2026-04-27

Creates the 8 compliance tables that constitute the Phase 9 data spine:
    1. compliance_clients
    2. compliance_client_registrations (multi-GSTIN per client)
    3. compliance_client_memberships (m2m users<->clients with compliance_role)
    4. compliance_notice_types (lookup, authority+code unique)
    5. compliance_notices (the heart of LIFE-01..08)
    6. compliance_notice_activity (user-facing activity timeline)
    7. compliance_notice_tags (custom labels)
    8. compliance_regulatory_calendar (INFRA-05 — 2026 holidays + filing deadlines)

Adds notice_id FK to existing documents table for upload linking (D-10).
Adds JSONB GIN index on compliance_clients.config_overrides (CLIENT-06).

Per CONTEXT D-13/D-15/D-25: status, authority, type, compliance_role are
String columns with CHECK constraints (not Postgres ENUM types) — matches
v1.0 convention and avoids Postgres ENUM migration friction.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0013_compliance_foundation_schema"
down_revision = "0012_add_early_access_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------------------------------------------
    # 1) compliance_clients
    # -----------------------------------------------------------------
    op.create_table("compliance_clients",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("client_type", sa.String(30), nullable=False),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("primary_contact_email", sa.String(255), nullable=True),
        sa.Column(
            "config_overrides",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_clients_name", "compliance_clients", ["name"]
    )
    op.execute("""
        CREATE INDEX ix_clients_config_overrides_gin
        ON compliance_clients USING gin (config_overrides jsonb_path_ops);
    """)

    # -----------------------------------------------------------------
    # 2) compliance_regulatory_calendar
    #     (created early so Task 5 can INSERT into it; no FK dependency)
    # -----------------------------------------------------------------
    op.create_table("compliance_regulatory_calendar",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("authority", sa.String(10), nullable=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("reference_url", sa.String(1000), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "year BETWEEN 2020 AND 2050",
            name="ck_regulatory_calendar_year_range",
        ),
        sa.CheckConstraint(
            "category IN ('holiday','filing_deadline','circular_extension')",
            name="ck_regulatory_calendar_category",
        ),
        sa.CheckConstraint(
            "authority IS NULL OR authority IN ('GST','IT','MCA','RBI','SEBI')",
            name="ck_regulatory_calendar_authority",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_regulatory_calendar_year_date",
        "compliance_regulatory_calendar",
        ["year", "date"],
    )

    # -----------------------------------------------------------------
    # 3) compliance_client_registrations
    # -----------------------------------------------------------------
    op.create_table("compliance_client_registrations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("value", sa.String(30), nullable=False),
        sa.Column("state", sa.String(5), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["client_id"], ["compliance_clients.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "type IN ('GSTIN','PAN','CIN','DIN')",
            name="ck_client_registration_type",
        ),
        sa.UniqueConstraint(
            "client_id", "type", "value", name="uq_client_registration_value"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_client_registrations_client_id",
        "compliance_client_registrations",
        ["client_id"],
    )

    # -----------------------------------------------------------------
    # 4) compliance_client_memberships
    # -----------------------------------------------------------------
    op.create_table("compliance_client_memberships",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("compliance_role", sa.String(30), nullable=False),
        sa.Column("access_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["client_id"], ["compliance_clients.id"], ondelete="CASCADE"
        ),
        sa.CheckConstraint(
            "compliance_role IN ("
            "'compliance_head','legal_team','finance_team',"
            "'auditor','ca_consultant','staff','cfo')",
            name="ck_client_membership_role",
        ),
        sa.UniqueConstraint(
            "user_id", "client_id", name="uq_client_membership_user_client"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_client_memberships_user_id",
        "compliance_client_memberships",
        ["user_id"],
    )
    op.create_index(
        "ix_compliance_client_memberships_client_id",
        "compliance_client_memberships",
        ["client_id"],
    )

    # -----------------------------------------------------------------
    # 5) compliance_notice_types
    # -----------------------------------------------------------------
    op.create_table("compliance_notice_types",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("authority", sa.String(10), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.CheckConstraint(
            "authority IN ('GST','IT','MCA','RBI','SEBI')",
            name="ck_notice_type_authority",
        ),
        sa.UniqueConstraint(
            "authority", "code", name="uq_notice_type_authority_code"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # -----------------------------------------------------------------
    # 6) compliance_notices
    # -----------------------------------------------------------------
    op.create_table("compliance_notices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("client_id", sa.Integer(), nullable=False),
        sa.Column("notice_type_id", sa.Integer(), nullable=True),
        sa.Column("registration_id", sa.Integer(), nullable=True),
        sa.Column("parent_notice_id", sa.Integer(), nullable=True),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("notice_number", sa.String(100), nullable=False),
        sa.Column("authority", sa.String(10), nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default=sa.text("'received'"),
        ),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column("response_deadline", sa.Date(), nullable=True),
        sa.Column("hearing_date", sa.Date(), nullable=True),
        sa.Column("compliance_date", sa.Date(), nullable=True),
        sa.Column("appeal_deadline", sa.Date(), nullable=True),
        sa.Column("tax_demand", sa.Numeric(18, 2), nullable=True),
        sa.Column("interest", sa.Numeric(18, 2), nullable=True),
        sa.Column("penalty", sa.Numeric(18, 2), nullable=True),
        sa.Column("total_liability", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "legal_sections",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("assigned_user_id", sa.Integer(), nullable=True),
        sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["client_id"], ["compliance_clients.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["notice_type_id"],
            ["compliance_notice_types.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["registration_id"],
            ["compliance_client_registrations.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["parent_notice_id"],
            ["compliance_notices.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["assigned_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "authority IN ('GST','IT','MCA','RBI','SEBI')",
            name="ck_notice_authority",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'received','under_review','response_drafted',"
            "'submitted','resolved','dismissed')",
            name="ck_notice_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_notices_client_status",
        "compliance_notices",
        ["client_id", "status"],
    )
    op.create_index(
        "ix_compliance_notices_client_authority",
        "compliance_notices",
        ["client_id", "authority"],
    )
    op.create_index(
        "ix_compliance_notices_response_deadline",
        "compliance_notices",
        ["response_deadline"],
    )

    # -----------------------------------------------------------------
    # 7) compliance_notice_activity
    # -----------------------------------------------------------------
    op.create_table("compliance_notice_activity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("notice_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column(
            "details",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["notice_id"], ["compliance_notices.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.CheckConstraint(
            "type IN ('status_change','note_added','file_attached','assigned')",
            name="ck_notice_activity_type",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_compliance_notice_activity_notice_created",
        "compliance_notice_activity",
        ["notice_id", "created_at"],
    )

    # -----------------------------------------------------------------
    # 8) compliance_notice_tags
    # -----------------------------------------------------------------
    op.create_table("compliance_notice_tags",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("notice_id", sa.Integer(), nullable=False),
        sa.Column("tag", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["notice_id"], ["compliance_notices.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("notice_id", "tag", name="uq_notice_tag"),
        sa.PrimaryKeyConstraint("id"),
    )

    # -----------------------------------------------------------------
    # 9) Add notice_id FK to existing `documents` table (D-10)
    # -----------------------------------------------------------------
    op.add_column('documents', sa.Column('notice_id', sa.Integer(),
        sa.ForeignKey('compliance_notices.id', ondelete='SET NULL'), nullable=True))
    op.create_index('idx_documents_notice_id', 'documents', ['notice_id'])


def downgrade() -> None:
    # Reverse-order drops
    op.drop_index('idx_documents_notice_id', table_name='documents')
    op.drop_column('documents', 'notice_id')

    op.drop_table('compliance_notice_tags')

    op.drop_index(
        'ix_compliance_notice_activity_notice_created',
        table_name='compliance_notice_activity',
    )
    op.drop_table('compliance_notice_activity')

    op.drop_index(
        'ix_compliance_notices_response_deadline',
        table_name='compliance_notices',
    )
    op.drop_index(
        'ix_compliance_notices_client_authority',
        table_name='compliance_notices',
    )
    op.drop_index(
        'ix_compliance_notices_client_status',
        table_name='compliance_notices',
    )
    op.drop_table('compliance_notices')

    op.drop_table('compliance_notice_types')

    op.drop_index(
        'ix_compliance_client_memberships_client_id',
        table_name='compliance_client_memberships',
    )
    op.drop_index(
        'ix_compliance_client_memberships_user_id',
        table_name='compliance_client_memberships',
    )
    op.drop_table('compliance_client_memberships')

    op.drop_index(
        'ix_compliance_client_registrations_client_id',
        table_name='compliance_client_registrations',
    )
    op.drop_table('compliance_client_registrations')

    op.drop_index(
        'ix_compliance_regulatory_calendar_year_date',
        table_name='compliance_regulatory_calendar',
    )
    op.drop_table('compliance_regulatory_calendar')

    op.execute("DROP INDEX IF EXISTS ix_clients_config_overrides_gin;")
    op.drop_index(
        'ix_compliance_clients_name', table_name='compliance_clients'
    )
    op.drop_table('compliance_clients')
