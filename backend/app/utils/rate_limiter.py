"""Rate limiting configuration using slowapi backed by Redis."""

from slowapi import Limiter
from starlette.requests import Request

from app.config import settings


def _get_real_client_ip(request: Request) -> str:
    """Return the direct client IP, ignoring X-Forwarded-For to prevent spoofing.

    If the app is behind a trusted reverse proxy, configure the proxy to set
    a verified header and read that here instead.
    """
    if request.client:
        return request.client.host
    return "127.0.0.1"


limiter = Limiter(
    key_func=_get_real_client_ip,
    storage_uri=settings.REDIS_URL,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    headers_enabled=True,
)
