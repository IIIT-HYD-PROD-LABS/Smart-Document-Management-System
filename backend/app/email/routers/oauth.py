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
from sqlalchemy.orm import Session

from app.compliance.dependencies import require_compliance_permission
from app.compliance.models.membership import ClientMembership
from app.compliance.services.permission_registry import CompliancePermission
from app.config import settings
from app.database import get_db
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
    db: Session = Depends(get_db),
    membership: ClientMembership = Depends(
        require_compliance_permission(CompliancePermission.EMAIL_INTEGRATION_USE)
    ),
):
    """Validate state JWT, exchange code, persist refresh_token, schedule scanner.

    Error redirects route to the frontend with a query parameter so the
    UI can render an actionable message (matching the existing Google
    login OAuth callback pattern at auth.py:336).
    """
    frontend = _frontend_url()
    if error:
        return RedirectResponse(
            url=f"{frontend}/dashboard/email/connect?error=oauth_denied"
        )
    if not code:
        raise HTTPException(400, "Missing authorization code")
    if not state:
        raise HTTPException(400, "Missing OAuth state")
    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(400, "OAuth state expired -- please try again")
    except jwt.InvalidTokenError:
        raise HTTPException(400, "Invalid OAuth state -- possible CSRF")

    state_user_id = payload.get("user_id")
    state_client_id = payload.get("client_id")
    if state_user_id != membership.user_id:
        raise HTTPException(403, "OAuth state user mismatch")
    if state_client_id != membership.client_id:
        raise HTTPException(403, "OAuth state client mismatch")

    try:
        token_data = await GmailOAuth.exchange_code(
            code, redirect_uri=_gmail_redirect_uri()
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 — propagate as 502
        logger.exception("gmail_oauth_token_exchange_failed")
        raise HTTPException(
            502, f"OAuth token exchange failed: {type(e).__name__}"
        )

    cred = save_credential(
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
