"""GitHub OAuth endpoint tests (F7 Sub-phase B).

Uses ``respx`` to mock GitHub's OAuth endpoints, and ``monkeypatch``
to patch Redis-dependent state management and settings.

All Redis calls (``store_state``, ``verify_and_consume_state``) are mocked
so tests don't require a running Redis instance.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User

GITHUB_URL = "/api/v1/auth/github"
CALLBACK_URL = "/api/v1/auth/github/callback"

# Test GitHub user data
_GITHUB_USER_ID = 12345678
_GITHUB_LOGIN = "testuser"
_GITHUB_NAME = "Test User"
_GITHUB_AVATAR = "https://avatars.githubusercontent.com/u/12345678"

_MOCK_GITHUB_USER = {
    "id": _GITHUB_USER_ID,
    "login": _GITHUB_LOGIN,
    "name": _GITHUB_NAME,
    "avatar_url": _GITHUB_AVATAR,
    "email": "github-primary@example.com",
}

_MOCK_TOKEN_RESPONSE = {
    "access_token": "gho_test_token",
    "token_type": "bearer",
    "scope": "user:email",
}

_MOCK_VERIFIED_EMAIL = {
    "email": "github-primary@example.com",
    "primary": True,
    "verified": True,
}
_MOCK_ALREADY_LINKED_EMAIL = {
    "email": "already-linked@example.com",
    "primary": True,
    "verified": True,
}


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _configure_github_oauth(monkeypatch) -> None:
    """Activate GitHub OAuth settings for all tests in this file.

    Tests that need the unconfigured state override with monkeypatch.
    """
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(
        settings,
        "GITHUB_OAUTH_REDIRECT_URI",
        "http://test/api/v1/auth/github/callback",
    )


@pytest.fixture(autouse=True)
def _patch_oauth_state(monkeypatch) -> None:
    """Mock Redis-backed OAuth state management for all tests.

    - ``generate_state`` returns a predictable token.
    - ``store_state`` is a no-op.
    - ``verify_and_consume_state`` returns ``True`` by default.
    Individual tests override ``verify_and_consume_state`` to test
    rejection paths.
    """
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.generate_state",
        MagicMock(return_value="test-state-token"),
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.store_state",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.verify_and_consume_state",
        AsyncMock(return_value=True),
    )


@pytest.fixture
def _mock_github_apis(request: pytest.FixtureRequest) -> None:
    """Mock all three GitHub API endpoints used in the callback flow.

    Individual tests can override individual routes after calling this
    fixture by using ``respx.mock`` *inside* the test and re-registering
    specific routes (respx allows route re-registration within the same
    mock context).
    """
    respx.post("https://github.com/login/oauth/access_token").mock(
        return_value=httpx.Response(200, json=_MOCK_TOKEN_RESPONSE),
    )
    respx.get("https://api.github.com/user").mock(
        return_value=httpx.Response(200, json=_MOCK_GITHUB_USER),
    )
    respx.get("https://api.github.com/user/emails").mock(
        return_value=httpx.Response(
            200,
            json=[{"email": "github-primary@example.com", "primary": True, "verified": True}],
        ),
    )


# ── Start OAuth flow ──


class TestGitHubOAuthStart:
    """``GET /api/v1/auth/github`` — OAuth initiation."""

    @pytest.mark.asyncio
    async def test_redirects_to_github(self, client: AsyncClient) -> None:
        """A GET request should redirect to GitHub's authorization URL."""
        response = await client.get(GITHUB_URL, follow_redirects=False)
        assert response.status_code in (302, 307)
        location = response.headers.get("location", "")
        assert "https://github.com/login/oauth/authorize" in location

    @pytest.mark.asyncio
    async def test_get_authorization_url_includes_state_and_scope(
        self,
        client: AsyncClient,
    ) -> None:
        """The authorization URL must contain state, scope, and redirect_uri."""
        response = await client.get(GITHUB_URL, follow_redirects=False)
        location = response.headers.get("location", "")
        assert "state=test-state-token" in location
        assert "scope=" in location
        assert "redirect_uri=" in location
        assert "client_id=test-client-id" in location

    @pytest.mark.asyncio
    async def test_get_authorization_url_503_when_not_configured(
        self,
        client: AsyncClient,
        monkeypatch,
    ) -> None:
        """If GITHUB_OAUTH_CLIENT_ID is empty, the endpoint must return 503."""
        monkeypatch.setattr(settings, "GITHUB_OAUTH_CLIENT_ID", "")
        response = await client.get(GITHUB_URL)
        assert response.status_code == 503


