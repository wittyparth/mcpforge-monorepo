"""Pydantic schemas for authentication endpoints."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr
    password: str = Field(..., min_length=12, max_length=128)
    display_name: str | None = Field(None, max_length=100)


class LoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    """Response body after successful authentication."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    display_name: str | None = None


class TokenResponse(BaseModel):
    """Response body containing token info (for debugging; tokens are in cookies)."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
