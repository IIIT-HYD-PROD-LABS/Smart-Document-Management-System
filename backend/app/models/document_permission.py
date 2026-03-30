"""DocumentPermission model for document sharing."""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from app.database import Base


class DocumentPermission(Base):
    __tablename__ = "document_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    permission = Column(String(20), nullable=False, default="view")  # "view" or "edit"
    granted_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    document = relationship("Document", back_populates="permissions")
    user = relationship("User", foreign_keys=[user_id], back_populates="shared_documents")
    granter = relationship("User", foreign_keys=[granted_by])

    __table_args__ = (
        UniqueConstraint("document_id", "user_id", name="uq_document_user_permission"),
        Index("idx_doc_permissions_user", "user_id"),
        Index("idx_doc_permissions_document", "document_id"),
    )

    def __repr__(self):
        return (
            f"<DocumentPermission(id={self.id}, document_id={self.document_id}, "
            f"user_id={self.user_id}, permission='{self.permission}')>"
        )
