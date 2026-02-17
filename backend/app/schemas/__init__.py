"""Pydantic schemas for User request/response models."""

from datetime import datetime
from pydantic import BaseModel, EmailStr, Field


# --- Request Schemas ---

class UserRegister(BaseModel):
    email: str = Field(..., min_length=5, max_length=255, examples=["user@example.com"])
    username: str = Field(..., min_length=3, max_length=100, examples=["johndoe"])
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str | None = Field(None, max_length=200, examples=["John Doe"])


class UserLogin(BaseModel):
    email: str = Field(..., examples=["user@example.com"])
    password: str = Field(...)


# --- Response Schemas ---

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
