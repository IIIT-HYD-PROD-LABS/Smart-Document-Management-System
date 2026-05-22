"""ComplianceNotice + NoticeActivity + NoticeTag ORM models.

Phase 9 LIFE-01..09. Maps to migration 0013 tables:
  - compliance_notices         (ComplianceNotice — heart of LIFE-01..08)
  - compliance_notice_activity (NoticeActivity   — D-09 user-facing timeline)
  - compliance_notice_tags     (NoticeTag        — D-11 custom labels)

Per CONTEXT D-02: ComplianceNotice is its own model (NOT extending Document).
Document is linked via FK for uploaded notice files (D-10) and the v1.0
upload pipeline keeps working unchanged.

Per CONTEXT D-03: status is a String(30) column with CHECK constraint —
authoritative state machine logic lives in services.notice_state_machine.
The DB constraint is a defense-in-depth boundary.

Per CONTEXT D-04: parent_notice_id is the self-FK that builds the
SCN -> Assessment -> Demand -> Appeal chain. notice_service.get_notice_chain
runs a recursive CTE bounded by max_depth (Pattern 5 from RESEARCH).

Per CONTEXT D-05: 4 distinct deadline columns capture the multi-stage
Indian compliance timeline (response, hearing, compliance, appeal).

Per CONTEXT D-08: tax_demand / interest / penalty / total_liability are
Numeric(18, 2) for INR audit-grade money math.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import relationship

from app.database import Base


VALID_NOTICE_STATUSES = (
    "received",
    "under_review",
    "response_drafted",
    "submitted",
    "resolved",
    "dismissed",
)

VALID_AUTHORITIES = ("GST", "IT", "MCA", "RBI", "SEBI")


class ComplianceNotice(Base):
    __tablename__ = "compliance_notices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(
        Integer,
        ForeignKey("compliance_clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notice_type_id = Column(
        Integer,
        ForeignKey("compliance_notice_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    registration_id = Column(
        Integer,
        ForeignKey("compliance_client_registrations.id", ondelete="SET NULL"),
        nullable=True,
    )
    # D-04: Self-FK for SCN -> Assessment -> Demand -> Appeal chains.
    parent_notice_id = Column(
        Integer,
        ForeignKey("compliance_notices.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # D-10: Reuses v1.0 Document model for uploaded notice file (back-ref
    # added on Document.notice in Task 4).
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )

    notice_number = Column(String(100), nullable=False, index=True)
    authority = Column(String(10), nullable=False, index=True)
    # D-03: 'received' is the entry state of the state machine.
    status = Column(
        String(30),
        nullable=False,
        default="received",
        server_default="received",
        index=True,
    )
    received_date = Column(
        Date,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).date(),
        server_default="now()",
    )
    # D-05: Multi-stage deadlines.
    response_deadline = Column(Date, nullable=True, index=True)
    hearing_date = Column(Date, nullable=True)
    compliance_date = Column(Date, nullable=True)
    appeal_deadline = Column(Date, nullable=True)
    # D-08: Structured INR financial fields.
    tax_demand = Column(Numeric(18, 2), nullable=True)
    interest = Column(Numeric(18, 2), nullable=True)
    penalty = Column(Numeric(18, 2), nullable=True)
    total_liability = Column(Numeric(18, 2), nullable=True)
    # D-12: Legal section references (rendered as badges; future regulation library).
    legal_sections = Column(
        JSONB,
        nullable=False,
        default=list,
        server_default="'[]'::jsonb",
    )
    assigned_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status_changed_at = Column(DateTime(timezone=True), nullable=True)
    created_by_user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Phase 10 — ML output columns (migration 0020)
    classifier_authority_confidence = Column(Numeric(5, 4), nullable=True)
    classifier_type_confidence = Column(Numeric(5, 4), nullable=True)
    risk_score = Column(Numeric(5, 2), nullable=True)
    risk_tier = Column(String(20), nullable=True, index=True)
    ner_extracted_fields = Column(JSONB, nullable=True)
    model_version = Column(String(50), nullable=True)
    classified_at = Column(DateTime(timezone=True), nullable=True)
    risk_scored_at = Column(DateTime(timezone=True), nullable=True)

    # Phase 17 — LLM-based field extraction artefact (migration 0034).
    # Shape per 17-CONTEXT.md D-03 envelope; routing per D-06.
    extracted_fields = Column(JSONB, nullable=True)
    extraction_confidence = Column(Numeric(3, 2), nullable=True)
    extracted_by_provider = Column(String(120), nullable=True)
    extracted_at = Column(DateTime(timezone=True), nullable=True)
    extraction_status = Column(String(20), nullable=True)
    # Phase 15 + Phase 14 — source provenance for filter chip on dashboard.
    source = Column(
        String(20),
        nullable=False,
        default="manual",
        server_default="manual",
        index=True,
    )

    # Phase 13 — full-text search vector (migration 0023). Maintained by a
    # PostgreSQL trigger; never written from Python.
    search_vector = Column(TSVECTOR, nullable=True)

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

    # Relationships
    client = relationship("Client", back_populates="notices")
    parent = relationship(
        "ComplianceNotice",
        remote_side="ComplianceNotice.id",
        foreign_keys=[parent_notice_id],
    )
    activities = relationship(
        "NoticeActivity",
        back_populates="notice",
        cascade="all, delete-orphan",
    )
    tags = relationship(
        "NoticeTag",
        back_populates="notice",
        cascade="all, delete-orphan",
    )
    notice_type = relationship("NoticeType", foreign_keys=[notice_type_id])
    registration = relationship(
        "ClientRegistration", foreign_keys=[registration_id]
    )
    assigned_user = relationship("User", foreign_keys=[assigned_user_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])

    __table_args__ = (
        CheckConstraint(
            "authority IN ('GST', 'IT', 'MCA', 'RBI', 'SEBI')",
            name="ck_notices_authority",
        ),
        CheckConstraint(
            "status IN ("
            "'received', 'under_review', 'response_drafted', "
            "'submitted', 'resolved', 'dismissed')",
            name="ck_notices_status",
        ),
        # Phase 10 — risk_tier check (mirrors migration 0020).
        CheckConstraint(
            "risk_tier IS NULL OR risk_tier IN ('critical', 'high', 'medium', 'low')",
            name="ck_compliance_notices_risk_tier_valid",
        ),
        # Phase 17 — extraction status check (mirrors migration 0034).
        CheckConstraint(
            "extraction_status IS NULL OR extraction_status IN "
            "('pending', 'completed', 'failed', 'accepted', 'superseded')",
            name="ck_compliance_notices_extraction_status",
        ),
        # Phase 17 — confidence bounded to [0, 1] (mirrors migration 0034).
        CheckConstraint(
            "extraction_confidence IS NULL OR "
            "(extraction_confidence >= 0 AND extraction_confidence <= 1)",
            name="ck_compliance_notices_extraction_confidence",
        ),
        # Phase 10 + Phase 15 — source provenance.
        CheckConstraint(
            "source IN ('manual', 'portal', 'gmail', 'imap')",
            name="ck_compliance_notices_source_valid",
        ),
        Index("ix_notices_client_status", "client_id", "status"),
        Index("ix_notices_client_authority", "client_id", "authority"),
    )

    def __repr__(self):
        return (
            f"<ComplianceNotice(id={self.id}, number='{self.notice_number}', "
            f"client_id={self.client_id}, status='{self.status}')>"
        )


class NoticeActivity(Base):
    """User-facing activity timeline (D-09).

    Distinct from system audit_log — this is the timeline rendered in the
    notice detail UI (status changes, notes, file attachments, assignments).
    Mutable per RESEARCH Q2 recommendation; immutability is the audit_log's
    job (AUDIT-01 / AUDIT-02).
    """

    __tablename__ = "compliance_notice_activity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notice_id = Column(
        Integer,
        ForeignKey("compliance_notices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # 'status_change' | 'note_added' | 'file_attached' | 'assigned'
    type = Column(String(30), nullable=False, index=True)
    details = Column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="'{}'::jsonb",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )

    notice = relationship("ComplianceNotice", back_populates="activities")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        CheckConstraint(
            "type IN ('status_change', 'note_added', 'file_attached', 'assigned')",
            name="ck_notice_activity_type",
        ),
        Index(
            "ix_notice_activity_notice_created",
            "notice_id",
            "created_at",
        ),
    )

    def __repr__(self):
        return (
            f"<NoticeActivity(notice_id={self.notice_id}, "
            f"type='{self.type}')>"
        )


class NoticeTag(Base):
    """Simple notice tag junction table (D-11).

    Custom user labels — branch, quarter, review-round, etc.
    Many-to-one to ComplianceNotice; UNIQUE (notice_id, tag) prevents
    duplicate labels on the same notice.
    """

    __tablename__ = "compliance_notice_tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    notice_id = Column(
        Integer,
        ForeignKey("compliance_notices.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag = Column(String(50), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default="now()",
    )

    notice = relationship("ComplianceNotice", back_populates="tags")

    __table_args__ = (
        UniqueConstraint("notice_id", "tag", name="uq_notice_tags_notice_tag"),
    )

    def __repr__(self):
        return f"<NoticeTag(notice_id={self.notice_id}, tag='{self.tag}')>"
