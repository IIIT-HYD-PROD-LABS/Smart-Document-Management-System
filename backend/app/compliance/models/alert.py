"""Phase 11 alert ORM — NoticeAlertLog + NoticeAlertRule.

Maps to migration 0021's tables. RLS-scoped per client_id.

Per RESEARCH-FINAL D-02: notice_alert_log carries (notice_id, alert_type,
recipient_user_id, channel) UNIQUE for idempotent dispatch. Re-firing the
same alert is a no-op via INSERT ON CONFLICT DO NOTHING.

Per RESEARCH-FINAL D-08: notice_alert_rules.rules holds JSONB with shape:
  {
    "channels": ["email", "sms", "websocket"],
    "min_risk_tier": "high",          # only fire if tier >= this
    "recipient_roles": ["compliance_head", "cfo"],
    "escalation_chain": ["compliance_head", "cfo", "external_counsel"]
  }
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


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


class NoticeAlertLog(Base):
    __tablename__ = "notice_alert_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notice_id = Column(
        Integer,
        ForeignKey("compliance_notices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(
        Integer,
        ForeignKey("compliance_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alert_type = Column(String(30), nullable=False)
    recipient_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    recipient_email = Column(String(254), nullable=True)
    recipient_phone = Column(String(20), nullable=True)
    channel = Column(String(20), nullable=False)
    delivery_status = Column(
        String(20),
        nullable=False,
        default="queued",
        server_default="queued",
    )
    provider_message_id = Column(String(255), nullable=True)
    error = Column(Text, nullable=True)
    payload = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )
    delivered_at = Column(DateTime(timezone=True), nullable=True)

    notice = relationship("ComplianceNotice", foreign_keys=[notice_id])
    recipient = relationship("User", foreign_keys=[recipient_user_id])

    __table_args__ = (
        UniqueConstraint(
            "notice_id",
            "alert_type",
            "recipient_user_id",
            "channel",
            name="uq_notice_alert_log_dedup",
        ),
        CheckConstraint(
            f"alert_type IN {VALID_ALERT_TYPES!r}".replace("'", "'"),
            name="ck_notice_alert_log_alert_type",
        ),
        CheckConstraint(
            f"channel IN {VALID_CHANNELS!r}".replace("'", "'"),
            name="ck_notice_alert_log_channel",
        ),
        CheckConstraint(
            f"delivery_status IN {VALID_DELIVERY_STATUSES!r}".replace("'", "'"),
            name="ck_notice_alert_log_delivery_status",
        ),
        Index(
            "ix_notice_alert_log_client_status",
            "client_id",
            "delivery_status",
        ),
    )


class NoticeAlertRule(Base):
    __tablename__ = "notice_alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(
        Integer,
        ForeignKey("compliance_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notice_type_id = Column(
        Integer,
        ForeignKey("compliance_notice_types.id", ondelete="CASCADE"),
        nullable=True,
    )
    rules = Column(JSONB, nullable=False, default=dict, server_default="'{}'::jsonb")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )

    notice_type = relationship("NoticeType", foreign_keys=[notice_type_id])

    __table_args__ = (
        UniqueConstraint(
            "client_id", "notice_type_id", name="uq_alert_rule_client_type"
        ),
    )
