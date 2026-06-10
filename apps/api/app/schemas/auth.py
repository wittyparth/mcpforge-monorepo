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


class ForgotPasswordRequest(BaseModel):
    """Request body for initiating a password reset."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request body for completing a password reset."""

    token: str = Field(..., min_length=1)
    password: str = Field(..., min_length=12, max_length=128)


class VerifyEmailRequest(BaseModel):
    """Request body for email verification."""

    token: str = Field(..., min_length=1)


class ResendVerificationRequest(BaseModel):
    """Request body for resending the verification email.

    Currently empty (no parameters needed) — the authenticated user's
    identity is derived from the auth cookie.  This schema exists for
    future extensibility (e.g., a ``target_email`` override for admins).
    """
