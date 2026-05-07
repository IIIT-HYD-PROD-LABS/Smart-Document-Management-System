"""GmailCredential ORM — Phase 15 EMAIL-01, EMAIL-03.

Per D-07: refresh_token stored as Fernet-encrypted bytes via
app.compliance.utils.pii_encryption (INFRA-06). Access tokens are never
persisted — derived on demand and cached in Redis with TTL=expires_in-60s.

Per D-09: composite UNIQUE on (user_id, client_id) enforces single Gmail
per user-client pair. CAs managing multiple clients connect a different
Gmail per client.
"""
from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class GmailCredential(Base):
    __tablename__ = "gmail_credentials"

    STATUS_ACTIVE = "active"
    STATUS_REVOKED = "revoked"
    STATUS_DISABLED = "disabled"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(
        Integer,
        ForeignKey("compliance_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    google_account_email = Column(String(254), nullable=True)
    refresh_token_enc = Column(LargeBinary, nullable=False)
    scopes = Column(Text, nullable=True)
    status = Column(
        String(20),
        nullable=False,
        server_default="active",
    )
    last_history_id = Column(String(64), nullable=True)
    cadence_minutes = Column(
        Integer,
        nullable=False,
        server_default="15",
    )
    last_scan_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "client_id",
            name="uq_gmail_credentials_user_client",
        ),
        CheckConstraint(
            "status IN ('active','revoked','disabled')",
            name="ck_gmail_credentials_status",
        ),
        CheckConstraint(
            "cadence_minutes BETWEEN 5 AND 1440",
            name="ck_gmail_credentials_cadence",
        ),
    )

    filter_rules = relationship(
        "GmailFilterRule",
        back_populates="credential",
        cascade="all, delete-orphan",
    )
    message_logs = relationship(
        "GmailMessageLog",
        back_populates="credential",
        cascade="all, delete-orphan",
    )
    fetch_logs = relationship(
        "GmailFetchLog",
        back_populates="credential",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<GmailCredential(id={self.id}, user_id={self.user_id}, "
            f"client_id={self.client_id}, status='{self.status}')>"
        )
