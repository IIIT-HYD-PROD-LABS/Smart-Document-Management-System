"""Gmail OAuth router — Phase 15 EMAIL-01.

Endpoints:
  POST /api/email/gmail/oauth/authorize -> {authorize_url}
  GET  /api/email/gmail/oauth/callback?code=&state=&error=

state CSRF: signed JWT (HS256, 10-min exp) with nonce + user_id + client_id,
verified by the callback. Mirrors the existing Google login OAuth state
pattern in backend/app/routers/auth.py:309-315.

Per D-07: refresh_token persisted Fernet-encrypted via credential_vault.
Per D-10: scanner scheduled at credential.cadence_minutes after persist.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.services.permission_registry import (
    CompliancePermission,
    ComplianceRole,
    has_permission,
)
from app.config import settings
from app.database import get_async_db
from app.email.services.credential_vault import save_credential
from app.email.services.oauth_service import GmailOAuth
from app.email.services.scanner_service import schedule_gmail_scan

logger = logging.getLogger(__name__)

router = APIRouter(tags=["gmail-oauth"])


def _gmail_redirect_uri() -> str:
    """Resolve the OAuth callback URI.

    Prefers explicit settings.GMAIL_OAUTH_REDIRECT_URI; falls back to
    BASE_URL-derived path. Final fallback is localhost so tests don't
    need to set env vars.
    """
    configured = getattr(settings, "GMAIL_OAUTH_REDIRECT_URI", None)
    if configured:
        return configured
    base = getattr(settings, "BASE_URL", None) or "http://localhost:8000"
    return f"{base.rstrip('/')}/api/email/gmail/oauth/callback"


def _frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", None) or "http://localhost:3000"


@router.post("/gmail/oauth/authorize")
def gmail_authorize(
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """Return the Google OAuth consent URL with signed-JWT state (EMAIL-01).

    state JWT payload: {nonce, user_id, client_id, exp}. Cross-origin
    callback (Google -> backend) cannot use cookies; the JWT is the
    only CSRF binding between authorize and callback.
    """
    state = jwt.encode(
        {
            "nonce": secrets.token_hex(16),
            "user_id": membership.user_id,
            "client_id": membership.client_id,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        },
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    url = GmailOAuth.get_auth_url(state=state, redirect_uri=_gmail_redirect_uri())
    return {"authorize_url": url}


@router.get("/gmail/oauth/callback")
async def gmail_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: AsyncSession = Depends(get_async_db),
):
    """Validate state JWT, exchange code, persist refresh_token, schedule scanner.

    NOTE: This endpoint is NOT cookie-auth gated. Google's redirect comes
    from accounts.google.com cross-site, so SameSite=Strict cookies (our
    JWT, see api.ts) are NOT sent on this request — adding
    require_compliance_permission here would always 401 with
    'Not authenticated'. The signed state JWT (HS256 with our SECRET_KEY,
    nonce + user_id + client_id + exp) is the authentication of record
    here: it proves the request originated from a logged-in user who hit
    /authorize on this server in the last few minutes (and survived a
    round-trip through Google). Same pattern used by /api/auth/oauth/google
    callback (auth.py:336) for v1.0 SSO.

    Error redirects route to the frontend with a query parameter so the
    UI can render an actionable message.
    """
    frontend = _frontend_url()
    if error:
        return RedirectResponse(
            url=f"{frontend}/dashboard/email/connect?error=oauth_denied"
        )
    if not code:
        return RedirectResponse(
            url=f"{frontend}/dashboard/email/connect?error=missing_code"
        )
    if not state:
        return RedirectResponse(
            url=f"{frontend}/dashboard/email/connect?error=missing_state"
        )
    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return RedirectResponse(
            url=f"{frontend}/dashboard/email/connect?error=state_expired"
        )
    except jwt.InvalidTokenError:
        return RedirectResponse(
            url=f"{frontend}/dashboard/email/connect?error=state_invalid"
        )

    state_user_id = payload.get("user_id")
    state_client_id = payload.get("client_id")
    if not state_user_id or not state_client_id:
        return RedirectResponse(
            url=f"{frontend}/dashboard/email/connect?error=state_malformed"
        )

    # Re-verify the user still has email_integration:use on this client at
    # callback time — the state JWT was minted at /authorize but membership
    # could have been revoked while the user was on Google's consent screen.
    membership = (
        await db.execute(
            select(ClientMembership).where(
                ClientMembership.user_id == int(state_user_id),
                ClientMembership.client_id == int(state_client_id),
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        return RedirectResponse(
            url=f"{frontend}/dashboard/email/connect?error=membership_revoked"
        )
    try:
        role_enum = ComplianceRole(membership.compliance_role)
    except ValueError:
        return RedirectResponse(
            url=f"{frontend}/dashboard/email/connect?error=role_invalid"
        )
    if not has_permission(
        role_enum,
        CompliancePermission.EMAIL_INTEGRATION_USE,
    ):
        return RedirectResponse(
            url=f"{frontend}/dashboard/email/connect?error=permission_revoked"
        )

    try:
        token_data = await GmailOAuth.exchange_code(
            code, redirect_uri=_gmail_redirect_uri()
        )
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 — propagate as redirect with error
        # Do not leak the internal exception class name into the URL: it
        # ends up in browser history, Referer headers, and proxy logs and
        # tells an observer which Python module raised. Full traceback is
        # in the server log via logger.exception above; the user only
        # needs a stable error code they can quote to support.
        logger.exception("gmail_oauth_token_exchange_failed")
        return RedirectResponse(
            url=(
                f"{frontend}/dashboard/email/connect"
                "?error=token_exchange_failed"
            )
        )

    cred = await save_credential(
        db,
        user_id=membership.user_id,
        client_id=membership.client_id,
        refresh_token=token_data["refresh_token"],
        scopes=token_data.get("scope"),
        google_account_email=None,
    )
    schedule_gmail_scan(cred.id, cadence_minutes=cred.cadence_minutes)
    return RedirectResponse(
        url=(
            f"{frontend}/dashboard/email/connect?status=success"
            f"&credential_id={cred.id}"
        )
    )
