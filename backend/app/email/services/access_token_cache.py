"""Gmail access-token cache — Phase 15 EMAIL-03.

Access tokens NEVER persisted to DB; only Redis with TTL = expires_in - 60s
skew. RefreshError (invalid_grant) flips the credential to revoked via
credential_vault.handle_invalid_grant and re-raises as 401 (Pitfall 2).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import redis
from fastapi import HTTPException
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy.orm import Session

from app.config import settings
from app.email.services.credential_vault import handle_invalid_grant, load_credential

logger = logging.getLogger(__name__)

_redis: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    """Singleton Redis client. Reads from `settings.REDIS_URL` (not the raw
    env var) so deployments that override REDIS_SSL_VERIFY or normalise the
    URL through pydantic-settings get the correct client. The connection
    options stay aligned with `rate_limiter.py` and `main.py`.
    """
    global _redis
    if _redis is None:
        url = settings.REDIS_URL
        kwargs: dict = {"decode_responses": True}
        if url.startswith("rediss://") and not settings.REDIS_SSL_VERIFY:
            kwargs["ssl_cert_reqs"] = None
        _redis = redis.Redis.from_url(url, **kwargs)
    return _redis


def get_or_refresh_access_token(db: Session, credential_id: int) -> Credentials:
    r = _get_redis()
    cache_key = f"gmail:access:{credential_id}"
    cred, refresh_token = load_credential(db, credential_id)
    scopes = (cred.scopes or "").split() if cred.scopes else []
    cached = r.get(cache_key)
    if cached:
        return Credentials(
            token=cached,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=scopes,
        )
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=scopes,
    )
    try:
        creds.refresh(Request())
    except RefreshError as e:
        logger.warning(
            "Gmail invalid_grant for credential %s: %s", credential_id, e
        )
        handle_invalid_grant(db, credential_id)
        raise HTTPException(401, "Gmail credential revoked") from e

    ttl = 3600 - 60
    if creds.expiry:
        expiry_aware = creds.expiry
        if expiry_aware.tzinfo is None:
            expiry_aware = expiry_aware.replace(tzinfo=timezone.utc)
        seconds_left = int(
            (expiry_aware - datetime.now(timezone.utc)).total_seconds()
        )
        ttl = max(60, seconds_left - 60)
    if creds.token:
        r.setex(cache_key, ttl, creds.token)
    return creds
