"""Document SQLAlchemy model with full-text search support."""

import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Enum,
    ForeignKey, Index, JSON,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship
from app.database import Base


class DocumentCategory(str, enum.Enum):
    BILLS = "bills"
    UPI = "upi"
    TICKETS = "tickets"
    TAX = "tax"
    BANK = "bank"
    INVOICES = "invoices"
    UNKNOWN = "unknown"


class DocumentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # File info
    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)  # pdf, png, jpg, etc.
    file_size = Column(Integer, nullable=False)       # bytes
    file_path = Column(String(1000), nullable=True)   # local path
    s3_url = Column(String(1000), nullable=True)      # S3 URL if uploaded

    # ML classification
    category = Column(
        Enum(DocumentCategory, values_callable=lambda e: [x.value for x in e]),
        default=DocumentCategory.UNKNOWN,
        nullable=False,
        index=True,
    )
    confidence_score = Column(Float, default=0.0, nullable=False)
    extracted_text = Column(Text, nullable=True)

    # Processing status
    status = Column(
        Enum(DocumentStatus, values_callable=lambda e: [x.value for x in e]),
        default=DocumentStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Async processing
    celery_task_id = Column(String(255), nullable=True, index=True)
    extracted_metadata = Column(JSON, nullable=True)

    # Full-text search vector (populated by trigger on INSERT/UPDATE; managed by migration 0003)
    # CRITICAL: No Index(...) here -- GIN index is created via op.execute() in migration to avoid
    # Alembic autogenerate false-diff bug (issue #1390)
    search_vector = Column(TSVECTOR, nullable=True)

    # User-highlighted text (refined extraction)
    highlighted_text = Column(JSON, nullable=True)  # list of {text, start, end} selections

    # AI / LLM extraction (Phase 5)
    ai_summary = Column(Text, nullable=True)
    ai_extracted_fields = Column(JSON, nullable=True)
    ai_extraction_status = Column(String(20), nullable=True)  # pending, completed, failed, skipped
    ai_provider = Column(String(50), nullable=True)
    ai_error = Column(Text, nullable=True)

    # Version control
    current_version = Column(Integer, default=1, nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    owner = relationship("User", back_populates="documents")
    permissions = relationship("DocumentPermission", back_populates="document", cascade="all, delete-orphan")
    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan", order_by="DocumentVersion.version_number.desc()")

    # Indexes for search performance
    __table_args__ = (
        Index("idx_documents_category_user", "category", "user_id"),
        Index("idx_documents_created_at", "created_at"),
    )

    @property
    def total_versions(self) -> int:
        """Total version count: stored snapshots + the current live version."""
        return len(self.versions) + 1 if self.versions is not None else 1

    def __repr__(self):
        return (
            f"<Document(id={self.id}, filename='{self.original_filename}', "
            f"category='{self.category}', status='{self.status}')>"
        )
