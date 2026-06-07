"""Authentication endpoint tests."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
REFRESH_URL = "/api/v1/auth/refresh"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123!"
TEST_DISPLAY = "Test User"


@pytest.mark.asyncio
async def test_register(client: AsyncClient) -> None:
    """POST /api/v1/auth/register should create a user and set cookies."""
    response = await client.post(
        REGISTER_URL,
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD, "display_name": TEST_DISPLAY},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_EMAIL
    assert data["display_name"] == TEST_DISPLAY
    assert "id" in data

    # Should have auth cookies
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    """POST /api/v1/auth/register with an existing email should fail."""
    # First registration
    await client.post(
        REGISTER_URL,
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )

    # Duplicate registration
    response = await client.post(
        REGISTER_URL,
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login(client: AsyncClient) -> None:
    """POST /api/v1/auth/login should authenticate and set cookies."""
    # Register first
    await client.post(
        REGISTER_URL,
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )

    # Login
    response = await client.post(
        LOGIN_URL,
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_EMAIL

    # Should have auth cookies
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient) -> None:
    """POST /api/v1/auth/login with wrong password should fail."""
    await client.post(
        REGISTER_URL,
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )

    response = await client.post(
        LOGIN_URL,
        json={"email": TEST_EMAIL, "password": "wrongpassword123!"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient) -> None:
    """GET /api/v1/auth/me should return the current user."""
    # Register and login
    reg_response = await client.post(
        REGISTER_URL,
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    access_token = reg_response.cookies.get("access_token")

    # Access /me with cookies
    response = await client.get(
        ME_URL,
        cookies={"access_token": access_token},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == TEST_EMAIL
    assert data["plan"] == "free"
    assert data["ai_enhancement_credits"] == 3


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient) -> None:
    """GET /api/v1/auth/me without auth should fail."""
    response = await client.get(ME_URL)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_logout(client: AsyncClient) -> None:
    """POST /api/v1/auth/logout should clear cookies."""
    response = await client.post(LOGOUT_URL)
    assert response.status_code == 200
    # Cookies should be cleared (set to empty with max_age=0)
    assert response.json() == {"message": "Logged out successfully"}
