"""Phase 12 response workflow ORM — NoticeResponse + NoticeResponseVersion +
NoticeResponseApproval + NoticeEvidenceAttachment.

Maps to migration 0022. RLS-scoped per Phase 9 client_id pattern.

Per Phase 12 RESEARCH-FINAL §2: 4-stage state machine
(Drafter → Reviewer → Legal → CFO) is enforced server-side via
`approval_service`. The DB CHECK constraint is defense-in-depth only.

Per RESEARCH-FINAL §3: NoticeResponseVersion is append-only — rollback
writes a new version pointing at older content, never mutates an existing
version row.

Approvals are immutable per Phase 9 AUDIT-02 pattern (no UPDATE grant on
app_runtime).
"""
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database import Base


VALID_RESPONSE_STATUSES = (
    "draft",
    "reviewer_pending",
    "legal_pending",
    "cfo_pending",
    "approved",
    "rejected",
    "withdrawn",
)

VALID_APPROVAL_STAGES = ("reviewer", "legal", "cfo")
VALID_APPROVAL_DECISIONS = ("approved", "rejected")

TERMINAL_RESPONSE_STATUSES = frozenset({"approved", "rejected", "withdrawn"})


class NoticeResponse(Base):
    __tablename__ = "notice_responses"

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
    current_version_id = Column(
        Integer,
        ForeignKey("notice_response_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(String(30), nullable=False, default="draft", server_default="draft")
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
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

    notice = relationship("ComplianceNotice", foreign_keys=[notice_id])
    client = relationship("Client", foreign_keys=[client_id])
    current_version = relationship(
        "NoticeResponseVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )
    versions = relationship(
        "NoticeResponseVersion",
        back_populates="response",
        foreign_keys="NoticeResponseVersion.response_id",
        cascade="all, delete-orphan",
    )
    approvals = relationship(
        "NoticeResponseApproval",
        back_populates="response",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN {VALID_RESPONSE_STATUSES!r}".replace("'", "'"),
            name="ck_notice_responses_status",
        ),
    )

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_RESPONSE_STATUSES


class NoticeResponseVersion(Base):
    __tablename__ = "notice_response_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    response_id = Column(
        Integer,
        ForeignKey("notice_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(
        Integer,
        ForeignKey("compliance_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_no = Column(Integer, nullable=False)
    subject = Column(String(500), nullable=True)
    body_markdown = Column(Text, nullable=False, default="", server_default="")
    recipient = Column(String(500), nullable=True)
    response_date = Column(Date, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    rolled_back_from_version_id = Column(Integer, nullable=True)
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )

    response = relationship(
        "NoticeResponse",
        back_populates="versions",
        foreign_keys=[response_id],
    )

    __table_args__ = (
        UniqueConstraint(
            "response_id", "version_no", name="uq_response_versions_no"
        ),
    )


class NoticeResponseApproval(Base):
    __tablename__ = "notice_response_approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    response_id = Column(
        Integer,
        ForeignKey("notice_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version_id = Column(
        Integer,
        ForeignKey("notice_response_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    client_id = Column(
        Integer,
        ForeignKey("compliance_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stage = Column(String(20), nullable=False)
    decision = Column(String(20), nullable=False)
    actor_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )

    response = relationship("NoticeResponse", back_populates="approvals")
    version = relationship("NoticeResponseVersion", foreign_keys=[version_id])
    actor = relationship("User", foreign_keys=[actor_user_id])

    __table_args__ = (
        CheckConstraint(
            f"stage IN {VALID_APPROVAL_STAGES!r}".replace("'", "'"),
            name="ck_response_approvals_stage",
        ),
        CheckConstraint(
            f"decision IN {VALID_APPROVAL_DECISIONS!r}".replace("'", "'"),
            name="ck_response_approvals_decision",
        ),
    )


class NoticeEvidenceAttachment(Base):
    __tablename__ = "notice_evidence_attachments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notice_id = Column(
        Integer,
        ForeignKey("compliance_notices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_id = Column(
        Integer,
        ForeignKey("compliance_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_order = Column(Integer, nullable=False, default=0, server_default="0")
    description = Column(String(500), nullable=True)
    added_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )

    notice = relationship("ComplianceNotice", foreign_keys=[notice_id])
    document = relationship("Document", foreign_keys=[document_id])

    __table_args__ = (
        UniqueConstraint(
            "notice_id", "document_id", name="uq_evidence_notice_document"
        ),
    )
