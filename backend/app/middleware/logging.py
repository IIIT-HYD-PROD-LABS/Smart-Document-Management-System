"""Request logging middleware with timing and correlation-ID binding."""

import time

import structlog
from asgi_correlation_id import correlation_id
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = structlog.stdlib.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with duration, status, and correlation ID."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Reset per-request context
        structlog.contextvars.clear_contextvars()

        # Bind useful identifiers into every log line for this request
        structlog.contextvars.bind_contextvars(
            request_id=correlation_id.get() or "",
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        # Try to extract user from Authorization header for logging context
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                import jwt
                from app.config import settings
                token = auth_header.split(" ")[1]
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                structlog.contextvars.bind_contextvars(user_id=payload.get("sub"))
            except Exception:
                pass

        start = time.perf_counter()

        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)

            logger.info(
                "request_completed",
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            return response

        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                "request_failed",
                duration_ms=duration_ms,
                exc_info=True,
            )
            raise
