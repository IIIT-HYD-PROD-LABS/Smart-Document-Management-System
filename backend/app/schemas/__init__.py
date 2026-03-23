"""Pydantic schemas for User request/response models."""

import re
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# --- Request Schemas ---

class UserRegister(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, examples=["user@example.com"])
    username: str = Field(..., min_length=3, max_length=100, examples=["johndoe"])
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str | None = Field(None, max_length=200, examples=["John Doe"])

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
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Username may only contain letters, numbers, hyphens, and underscores")
        return v


class UserLogin(BaseModel):
    email: str = Field(..., min_length=1, examples=["user@example.com"])
    password: str = Field(..., min_length=1)


# --- Response Schemas ---

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str | None
    is_active: bool
    role: str
    created_at: datetime

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


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)


class OAuthExchangeRequest(BaseModel):
    code: str = Field(..., min_length=1)
    token: str = Field(..., min_length=1)
