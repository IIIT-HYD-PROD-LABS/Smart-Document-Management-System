"""GmailFilterRule ORM — Phase 15 EMAIL-04.

priority Integer column resolves open question #5: when two rules match
the same email, the rule with the lower priority value wins. Tie-break
by created_at ASC (older rule wins) — applied at the service layer in
Plan 03's classifier.resolve_route.
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class GmailFilterRule(Base):
    __tablename__ = "gmail_filter_rules"

    ROUTE_COMPLIANCE = "compliance_notice"
    ROUTE_BILL = "bill"
    ROUTE_DMS_ONLY = "dms_only"
    ROUTE_IGNORE = "ignore"

    id = Column(Integer, primary_key=True, autoincrement=True)
    credential_id = Column(
        Integer,
        ForeignKey("gmail_credentials.id", ondelete="CASCADE"),
        nullable=False,
    )
    priority = Column(
        Integer,
        nullable=False,
        server_default="100",
    )
    sender_pattern = Column(String(255), nullable=True)
    subject_pattern = Column(String(255), nullable=True)
    label_include = Column(String(255), nullable=True)
    label_exclude = Column(String(255), nullable=True)
    route_to = Column(String(20), nullable=False)
    enabled = Column(
        Boolean,
        nullable=False,
        server_default="true",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        CheckConstraint(
            "route_to IN ('compliance_notice','bill','dms_only','ignore')",
            name="ck_gmail_filter_rules_route_to",
        ),
        Index(
            "ix_gmail_filter_rules_credential_priority",
            "credential_id",
            "priority",
        ),
    )

    credential = relationship(
        "GmailCredential", back_populates="filter_rules"
    )

    def __repr__(self) -> str:
        return (
            f"<GmailFilterRule(id={self.id}, credential_id={self.credential_id}, "
            f"priority={self.priority}, route_to='{self.route_to}')>"
        )
