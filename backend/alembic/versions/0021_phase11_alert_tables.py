"""Phase 11 — alert pipeline tables (notice_alert_log + notice_alert_rules).

Reuses the existing `compliance_regulatory_calendar` table from Phase 9
migration 0013 (seeded by 0016) for holidays + filing deadlines. This
migration only adds the per-notice alert tracking and per-client/type
alert rule storage.

Per Phase 11 RESEARCH-FINAL.md decisions:
- D-02: notice_alert_log carries (notice_id, alert_type, recipient_user_id,
  channel) UNIQUE for idempotency
- D-08: notice_alert_rules holds JSONB rule per (client_id, notice_type_id)
- RLS: both tables enable + force ROW LEVEL SECURITY mirroring Phase 9 pattern

Idempotent: ADD COLUMN IF NOT EXISTS + CREATE TABLE IF NOT EXISTS.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0021_phase11_alert_tables"
down_revision = "0020_phase10_ml_columns_and_review_queue"
branch_labels = None
depends_on = None


VALID_ALERT_TYPES = (
    "deadline_t7",
    "deadline_t3",
    "deadline_t1",
    "overdue",
    "status_change",
    "received",
    "escalation",
)

VALID_CHANNELS = ("email", "sms", "websocket")

VALID_DELIVERY_STATUSES = ("queued", "sent", "delivered", "failed", "bounced")


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────────
    # 1. notice_alert_log — append-only delivery audit
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "notice_alert_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "notice_id",
            sa.Integer,
            sa.ForeignKey("compliance_notices.id", ondelete="CASCADE"),
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
        sa.Column("alert_type", sa.String(30), nullable=False),
        sa.Column(
            "recipient_user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("recipient_email", sa.String(254), nullable=True),
        sa.Column("recipient_phone", sa.String(20), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column(
            "delivery_status",
            sa.String(20),
            nullable=False,
            server_default="queued",
        ),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "notice_id",
            "alert_type",
            "recipient_user_id",
            "channel",
            name="uq_notice_alert_log_dedup",
        ),
    )
    op.create_check_constraint(
        "ck_notice_alert_log_alert_type",
        "notice_alert_log",
        f"alert_type IN {VALID_ALERT_TYPES!r}".replace("'", "'"),
    )
    op.create_check_constraint(
        "ck_notice_alert_log_channel",
        "notice_alert_log",
        f"channel IN {VALID_CHANNELS!r}".replace("'", "'"),
    )
    op.create_check_constraint(
        "ck_notice_alert_log_delivery_status",
        "notice_alert_log",
        f"delivery_status IN {VALID_DELIVERY_STATUSES!r}".replace("'", "'"),
    )
    op.create_index(
        "ix_notice_alert_log_client_status",
        "notice_alert_log",
        ["client_id", "delivery_status"],
    )

    op.execute("ALTER TABLE notice_alert_log ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notice_alert_log FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON notice_alert_log
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
    # 2. notice_alert_rules — per-client per-notice-type rule overrides
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "notice_alert_rules",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "client_id",
            sa.Integer,
            sa.ForeignKey("compliance_clients.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "notice_type_id",
            sa.Integer,
            sa.ForeignKey("compliance_notice_types.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "rules",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
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
            "client_id",
            "notice_type_id",
            name="uq_alert_rule_client_type",
        ),
    )

    op.execute("ALTER TABLE notice_alert_rules ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE notice_alert_rules FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON notice_alert_rules
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
    # 3. app_runtime grants
    # ──────────────────────────────────────────────────────────────────
    op.execute("GRANT SELECT, INSERT, UPDATE ON notice_alert_log TO app_runtime")
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE notice_alert_log_id_seq TO app_runtime"
    )
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON notice_alert_rules TO app_runtime"
    )
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE notice_alert_rules_id_seq TO app_runtime"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notice_alert_rules")
    op.drop_table("notice_alert_rules")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON notice_alert_log")
    op.drop_index("ix_notice_alert_log_client_status", "notice_alert_log")
    op.drop_constraint("ck_notice_alert_log_delivery_status", "notice_alert_log", type_="check")
    op.drop_constraint("ck_notice_alert_log_channel", "notice_alert_log", type_="check")
    op.drop_constraint("ck_notice_alert_log_alert_type", "notice_alert_log", type_="check")
    op.drop_table("notice_alert_log")
