"""RefreshToken SQLAlchemy model for opaque refresh token storage."""

from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship
from app.database import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    replaced_by = Column(String(500), nullable=True)

    # Relationship
    owner = relationship("User", back_populates="refresh_tokens")

    __table_args__ = (
        Index("idx_refresh_tokens_user_id", "user_id"),
        Index("idx_refresh_tokens_expires", "expires_at"),
    )

    def __repr__(self):
        return (
            f"<RefreshToken(id={self.id}, user_id={self.user_id}, "
            f"is_revoked={self.is_revoked})>"
        )
