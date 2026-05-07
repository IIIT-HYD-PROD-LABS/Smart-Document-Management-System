"""Gmail OAuth web-server flow — Phase 15 EMAIL-01.

Separate from login GoogleOAuth (different scopes, different side effects).
Pitfall 7: access_type=offline + prompt=consent reliably yields a refresh
token on every connection round, including reconnect-after-disconnect.
"""
from __future__ import annotations

from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from app.config import settings


class GmailOAuth:
    AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.modify",
    ]

    @staticmethod
    def get_auth_url(state: str, redirect_uri: str) -> str:
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GmailOAuth.SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "state": state,
        }
        return f"{GmailOAuth.AUTH_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code(code: str, redirect_uri: str) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                GmailOAuth.TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )
        if resp.status_code != 200:
            raise HTTPException(
                400, f"OAuth token exchange failed: {resp.text[:200]}"
            )
        data = resp.json()
        if "refresh_token" not in data:
            raise HTTPException(
                400,
                "No refresh token returned. Disconnect Gmail in Google account "
                "(myaccount.google.com/permissions) and reconnect.",
            )
        return data
