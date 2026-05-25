"""Pydantic schemas for User request/response models."""

import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# --- Request Schemas ---

class UserRegister(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, examples=["user@example.com"])
    username: str = Field(..., min_length=3, max_length=100, examples=["johndoe"])
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(None, max_length=200, examples=["John Doe"])
    # JWT from an approved early-access invitation. Required for all
    # registrations after the first (bootstrap) user; otherwise the
    # early-access gate is decorative and trivially bypassed.
    invitation_token: str | None = Field(None, max_length=2048)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, v):
            raise ValueError("Invalid email format")
        return v.lower()

    @field_validator("username")
    @classmethod
    def validate_username_chars(cls, v: str) -> str:
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$', v):
            raise ValueError("Username must start with a letter or number and may only contain letters, numbers, hyphens, and underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        if not re.search(r'[A-Z]', v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r'[a-z]', v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r'[0-9]', v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]', v):
            raise ValueError("Password must contain at least one special character")
        return v

    @field_validator("full_name")
    @classmethod
    def sanitize_full_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        sanitized = re.sub(r'<[^>]*>', '', v)
        sanitized = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', sanitized)
        return sanitized.strip()


class UserLogin(BaseModel):
    email: str = Field(..., min_length=1, examples=["user@example.com"])
    password: str = Field(..., min_length=1)

    @field_validator("email")
    @classmethod
    def normalize_login_email(cls, v: str) -> str:
        return v.strip().lower()


# --- Response Schemas ---

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str | None
    is_active: bool
    role: str
    created_at: datetime
    mfa_enabled: bool = False

    @field_validator("mfa_enabled", mode="before")
    @classmethod
    def _coerce_mfa_enabled(cls, v):
        # A freshly-constructed (unflushed) User has mfa_enabled=None: the DB
        # default applies on INSERT, not on Python object construction. Treat
        # that as the default False rather than failing bool validation.
        return False if v is None else v

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenPairResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- MFA (TOTP) schemas ---

class MfaChallengeResponse(BaseModel):
    """Returned by /login when the password is correct but the account has MFA.
    The client exchanges ``mfa_token`` + a TOTP/backup code at /auth/mfa/verify."""
    mfa_required: bool = True
    mfa_token: str


class MfaVerifyRequest(BaseModel):
    mfa_token: str = Field(..., min_length=1)
    code: str = Field(..., min_length=6, max_length=32)  # 6-digit TOTP or a backup code

    @field_validator("code")
    @classmethod
    def _strip_code(cls, v: str) -> str:
        return v.strip()


class TotpEnrollResponse(BaseModel):
    """Enrollment material, shown once. MFA is inactive until /totp/confirm."""
    secret: str
    otpauth_uri: str
    qr_data_uri: str


class TotpConfirmRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class MfaDisableRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=32)


class BackupCodesResponse(BaseModel):
    backup_codes: list[str]


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class OAuthExchangeRequest(BaseModel):
    code: str = Field(..., min_length=1)
    token: str = Field(..., min_length=1)


class AcceptInviteRequest(BaseModel):
    """Typed body for POST /api/auth/accept-invite.

    Replaces the previous untyped dict so the password is bounded at the
    API boundary (defense-in-depth alongside invitation_service's check)
    and OpenAPI consumers see real field documentation.
    """
    token: str = Field(..., min_length=1, max_length=2048)
    password: str = Field(..., min_length=12, max_length=128)


class ForgotPasswordRequest(BaseModel):
    """Body for POST /api/auth/forgot-password. Caller-side intake only."""

    email: str = Field(..., min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ResetPasswordRequest(BaseModel):
    """Body for POST /api/auth/reset-password.

    Same complexity floor as the registration form so a reset cannot
    bypass the password policy advertised on the admin Security page.
    """

    token: str = Field(..., min_length=1, max_length=2048)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def _validate_complexity(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\\/~`]', v):
            raise ValueError("Password must contain at least one special character")
        return v
