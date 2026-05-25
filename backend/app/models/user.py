"""User SQLAlchemy model."""

import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, LargeBinary
from sqlalchemy.orm import relationship
from app.database import Base


class UserRole(str, enum.Enum):
    """Enum for user roles."""
    admin = "admin"
    editor = "editor"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=True)
    full_name = Column(String(200), nullable=True)
    role = Column(String(20), default="editor", index=True, nullable=False)
    auth_provider = Column(String(20), default="local", nullable=False)
    oauth_id = Column(String(255), unique=True, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    # Soft-delete timestamp. NULL = active record; set = anonymized + retired.
    # See migration 0030 for why the audit-log immutability trigger forces
    # soft-delete instead of a real DELETE.
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # --- MFA (TOTP). Secret + backup-code hashes are Fernet-encrypted at rest. ---
    mfa_enabled = Column(Boolean, default=False, nullable=False, server_default="false")
    totp_secret_enc = Column(LargeBinary, nullable=True)         # Fernet(base32 secret)
    mfa_backup_codes_enc = Column(LargeBinary, nullable=True)    # Fernet(JSON[sha256 hashes])
    mfa_enrolled_at = Column(DateTime(timezone=True), nullable=True)

    # --- per-account brute-force lockout (coexists with the per-IP rate limit) ---
    failed_login_count = Column(Integer, default=0, nullable=False, server_default="0")
    locked_until = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    documents = relationship("Document", back_populates="owner", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="owner", cascade="all, delete-orphan")
    shared_documents = relationship("DocumentPermission", back_populates="user", foreign_keys="[DocumentPermission.user_id]")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"
