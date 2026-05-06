"""NoticeReviewQueue ORM — Phase 10 CLASS-04.

Maps to migration 0020's `notice_review_queue` table. Holds low-confidence
(<0.75) classifier predictions until a human reviewer assigns the correct
authority + notice_type. Each notice has at most one row (UNIQUE on
notice_id) — re-classification overwrites the prior row via
ON CONFLICT (notice_id) DO UPDATE.

RLS scoped per Phase 9 client_id pattern (migration 0020 enables and forces
ROW LEVEL SECURITY with tenant_isolation policy).

Reviewer label assignment is a side-effect of /api/compliance/review/{id}/assign
which mutates the parent ComplianceNotice (authority + notice_type_id) within
the same transaction, with NoticeActivity timeline + AuditLog rows written.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import relationship

from app.database import Base


class NoticeReviewQueue(Base):
    __tablename__ = "notice_review_queue"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notice_id = Column(
        Integer,
        ForeignKey("compliance_notices.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    client_id = Column(
        Integer,
        ForeignKey("compliance_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    predicted_authority = Column(String(10), nullable=True)
    predicted_authority_confidence = Column(Numeric(5, 4), nullable=True)
    predicted_type_id = Column(
        Integer,
        ForeignKey("compliance_notice_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    predicted_type_confidence = Column(Numeric(5, 4), nullable=True)

    model_version = Column(String(50), nullable=False)
    reason = Column(String(50), nullable=False)

    reviewer_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewer_assigned_authority = Column(String(10), nullable=True)
    reviewer_assigned_type_id = Column(
        Integer,
        ForeignKey("compliance_notice_types.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )

    notice = relationship("ComplianceNotice", foreign_keys=[notice_id])
    client = relationship("Client", foreign_keys=[client_id])
    predicted_type = relationship(
        "NoticeType", foreign_keys=[predicted_type_id]
    )
    reviewer_assigned_type = relationship(
        "NoticeType", foreign_keys=[reviewer_assigned_type_id]
    )
    reviewer = relationship("User", foreign_keys=[reviewer_id])

    __table_args__ = (
        Index(
            "ix_notice_review_queue_client_pending",
            "client_id",
            "reviewed_at",
        ),
    )

    @property
    def is_pending(self) -> bool:
        return self.reviewed_at is None

    def __repr__(self):
        return (
            f"<NoticeReviewQueue(id={self.id}, notice_id={self.notice_id}, "
            f"reason='{self.reason}', pending={self.is_pending})>"
        )
