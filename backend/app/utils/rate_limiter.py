"""Rate limiting configuration using slowapi backed by Redis with in-memory fallback."""

import logging
from urllib.parse import urlparse

from redis import Redis
from slowapi import Limiter
from starlette.requests import Request

from app.config import settings

logger = logging.getLogger(__name__)


def _redact_url(url: str) -> str:
    """Redact password from a Redis URL for safe logging."""
    try:
        parsed = urlparse(url)
        if parsed.password:
            return url.replace(f":{parsed.password}@", ":***@")
        return url
    except Exception:
        return "<unparseable-url>"


def _get_real_client_ip(request: Request) -> str:
    """Return the direct client IP, ignoring X-Forwarded-For to prevent spoofing.

    If the app is behind a trusted reverse proxy, configure the proxy to set
    a verified header and read that here instead.
    """
    if request.client:
        return request.client.host
    return "127.0.0.1"


def _get_storage_uri() -> str:
    """Return Redis URI if Redis is reachable, otherwise fall back to in-memory storage."""
    redis_url = settings.REDIS_URL
    safe_url = _redact_url(redis_url)
    try:
        r = Redis.from_url(redis_url, socket_connect_timeout=2)
        r.ping()
        logger.info("Rate limiter connected to Redis at %s", safe_url)
        return redis_url
    except Exception:
        logger.warning(
            "Redis unavailable at %s — rate limiter falling back to in-memory storage. "
            "Rate limits will not be shared across workers.",
            safe_url,
        )
        return "memory://"


limiter = Limiter(
    key_func=_get_real_client_ip,
    storage_uri=_get_storage_uri(),
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    headers_enabled=True,
)
