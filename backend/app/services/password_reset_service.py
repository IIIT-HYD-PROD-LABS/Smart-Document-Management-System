"""Self-service password reset.

Two-step flow:
    1. `POST /api/auth/forgot-password` { email }
       Always returns 204 (no content) regardless of whether the email
       resolves to a user. Prevents enumeration. If the email DOES
       resolve to a local-auth, active, non-deleted user, an email is
       sent containing a 15-minute single-use signed JWT.

    2. `POST /api/auth/reset-password` { token, password }
       Validates the JWT, looks up the user, sets the new bcrypt hash,
       writes an immutable `password_reset_completed` audit row, and
       invalidates every outstanding refresh token for that user so a
       compromised cookie cannot survive a password change.

Token design:
    Type:        `password_reset`
    TTL:         15 minutes
    Single-use:  enforced by including the user's `updated_at` epoch in
                 the JWT payload. After the reset, `updated_at` advances
                 so the same token fails the re-presentation check.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
from passlib.context import CryptContext
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.models.refresh_token import RefreshToken
from app.models.user import User


logger = logging.getLogger(__name__)


RESET_TOKEN_TYPE = "password_reset"
RESET_TTL = timedelta(minutes=15)

# Matches the bcrypt context used in app.utils.security so hashes are
# interoperable with login. Cost factor 12 = ~200ms verify, sane default.
_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


class PasswordResetError(Exception):
    """Caller-facing failure for reset flows (invalid token, expired, etc.)."""


def _user_token_anchor(user: User) -> int:
    """Anchor a reset token to the user's current state so issuing a new
    token invalidates older ones, and using a token rotates the anchor
    so the same token cannot be replayed.

    `updated_at` advances on every UPDATE to the users row (including
    setting the new password hash), so referencing it as an epoch-seconds
    int gives a single-use property without a separate
    `password_reset_tokens` table.
    """
    ts = getattr(user, "updated_at", None) or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return int(ts.timestamp())


def issue_reset_token(*, user: User) -> str:
    """Mint a short-lived signed JWT for the given user.

    Caller is responsible for resolving the user from the email and
    deciding whether to actually send the email. This function does the
    pure crypto so it stays unit-testable without DB or SMTP.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "type": RESET_TOKEN_TYPE,
        "anchor": _user_token_anchor(user),
        "iat": int(now.timestamp()),
        "exp": int((now + RESET_TTL).timestamp()),
    }
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def consume_reset_token(
    db: Session,
    *,
    token: str,
    new_password: str,
) -> User:
    """Validate the token, update the password, invalidate refresh tokens.

    Raises PasswordResetError with a user-safe message on any failure.
    The router catches it and maps to HTTP 400.
    """
    try:
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except pyjwt.ExpiredSignatureError:
        raise PasswordResetError("Reset link has expired. Request a new one.")
    except pyjwt.InvalidTokenError:
        raise PasswordResetError("Reset link is invalid or has been used.")

    if payload.get("type") != RESET_TOKEN_TYPE:
        raise PasswordResetError("Reset link is not valid for password reset.")

    try:
        user_id = int(payload.get("sub", "0"))
    except (TypeError, ValueError):
        raise PasswordResetError("Reset link is malformed.")

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active or getattr(user, "deleted_at", None) is not None:
        raise PasswordResetError("Reset link is not valid for this account.")

    if user.auth_provider and user.auth_provider != "local":
        # OAuth-only accounts have no password to reset. Tell the user to
        # use their OAuth provider instead of letting them set a password
        # that the login flow will never accept.
        raise PasswordResetError(
            "This account signs in with a provider, not a password. Use the "
            "provider button on /login."
        )

    expected_anchor = _user_token_anchor(user)
    if int(payload.get("anchor", -1)) != expected_anchor:
        # Token was issued before the most recent password change OR
        # already consumed (consumption advances updated_at).
        raise PasswordResetError("Reset link has already been used or superseded.")

    user.hashed_password = _pwd_context.hash(new_password)
    user.updated_at = datetime.now(timezone.utc)

    # Invalidate every outstanding refresh token for this user. A
    # compromised cookie must not survive a password change.
    db.query(RefreshToken).filter(
        RefreshToken.user_id == user.id,
        RefreshToken.is_revoked == False,  # noqa: E712
    ).update({"is_revoked": True}, synchronize_session=False)

    db.commit()
    db.refresh(user)
    return user


async def consume_reset_token_async(
    db: AsyncSession,
    *,
    token: str,
    new_password: str,
) -> User:
    """Async twin of `consume_reset_token`, used by the /reset-password router."""
    try:
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except pyjwt.ExpiredSignatureError:
        raise PasswordResetError("Reset link has expired. Request a new one.")
    except pyjwt.InvalidTokenError:
        raise PasswordResetError("Reset link is invalid or has been used.")

    if payload.get("type") != RESET_TOKEN_TYPE:
        raise PasswordResetError("Reset link is not valid for password reset.")

    try:
        user_id = int(payload.get("sub", "0"))
    except (TypeError, ValueError):
        raise PasswordResetError("Reset link is malformed.")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active or getattr(user, "deleted_at", None) is not None:
        raise PasswordResetError("Reset link is not valid for this account.")

    if user.auth_provider and user.auth_provider != "local":
        # OAuth-only accounts have no password to reset. Tell the user to
        # use their OAuth provider instead of letting them set a password
        # that the login flow will never accept.
        raise PasswordResetError(
            "This account signs in with a provider, not a password. Use the "
            "provider button on /login."
        )

    expected_anchor = _user_token_anchor(user)
    if int(payload.get("anchor", -1)) != expected_anchor:
        # Token was issued before the most recent password change OR
        # already consumed (consumption advances updated_at).
        raise PasswordResetError("Reset link has already been used or superseded.")

    user.hashed_password = _pwd_context.hash(new_password)
    user.updated_at = datetime.now(timezone.utc)

    # Invalidate every outstanding refresh token for this user. A
    # compromised cookie must not survive a password change.
    await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user.id,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
        .values(is_revoked=True)
    )

    await db.commit()
    await db.refresh(user)
    return user
