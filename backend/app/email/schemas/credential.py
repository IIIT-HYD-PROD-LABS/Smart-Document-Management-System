"""GmailCredential Pydantic schemas — Phase 15 EMAIL-01, EMAIL-03.

Security boundary: GmailCredentialResponse omits refresh_token_enc and
scopes (Fernet ciphertext + scope string are server-side internals).
GmailCredentialCreate accepts plaintext refresh_token; the service layer
encrypts before persisting.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class GmailCredentialResponse(BaseModel):
    """Read-only view of a GmailCredential row. Never exposes refresh token."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    google_account_email: Optional[str] = None
    status: str
    cadence_minutes: int
    last_scan_at: Optional[datetime] = None
    created_at: datetime


class GmailCredentialUpdate(BaseModel):
    """Mutable subset for PATCH. cadence_minutes constrained to 5..1440 per D-10."""

    cadence_minutes: Optional[int] = Field(default=None, ge=5, le=1440)


class GmailCredentialCreate(BaseModel):
    """OAuth callback payload. refresh_token is plaintext here; encrypted on persist."""

    google_account_email: Optional[str] = None
    refresh_token: str
    scopes: Optional[str] = None
