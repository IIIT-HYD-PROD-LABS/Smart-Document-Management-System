"""JWT authentication and password hashing utilities."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_async_db
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)
security_scheme = HTTPBearer(auto_error=False)

# bcrypt only hashes the first 72 bytes and silently ignores the rest, so two
# passwords sharing a 72-byte prefix would verify interchangeably. Reject longer
# inputs at the boundary instead of letting the tail be silently dropped.
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """Hash a password using bcrypt.

    Raises ValueError if the password exceeds bcrypt's 72-byte limit, so the
    silent-truncation footgun cannot reach the hash. Callers validate length at
    the API boundary first; this is the last-line guard for internal callers.
    """
    if len(password.encode("utf-8")) > BCRYPT_MAX_BYTES:
        raise ValueError(f"Password must not exceed {BCRYPT_MAX_BYTES} bytes")
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode["exp"] = expire
    if "type" not in to_encode:
        to_encode["type"] = "access"
    to_encode["jti"] = secrets.token_urlsafe(16)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token() -> tuple[str, datetime]:
    """Generate an opaque refresh token and its expiry timestamp."""
    token = secrets.token_urlsafe(64)
    expires_at = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    return token, expires_at


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT access token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: AsyncSession = Depends(get_async_db),
) -> User:
    """FastAPI dependency to get the current authenticated user."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(credentials.credentials)
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    try:
        user_id_int = int(user_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )
    result = await db.execute(select(User).where(User.id == user_id_int))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated",
        )
    # Phase 9: propagate user_id to ContextVar so the SQLAlchemy
    # before_cursor_execute listener can write it as app.user_id, which
    # is_cross_client_eligible() reads to authorize the cross_client_view
    # RLS policy. Compliance package may not be loaded at v1.0 endpoint
    # time, so swallow ImportError silently.
    try:
        from app.compliance.middleware.tenant_context import current_user_id_var

        current_user_id_var.set(user.id)
    except Exception:
        pass
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency that restricts access to admin users only."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_editor(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency that restricts access to admin and editor users."""
    if current_user.role not in ("admin", "editor"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Editor access required",
        )
    return current_user


def require_viewer(current_user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency for viewer access. All authenticated users can view."""
    return current_user


# ---------------------------------------------------------------------------
# Phase 9: Compliance role/permission Depends — delegates to
# app.compliance.dependencies. Mirrors the v1.0 require_admin/require_editor
# naming convention so routers can `from app.utils.security import ...` for
# both system-role and compliance-role guards.
#
# Imports are deferred to avoid a circular import at startup:
# app.compliance.dependencies depends on this module's get_current_user.
# ---------------------------------------------------------------------------


def require_compliance_permission(perm):
    """Re-export of app.compliance.dependencies.require_compliance_permission.

    Allows routers to import compliance guards from app.utils.security
    consistently with the v1.0 require_admin pattern.
    """
    from app.compliance.dependencies import (
        require_compliance_permission as _impl,
    )

    return _impl(perm)


def require_compliance_role(*roles):
    """Re-export of app.compliance.dependencies.require_compliance_role."""
    from app.compliance.dependencies import require_compliance_role as _impl

    return _impl(*roles)
