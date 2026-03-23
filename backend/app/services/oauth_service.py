"""OAuth service for Google and Microsoft authentication."""

from urllib.parse import urlencode
import httpx
from app.config import settings


def _get_backend_url() -> str:
    """Get the backend URL for OAuth redirects."""
    if settings.BACKEND_URL:
        return settings.BACKEND_URL.rstrip("/")
    # Fallback: derive from ALLOWED_ORIGINS or use default
    return "http://localhost:8000"


class GoogleOAuth:
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    @staticmethod
    def get_auth_url(state: str) -> str:
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": f"{_get_backend_url()}/api/auth/callback/google",
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
        return f"{GoogleOAuth.AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code(code: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GoogleOAuth.TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": f"{_get_backend_url()}/api/auth/callback/google",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def get_user_info(access_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                GoogleOAuth.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15,
            )
            response.raise_for_status()
            return response.json()


class MicrosoftOAuth:
    @staticmethod
    def _tenant() -> str:
        return settings.MICROSOFT_TENANT_ID or "common"

    @classmethod
    def auth_url_base(cls) -> str:
        return f"https://login.microsoftonline.com/{cls._tenant()}/oauth2/v2.0/authorize"

    @classmethod
    def token_url(cls) -> str:
        return f"https://login.microsoftonline.com/{cls._tenant()}/oauth2/v2.0/token"

    USERINFO_URL = "https://graph.microsoft.com/v1.0/me"

    @classmethod
    def get_auth_url(cls, state: str) -> str:
        params = {
            "client_id": settings.MICROSOFT_CLIENT_ID,
            "redirect_uri": f"{_get_backend_url()}/api/auth/callback/microsoft",
            "response_type": "code",
            "scope": "openid email profile User.Read",
            "response_mode": "query",
            "state": state,
        }
        return f"{cls.auth_url_base()}?{urlencode(params)}"

    @classmethod
    async def exchange_code(cls, code: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                cls.token_url(),
                data={
                    "client_id": settings.MICROSOFT_CLIENT_ID,
                    "client_secret": settings.MICROSOFT_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": f"{_get_backend_url()}/api/auth/callback/microsoft",
                    "scope": "openid email profile User.Read",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def get_user_info(access_token: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                MicrosoftOAuth.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=15,
            )
            response.raise_for_status()
            return response.json()
