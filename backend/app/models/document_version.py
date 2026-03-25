"""Document version model for tracking file revision history."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Float, JSON, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.database import Base


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)

    filename = Column(String(500), nullable=False)
    original_filename = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_path = Column(String(1000), nullable=True)
    s3_url = Column(String(1000), nullable=True)

    extracted_text = Column(Text, nullable=True)
    extracted_metadata = Column(JSON, nullable=True)
    category = Column(String(50), nullable=True)
    confidence_score = Column(Float, nullable=True)
    ai_summary = Column(Text, nullable=True)
    ai_extracted_fields = Column(JSON, nullable=True)

    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    change_reason = Column(String(500), nullable=True)

    document = relationship("Document", back_populates="versions")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("document_id", "version_number", name="uq_document_version"),
        Index("idx_doc_versions_document", "document_id"),
    )
