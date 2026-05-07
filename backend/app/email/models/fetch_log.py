"""GmailFetchLog ORM — Phase 15 EMAIL-07.

Three-state status matching Phase 14 PortalFetchLog pattern (D-15):
SUCCESS_EMPTY (poll completed, no new messages),
SUCCESS_WITH_RESULTS (poll completed, N messages processed),
FETCH_FAILED (poll raised an exception). Two consecutive FETCH_FAILED
rows for the same credential trigger a Phase 11 alert in Plan 03.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.database import Base


class GmailFetchLog(Base):
    __tablename__ = "gmail_fetch_log"

    STATUS_SUCCESS_EMPTY = "SUCCESS_EMPTY"
    STATUS_SUCCESS_WITH_RESULTS = "SUCCESS_WITH_RESULTS"
    STATUS_FETCH_FAILED = "FETCH_FAILED"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    credential_id = Column(
        Integer,
        ForeignKey("gmail_credentials.id", ondelete="CASCADE"),
        nullable=False,
    )
    status = Column(String(30), nullable=False)
    messages_processed = Column(
        Integer,
        nullable=False,
        server_default="0",
    )
    error_message = Column(Text, nullable=True)
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('SUCCESS_EMPTY','SUCCESS_WITH_RESULTS','FETCH_FAILED')",
            name="ck_gmail_fetch_log_status",
        ),
        Index(
            "ix_gmail_fetch_log_credential_started",
            "credential_id",
            text("started_at DESC"),
        ),
    )

    credential = relationship(
        "GmailCredential", back_populates="fetch_logs"
    )

    def __repr__(self) -> str:
        return (
            f"<GmailFetchLog(id={self.id}, credential_id={self.credential_id}, "
            f"status='{self.status}', messages_processed={self.messages_processed})>"
        )
