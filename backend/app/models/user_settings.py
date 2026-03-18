"""UserLLMSettings SQLAlchemy model -- per-user LLM provider configuration."""

import base64
import hashlib
from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UserLLMSettings(Base):
    __tablename__ = "user_llm_settings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    llm_provider = Column(String(50), default="gemini", nullable=False)
    api_key_encrypted = Column(Text, nullable=True)
    model_name = Column(String(100), nullable=True)
    ollama_base_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=lambda: datetime.now(timezone.utc))

    # Relationship back to User
    owner = relationship("User", back_populates="llm_settings")

    def _get_fernet(self):
        """Derive a Fernet key from settings.SECRET_KEY (SHA-256 -> 32 bytes -> base64url)."""
        from cryptography.fernet import Fernet
        from app.config import settings

        key_bytes = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key_bytes)
        return Fernet(fernet_key)

    def encrypt_api_key(self, key: str) -> str:
        """Encrypt an API key and store it in api_key_encrypted. Returns the ciphertext."""
        fernet = self._get_fernet()
        encrypted = fernet.encrypt(key.encode()).decode()
        self.api_key_encrypted = encrypted
        return encrypted

    def decrypt_api_key(self) -> str | None:
        """Decrypt and return the stored API key, or None if no key is stored."""
        if self.api_key_encrypted is None:
            return None
        fernet = self._get_fernet()
        return fernet.decrypt(self.api_key_encrypted.encode()).decode()

    def __repr__(self):
        return (
            f"<UserLLMSettings(id={self.id}, user_id={self.user_id}, "
            f"provider='{self.llm_provider}')>"
        )