# ── OAuth callback ──


class TestGitHubOAuthCallback:
    """``GET /api/v1/auth/github/callback`` — OAuth callback handling."""

    # ── Error paths ──

    @pytest.mark.asyncio
    async def test_callback_rejects_missing_code(
        self,
        client: AsyncClient,
    ) -> None:
        """Missing ``code`` query param must redirect with ``missing_code``."""
        response = await client.get(
            f"{CALLBACK_URL}?state=test-state",
            follow_redirects=False,
        )
        assert response.status_code in (302, 307)
        assert "oauth=error=missing_code" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_callback_rejects_invalid_state(
        self,
        client: AsyncClient,
        monkeypatch,
    ) -> None:
        """Invalid or consumed state must redirect with ``invalid_state``."""
        monkeypatch.setattr(
            "app.api.v1.endpoints.auth.verify_and_consume_state",
            AsyncMock(return_value=False),
        )
        response = await client.get(
            f"{CALLBACK_URL}?code=testcode&state=bad-state",
            follow_redirects=False,
        )
        assert response.status_code in (302, 307)
        assert "oauth=error=invalid_state" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_exchange_code_handles_github_400(
        self,
        client: AsyncClient,
    ) -> None:
        """A 4xx from GitHub's token endpoint must redirect with ``exchange_failed``."""
        with respx.mock:
            respx.post("https://github.com/login/oauth/access_token").mock(
                return_value=httpx.Response(
                    400,
                    json={
                        "error": "bad_verification_code",
                        "error_description": "The code passed is incorrect or expired.",
                    },
                ),
            )

            response = await client.get(
                f"{CALLBACK_URL}?code=expired-code&state=test-state",
                follow_redirects=False,
            )

        assert response.status_code in (302, 307)
        location = response.headers.get("location", "")
        assert "oauth=error=exchange_failed" in location

    @pytest.mark.asyncio
    async def test_callback_no_email_returns_redirect(
        self,
        client: AsyncClient,
    ) -> None:
        """If GitHub returns no verified email, must redirect with ``no_email``."""
        with respx.mock:
            respx.post("https://github.com/login/oauth/access_token").mock(
                return_value=httpx.Response(200, json=_MOCK_TOKEN_RESPONSE),
            )
            respx.get("https://api.github.com/user").mock(
                return_value=httpx.Response(
                    200,
                    json={"id": 9999, "login": "noemailuser", "name": None, "email": None},
                ),
            )
            # No verified emails and no public email.
            respx.get("https://api.github.com/user/emails").mock(
                return_value=httpx.Response(200, json=[]),
            )

            response = await client.get(
                f"{CALLBACK_URL}?code=testcode&state=test-state",
                follow_redirects=False,
            )

        assert response.status_code in (302, 307)
        location = response.headers.get("location", "")
        assert "oauth=error=no_email" in location

    # ── User creation / linking ──

    @pytest.mark.asyncio
    async def test_callback_creates_new_user_on_first_login(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """A first-time GitHub user should be created in the database."""
        with respx.mock:
            respx.post("https://github.com/login/oauth/access_token").mock(
                return_value=httpx.Response(200, json=_MOCK_TOKEN_RESPONSE),
            )
            respx.get("https://api.github.com/user").mock(
                return_value=httpx.Response(200, json=_MOCK_GITHUB_USER),
            )
            respx.get("https://api.github.com/user/emails").mock(
                return_value=httpx.Response(
                    200,
                    json=[_MOCK_VERIFIED_EMAIL],
                ),
            )

            response = await client.get(
                f"{CALLBACK_URL}?code=testcode&state=test-state",
                follow_redirects=False,
            )

        assert response.status_code in (302, 307)
        assert "oauth=success" in response.headers.get("location", "")

        # Cookies must be set
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

        # Verify user was created
        from app.repositories.user_repo import UserRepository

        repo = UserRepository(test_session)
        user = await repo.get_by_github_id(str(_GITHUB_USER_ID))
        assert user is not None
        assert user.email == "github-primary@example.com"
        assert user.email_verified is True
        assert user.display_name == _GITHUB_NAME
        assert user.avatar_url == _GITHUB_AVATAR

    @pytest.mark.asyncio
    async def test_callback_links_existing_user_by_email(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """An existing user with matching email should have their GitHub ID linked."""
        existing = User(
            email="github-primary@example.com",
            password_hash="existing-hash",
            display_name="Existing User",
        )
        test_session.add(existing)
        await test_session.flush()
        existing_id = existing.id

        with respx.mock:
            respx.post("https://github.com/login/oauth/access_token").mock(
                return_value=httpx.Response(200, json=_MOCK_TOKEN_RESPONSE),
            )
            respx.get("https://api.github.com/user").mock(
                return_value=httpx.Response(200, json=_MOCK_GITHUB_USER),
            )
            respx.get("https://api.github.com/user/emails").mock(
                return_value=httpx.Response(
                    200,
                    json=[_MOCK_VERIFIED_EMAIL],
                ),
            )

            response = await client.get(
                f"{CALLBACK_URL}?code=testcode&state=test-state",
                follow_redirects=False,
            )

        assert response.status_code in (302, 307)
        assert "oauth=success" in response.headers.get("location", "")

        # Must be the same user (not duplicated)
        await test_session.refresh(existing)
        assert existing.github_id == str(_GITHUB_USER_ID)
        assert existing.email_verified is True
        assert existing.display_name == "Existing User"  # Kept the name
        # Should have been linked, not re-created
        from app.repositories.user_repo import UserRepository

        repo = UserRepository(test_session)
        same_user = await repo.get_by_github_id(str(_GITHUB_USER_ID))
        assert same_user is not None
        assert same_user.id == existing_id

    @pytest.mark.asyncio
    async def test_callback_returns_existing_github_user(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ) -> None:
        """A user already linked to this GitHub ID should log in (no duplicate)."""
        existing = User(
            email="already-linked@example.com",
            password_hash="some-hash",
            github_id=str(_GITHUB_USER_ID),
            display_name="Old Name",
        )
        test_session.add(existing)
        await test_session.flush()

        with respx.mock:
            respx.post("https://github.com/login/oauth/access_token").mock(
                return_value=httpx.Response(200, json=_MOCK_TOKEN_RESPONSE),
            )
            respx.get("https://api.github.com/user").mock(
                return_value=httpx.Response(200, json=_MOCK_GITHUB_USER),
            )
            respx.get("https://api.github.com/user/emails").mock(
                return_value=httpx.Response(
                    200,
                    json=[_MOCK_ALREADY_LINKED_EMAIL],
                ),
            )

            response = await client.get(
                f"{CALLBACK_URL}?code=testcode&state=test-state",
                follow_redirects=False,
            )

        assert response.status_code in (302, 307)
        assert "oauth=success" in response.headers.get("location", "")

        # Exactly one user with this github_id
        from app.repositories.user_repo import UserRepository

        repo = UserRepository(test_session)
        user = await repo.get_by_github_id(str(_GITHUB_USER_ID))
        assert user is not None
        assert user.id == existing.id
        # Avatar should have been updated from GitHub
        assert user.avatar_url == _GITHUB_AVATAR

    @pytest.mark.asyncio
    async def test_callback_consumes_state_atomically(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch,
    ) -> None:
        """The same state token must not be usable twice (GETDEL semantics)."""
        call_count = 0

        async def mock_verify(redis: object, state: str) -> bool:
            nonlocal call_count
            call_count += 1
            return call_count == 1  # first succeeds, second fails

        monkeypatch.setattr(
            "app.api.v1.endpoints.auth.verify_and_consume_state",
            mock_verify,
        )

        with respx.mock:
            respx.post("https://github.com/login/oauth/access_token").mock(
                return_value=httpx.Response(200, json=_MOCK_TOKEN_RESPONSE),
            )
            respx.get("https://api.github.com/user").mock(
                return_value=httpx.Response(200, json=_MOCK_GITHUB_USER),
            )
            respx.get("https://api.github.com/user/emails").mock(
                return_value=httpx.Response(
                    200,
                    json=[{"email": "replay-test@example.com", "primary": True, "verified": True}],
                ),
            )

            # First call — succeeds
            resp1 = await client.get(
                f"{CALLBACK_URL}?code=code1&state=same-state",
                follow_redirects=False,
            )
            assert resp1.status_code in (302, 307)
            assert "oauth=success" in resp1.headers.get("location", "")

            # Second call with same state — must fail (state already consumed)
            resp2 = await client.get(
                f"{CALLBACK_URL}?code=code2&state=same-state",
                follow_redirects=False,
            )
            assert resp2.status_code in (302, 307)
            assert "oauth=error=invalid_state" in resp2.headers.get("location", "")
