"""AICredential ORM — Phase 16 BYOK AI integration.

One row per compliance_client. Stores the tenant's chosen provider
('anthropic' or 'google'), the model identifier, and the Fernet-encrypted
API key. Plaintext keys are never persisted — see INFRA-06 / pii_encryption.
"""
from __future__ import annotations

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base


class AICredential(Base):
    __tablename__ = "ai_credentials"

    PROVIDER_ANTHROPIC = "anthropic"
    PROVIDER_GOOGLE = "google"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(
        Integer,
        ForeignKey("compliance_clients.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = Column(String(20), nullable=False)
    model = Column(String(100), nullable=False)
    api_key_enc = Column(LargeBinary, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    last_used_at = Column(DateTime(timezone=True), nullable=True)

    client = relationship("Client")

    __table_args__ = (
        UniqueConstraint("client_id", name="uq_ai_credentials_client"),
        CheckConstraint(
            "provider IN ('anthropic', 'google')",
            name="ck_ai_credentials_provider",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AICredential(id={self.id}, client_id={self.client_id}, "
            f"provider='{self.provider}', model='{self.model}')>"
        )
