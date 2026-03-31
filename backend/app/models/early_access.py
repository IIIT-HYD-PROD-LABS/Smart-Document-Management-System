"""Early Access Request SQLAlchemy model."""

import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, Index
from app.database import Base


class EarlyAccessStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class EarlyAccessRequest(Base):
    __tablename__ = "early_access_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=False, index=True)
    company = Column(String(200), nullable=True)
    reason = Column(Text, nullable=True)
    status = Column(String(20), default="pending", nullable=False, index=True)
    admin_note = Column(Text, nullable=True)
    invitation_token = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(Integer, nullable=True)

    __table_args__ = (
        Index("ix_early_access_email_status", "email", "status"),
    )

    def __repr__(self):
        return f"<EarlyAccessRequest(id={self.id}, email='{self.email}', status='{self.status}')>"
