"""Tenant-team invitation service.

When an admin (or compliance_head) adds a team member to a client, the
caller may not know whether the invitee already has a TaxSync account.
This module hides the resolution rule:

  - If the email belongs to an existing User row, return that user.id.
  - If not, create a "pending" User row (hashed_password NULL,
    is_active=False) and queue an email invite containing a signed JWT.
    The invitee accepts via POST /api/auth/accept-invite, which sets the
    password and flips is_active=True.

The pending-User pattern means a ClientMembership row can always point
at a valid users.id, so the existing RLS / membership lookups need no
change. The only new gate is `get_current_user`, which already rejects
is_active=False, so an invited-but-not-accepted user cannot authenticate
until they complete the accept-invite flow.

Login flow for an invited team member:
  1. Admin POST /api/compliance/clients/{id}/memberships with {email,
     compliance_role}; this creates the User + Membership atomically and
     sends the invitation email.
  2. Invitee clicks the link, lands on /accept-invite?token=<JWT>; the
     frontend POSTs {token, password} to /api/auth/accept-invite.
  3. Backend validates the JWT, sets hashed_password, flips
     is_active=True, returns access + refresh tokens. Invitee is now
     logged in and has the membership granted in step 1.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import jwt as pyjwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)

_EMAIL_RX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Use the same bcrypt context as utils/security.py so password hashes
# are interoperable; the accept-invite endpoint hashes the chosen
# password through this and writes it back to users.hashed_password.
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

INVITE_TOKEN_TYPE = "tenant_invite"
INVITE_TTL = timedelta(days=7)


class InvitationError(Exception):
    """Caller-facing failure (validation / not-found) for invite flows."""


def _email_to_username(email: str) -> str:
    """Derive a username from an email local-part. Falls back to
    timestamp suffix on collisions in the caller."""
    local = email.split("@", 1)[0]
    # Trim to schema max + sanitise
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "", local).lower()[:80]
    return cleaned or "user"


def _generate_invite_token(*, user_id: int, email: str, client_id: int) -> str:
    payload = {
        "type": INVITE_TOKEN_TYPE,
        "user_id": user_id,
        "email": email,
        "client_id": client_id,
        "exp": datetime.now(timezone.utc) + INVITE_TTL,
        "iat": datetime.now(timezone.utc),
    }
    return pyjwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_invite_token(token: str) -> dict:
    """Decode + validate a tenant-invite JWT. Raises InvitationError on
    expiry / signature / wrong-type."""
    try:
        payload = pyjwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
    except pyjwt.ExpiredSignatureError as e:
        raise InvitationError("Invitation has expired") from e
    except pyjwt.InvalidTokenError as e:
        raise InvitationError("Invalid invitation link") from e
    if payload.get("type") != INVITE_TOKEN_TYPE:
        raise InvitationError("Invalid invitation token type")
    if not (payload.get("user_id") and payload.get("email")):
        raise InvitationError("Malformed invitation payload")
    return payload


def _unique_username(db: Session, base: str) -> str:
    """Return a username not already taken in users.username."""
    candidate = base
    suffix = 0
    while db.query(User.id).filter(User.username == candidate).first() is not None:
        suffix += 1
        candidate = f"{base}_{suffix}"
        if suffix > 50:  # defensive: bail rather than spin forever
            candidate = f"{base}_{int(datetime.now(timezone.utc).timestamp())}"
            break
    return candidate


def resolve_or_invite(
    db: Session,
    *,
    client_id: int,
    client_name: str,
    inviter: User,
    email: Optional[str] = None,
    user_id: Optional[int] = None,
    full_name: Optional[str] = None,
) -> Tuple[int, bool, Optional[str]]:
    """Resolve an invitee to a User row, pre-creating + emailing on miss.

    Exactly one of `email` or `user_id` must be supplied. Returns
    (resolved_user_id, invite_sent, invite_token_for_dev_log).

    `invite_token_for_dev_log` is non-None only when SMTP is unconfigured
    and DEBUG=True; it lets the developer copy the accept-invite URL out
    of the structured log. Production callers should ignore it.
    """
    if not email and not user_id:
        raise InvitationError("Either email or user_id is required")
    if email and user_id:
        # Be explicit rather than silently picking one — the frontend
        # should send exactly one. Use email when both can be derived.
        raise InvitationError("Specify either email or user_id, not both")

    # Path A: user_id supplied -> verify it exists, no email side-effect.
    if user_id is not None:
        existing = db.get(User, user_id)
        if existing is None or existing.deleted_at is not None:
            raise InvitationError(f"User {user_id} does not exist")
        return existing.id, False, None

    # Path B: email supplied -> find or pre-create.
    assert email is not None  # for type-checkers
    if not _EMAIL_RX.match(email):
        raise InvitationError(f"Invalid email format: {email}")
    email = email.strip().lower()

    existing = (
        db.query(User)
        .filter(User.email == email, User.deleted_at.is_(None))
        .first()
    )
    if existing is not None:
        # Real user, just attach the membership. The standard get_current_user
        # path will reject them if is_active=False (e.g., they were invited
        # once, never accepted, and are now being re-invited from another
        # client). Re-send the invite so they can still complete signup.
        if not existing.is_active and existing.hashed_password is None:
            token = _generate_invite_token(
                user_id=existing.id, email=existing.email, client_id=client_id
            )
            _send_invite(
                existing.email,
                full_name or existing.full_name or existing.email,
                inviter,
                client_name,
                token,
            )
            dev_token = token if (not settings.SMTP_HOST and settings.DEBUG) else None
            return existing.id, True, dev_token
        return existing.id, False, None

    # Pre-create a pending user. Username derived from local-part with
    # collision-resolution suffix. hashed_password stays NULL until the
    # invitee accepts.
    username = _unique_username(db, _email_to_username(email))
    pending = User(
        email=email,
        username=username,
        hashed_password=None,
        full_name=(full_name or "").strip() or None,
        role="editor",  # global role; compliance scope is on the membership
        is_active=False,
        auth_provider="local",
    )
    db.add(pending)
    db.flush()  # materialise pending.id without committing the wrapper

    token = _generate_invite_token(
        user_id=pending.id, email=pending.email, client_id=client_id
    )
    _send_invite(
        pending.email,
        full_name or pending.email,
        inviter,
        client_name,
        token,
    )

    dev_token = token if (not settings.SMTP_HOST and settings.DEBUG) else None
    return pending.id, True, dev_token


def _send_invite(
    to_email: str,
    invitee_name: str,
    inviter: User,
    client_name: str,
    token: str,
) -> None:
    """Send the tenant-invite email. Import is deferred so this module
    can be imported by tooling without dragging the email stack."""
    from app.utils.email import send_tenant_invite_email

    sent = send_tenant_invite_email(
        to_email=to_email,
        invitee_name=invitee_name,
        inviter_name=(inviter.full_name or inviter.email),
        client_name=client_name,
        invite_token=token,
    )
    if not sent:
        # Do not raise: the membership row should still be created so
        # the admin can resend the invite. The accept-invite URL is
        # logged in DEBUG mode for local development.
        logger.warning(
            "tenant_invite_email_skipped",
            extra={
                "to": to_email,
                "client": client_name,
                "inviter_id": inviter.id,
                "hint": (
                    "SMTP not configured or send rejected. "
                    "Use the dev token in the response (DEBUG mode) to "
                    "complete the accept-invite flow manually."
                ),
            },
        )


def accept_invite(
    db: Session, *, token: str, new_password: str
) -> User:
    """Consume an invite token: set the user's password + activate them.

    Returns the updated User on success. Raises InvitationError on
    invalid token / mismatched user / weak password.
    """
    payload = decode_invite_token(token)
    user_id = int(payload["user_id"])
    email = payload["email"]

    user = db.get(User, user_id)
    if user is None or user.deleted_at is not None or user.email != email:
        raise InvitationError("Invitation no longer valid")

    if user.is_active and user.hashed_password is not None:
        # Already accepted; signing in is the right next step. Do not
        # silently overwrite the existing password.
        raise InvitationError(
            "This account is already active. Sign in with your existing password."
        )

    if not new_password or len(new_password) < 12:
        raise InvitationError("Password must be at least 12 characters")

    user.hashed_password = pwd_context.hash(new_password)
    user.is_active = True
    db.commit()
    db.refresh(user)
    logger.info(
        "tenant_invite_accepted",
        extra={"user_id": user.id, "email": user.email},
    )
    return user
