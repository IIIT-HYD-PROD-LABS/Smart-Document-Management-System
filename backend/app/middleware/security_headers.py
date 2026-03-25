"""Security headers middleware -- adds defence-in-depth HTTP headers."""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Append security-related headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # Clickjacking protection
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME-type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS filter (legacy browsers)
        response.headers["X-XSS-Protection"] = "0"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (disable sensitive browser APIs)
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        # CSP frame-ancestors only for the API (full CSP belongs on the frontend)
        response.headers["Content-Security-Policy"] = "frame-ancestors 'none'"

        # Cross-origin headers: allow frontend (different origin) to read API responses
        response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"

        # Restrict cross-domain policy files
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # Prevent caching of sensitive API responses
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"

        # HSTS -- only in production (DEBUG=False)
        if not settings.DEBUG:
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains; preload"
            )

        return response
