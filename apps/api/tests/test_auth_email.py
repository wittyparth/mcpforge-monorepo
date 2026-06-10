"""Email verification and password-reset endpoint tests (F7 Sub-phase A).

All Redis-dependent functions (rate limiting, single-use token tracking) are
mocked at the module level so tests don't require a running Redis instance.
Email sending is also mocked; tests that verify delivery check mock call counts.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services.auth.email_verification import generate_verification_token
from app.services.auth.hibp import HIBPResult
from app.services.auth.password_reset import _generate_reset_token
from app.services.email_service import EmailResult

FORGOT_URL = "/api/v1/auth/forgot-password"
RESET_URL = "/api/v1/auth/reset-password"
VERIFY_URL = "/api/v1/auth/verify-email"
RESEND_URL = "/api/v1/auth/resend-verification"


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _patch_redis_deps(monkeypatch):
    """Prevent all Redis calls: rate-limiting, single-use token tracking."""
    monkeypatch.setattr(
        "app.services.auth.password_reset._check_rate_limit",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "app.services.auth.password_reset._is_token_used",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(
        "app.services.auth.password_reset._mark_token_used",
        AsyncMock(return_value=None),
    )


@pytest.fixture
def mock_password_reset_email(monkeypatch):
    """Return a mock for ``send_password_reset_email`` for call-count assertions."""
    mock = AsyncMock(return_value=EmailResult(success=True))
    monkeypatch.setattr(
        "app.services.auth.password_reset.send_password_reset_email",
        mock,
    )
    return mock


@pytest.fixture
def mock_verification_email(monkeypatch):
    """Return a mock for ``send_verification_email`` for call-count assertions."""
    mock = AsyncMock(return_value=EmailResult(success=True))
    monkeypatch.setattr(
        "app.services.auth.email_verification.send_verification_email",
        mock,
    )
    return mock


# ── Forgot password ───────────────────────────────────────────────────────────


class TestForgotPassword:
    """``POST /api/v1/auth/forgot-password`` — password reset initiation."""

    @pytest.mark.asyncio
    async def test_returns_200_for_unknown_email(self, client: AsyncClient) -> None:
        """No user enumeration — always returns 200 with the same message shape."""
        response = await client.post(FORGOT_URL, json={"email": "nobody@example.com"})
        assert response.status_code == 200
        data = response.json()
        assert "message" in data

    @pytest.mark.asyncio
    async def test_sends_email_for_known_email(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        mock_password_reset_email: AsyncMock,
    ) -> None:
        """A known email triggers a password-reset email."""
        user = User(
            email="known-user@example.com",
            password_hash="argon2id-placeholder",
        )
        test_session.add(user)
        await test_session.flush()

        response = await client.post(FORGOT_URL, json={"email": "known-user@example.com"})
        assert response.status_code == 200
        mock_password_reset_email.assert_awaited_once()


# ── Reset password ────────────────────────────────────────────────────────────


class TestResetPassword:
    """``POST /api/v1/auth/reset-password`` — password reset completion."""

    @pytest.mark.asyncio
    async def test_reset_with_valid_token_updates_hash(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """A valid token should change the password hash and set ``password_changed_at``."""
        user = User(
            email="reset-test@example.com",
            password_hash="old-hash-placeholder",
        )
        test_session.add(user)
        await test_session.flush()

        token, _ = _generate_reset_token(user.id)
        new_password = "NewSecurePass123!"

        response = await client.post(
            RESET_URL,
            json={"token": token, "password": new_password},
        )
        assert response.status_code == 200

        await test_session.refresh(user)
        assert user.password_hash != "old-hash-placeholder"
        assert user.password_changed_at is not None

    @pytest.mark.asyncio
    async def test_reset_rejects_invalid_token(
        self,
        client: AsyncClient,
    ) -> None:
        """A garbage token should be rejected with 422."""
        response = await client.post(
            RESET_URL,
            json={"token": "this-is-not-a-real-jwt-token", "password": "NewSecurePass123!"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_reset_rejects_expired_token(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """An expired token (1-hour TTL) should be rejected with 422."""
        user = User(
            email="expired-test@example.com",
            password_hash="hash-placeholder",
        )
        test_session.add(user)
        await test_session.flush()

        with freeze_time("2024-01-01 00:00:00 UTC"):
            token, _ = _generate_reset_token(user.id)

        # Advance past the 1-hour expiry window
        with freeze_time("2024-01-01 02:00:00 UTC"):
            response = await client.post(
                RESET_URL,
                json={"token": token, "password": "NewSecurePass123!"},
            )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_reset_rejects_breached_password(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch,
    ) -> None:
        """A password found in HIBP should be rejected with 422."""
        user = User(
            email="hibp-test@example.com",
            password_hash="hash-placeholder",
        )
        test_session.add(user)
        await test_session.flush()

        token, _ = _generate_reset_token(user.id)

        monkeypatch.setattr("app.core.config.settings.HIBP_ENABLED", True)
        monkeypatch.setattr(
            "app.services.auth.hibp.check_password_breached",
            AsyncMock(return_value=HIBPResult(breached=True, count=100)),
        )

        response = await client.post(
            RESET_URL,
            json={"token": token, "password": "BreachedPass123!"},
        )
        assert response.status_code == 422


# ── Email verification ────────────────────────────────────────────────────────


class TestVerifyEmail:
    """``POST /api/v1/auth/verify-email`` — email verification."""

    @pytest.mark.asyncio
    async def test_marks_user_verified(
        self,
        auth_client: AsyncClient,
        auth_user: User,
        test_session: AsyncSession,
    ) -> None:
        """A valid verification token should set ``email_verified = True``."""
        assert auth_user.email_verified is False

        token = generate_verification_token(auth_user.id)

        response = await auth_client.post(VERIFY_URL, json={"token": token})
        assert response.status_code == 200

        await test_session.refresh(auth_user)
        assert auth_user.email_verified is True

    @pytest.mark.asyncio
    async def test_rejects_invalid_token(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """A garbage token should be rejected with 422."""
        response = await auth_client.post(
            VERIFY_URL,
            json={"token": "not-a-valid-verification-token"},
        )
        assert response.status_code == 422


# ── Resend verification ───────────────────────────────────────────────────────


class TestResendVerification:
    """``POST /api/v1/auth/resend-verification`` — regenerate + resend verification email."""

    @pytest.mark.asyncio
    async def test_requires_auth(self, client: AsyncClient) -> None:
        """An unauthenticated request should be rejected with 401."""
        response = await client.post(RESEND_URL)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_sends_email_when_authenticated(
        self,
        auth_client: AsyncClient,
        mock_verification_email: AsyncMock,
    ) -> None:
        """An authenticated request should trigger a verification email."""
        response = await auth_client.post(RESEND_URL)
        assert response.status_code == 200
        mock_verification_email.assert_awaited_once()
