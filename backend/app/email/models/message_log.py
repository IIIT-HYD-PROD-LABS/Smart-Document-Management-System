"""GmailMessageLog ORM — Phase 15 EMAIL-08.

Composite UNIQUE on (credential_id, gmail_message_id) per Pitfall 3 +
D-13: dedup point per credential, not globally. Same message_id across
two credentials (different users) is allowed. Restarting the scanner
mid-run never creates duplicate rows.

Per D-36: sender_domain only (full address is PII-redacted out of the
audit args). body_sha256 stored for tampering detection without
persisting the body itself (D-34/D-35).
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class GmailMessageLog(Base):
    __tablename__ = "gmail_message_log"

    ROUTE_COMPLIANCE = "compliance_notice"
    ROUTE_BILL = "bill"
    ROUTE_DMS_ONLY = "dms_only"
    ROUTE_IGNORE = "ignore"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    credential_id = Column(
        Integer,
        ForeignKey("gmail_credentials.id", ondelete="CASCADE"),
        nullable=False,
    )
    gmail_message_id = Column(String(255), nullable=False)
    gmail_thread_id = Column(String(255), nullable=True)
    sender_domain = Column(String(254), nullable=True)
    body_sha256 = Column(String(64), nullable=True)
    route_taken = Column(String(20), nullable=False)
    processed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "credential_id",
            "gmail_message_id",
            name="uq_gmail_message_log_dedup",
        ),
        CheckConstraint(
            "route_taken IN ('compliance_notice','bill','dms_only','ignore')",
            name="ck_gmail_message_log_route_taken",
        ),
    )

    credential = relationship(
        "GmailCredential", back_populates="message_logs"
    )

    def __repr__(self) -> str:
        return (
            f"<GmailMessageLog(id={self.id}, credential_id={self.credential_id}, "
            f"gmail_message_id='{self.gmail_message_id}', route_taken='{self.route_taken}')>"
        )
