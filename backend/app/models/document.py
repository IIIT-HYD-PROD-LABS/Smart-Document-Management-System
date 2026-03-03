"""Document SQLAlchemy model with full-text search support."""

import enum
from datetime import datetime, timezone
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Enum,
    ForeignKey, Index, JSON,
)
from sqlalchemy.orm import relationship, deferred
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


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
    confidence_score = Column(Float, default=0.0)
    extracted_text = Column(Text, nullable=True, deferred=True)

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

    # Timestamps
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(
        DateTime,
        default=utcnow,
        onupdate=utcnow,
    )

    # Relationship
    owner = relationship("User", back_populates="documents")

    # Indexes for search performance
    __table_args__ = (
        Index("idx_documents_category_user", "category", "user_id"),
        Index("idx_documents_created_at", "created_at"),
        Index("idx_documents_user_id", "user_id"),
    )

    def __repr__(self):
        return (
            f"<Document(id={self.id}, filename='{self.original_filename}', "
            f"category='{self.category}', status='{self.status}')>"
        )
