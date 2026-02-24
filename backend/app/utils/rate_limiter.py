"""Rate limiting configuration using slowapi backed by Redis."""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    headers_enabled=True,
)
