"""GitHub OAuth 2.0 integration.

Handles the OAuth authorization code flow:
1. Generate the GitHub authorization URL with state and scopes.
2. Exchange the authorization code for an access token.
3. Fetch the authenticated user's GitHub profile.
4. Fetch the user's verified primary email.
5. Upsert the user in our database (create, link, or update).

The upsert logic is designed to be idempotent — re-clicking "Sign in with
GitHub" for the same user never creates duplicates.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.exceptions import ConflictError, UnauthorizedError
from app.core.logging import get_logger
from app.repositories.user_repo import UserRepository

if TYPE_CHECKING:
    from collections.abc import Mapping

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

logger = get_logger(__name__)

# GitHub OAuth endpoints
AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
TOKEN_URL = "https://github.com/login/oauth/access_token"
USER_URL = "https://api.github.com/user"
EMAILS_URL = "https://api.github.com/user/emails"

# GitHub API request timeout (seconds)
_HTTP_TIMEOUT = 10


class GitHubOAuth:
    """GitHub OAuth 2.0 authorization code flow.

    All methods are stateless from the class perspective; state management
    across the redirect round-trip is the caller's responsibility (see
    :mod:`app.services.auth.oauth_state`).
    """

    __slots__ = ()

    @staticmethod
    def get_authorization_url(state: str, redirect_uri: str) -> str:
        """Build the GitHub OAuth authorize URL.

        The caller is responsible for generating and storing ``state``
        via :func:`app.services.auth.oauth_state.generate_state` and
        :func:`~app.services.auth.oauth_state.store_state`.

        Args:
            state: Anti-CSRF state token (stored in Redis).
            redirect_uri: Callback URL registered with the GitHub OAuth app.

        Returns:
            Full GitHub authorization URL to redirect the user to.
        """
        params: dict[str, str] = {
            "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": "user:email",
            "state": state,
            "allow_signup": "true",
        }
        return f"{AUTHORIZE_URL}?{urlencode(params)}"

    @staticmethod
    async def exchange_code(code: str, redirect_uri: str) -> Mapping[str, Any]:
        """Exchange an authorization code for an access token.

        POST to GitHub's token endpoint with the code, client credentials,
        and redirect URI. Raises on 4xx/5xx or if the response contains an
        ``error`` field (indicating an expired or invalid code).

        Args:
            code: The authorization code from GitHub's callback.
            redirect_uri: Must match the redirect_uri used in the authorize step.

        Returns:
            The full token response as a dict (contains ``access_token``,
            ``token_type``, ``scope``).

        Raises:
            UnauthorizedError: If GitHub rejects the code (expired, invalid,
                or already used). The error message is sanitized — never
                expose the raw GitHub error to the client.
        """
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                TOKEN_URL,
                json={
                    "client_id": settings.GITHUB_OAUTH_CLIENT_ID,
                    "client_secret": settings.GITHUB_OAUTH_CLIENT_SECRET,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )

            data: dict[str, Any] = response.json()

            if response.status_code >= 400 or "error" in data:
                error_desc = data.get("error_description", data.get("error", "unknown"))
                logger.warning(
                    "github_token_exchange_failed",
                    status_code=response.status_code,
                    error=error_desc,
                )
                raise UnauthorizedError(
                    "Failed to exchange GitHub authorization code. "
                    "The code may have expired or already been used."
                )

            return data

    @staticmethod
    async def get_github_user(access_token: str) -> Mapping[str, Any]:
        """Fetch the authenticated GitHub user's profile.

        Args:
            access_token: The OAuth access token.

        Returns:
            GitHub user dict with keys: ``id``, ``login``, ``avatar_url``,
            ``name``, ``email``, and others.

        Raises:
            UnauthorizedError: If the token is invalid or the API returns 4xx.
        """
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(
                USER_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )

            if response.status_code >= 400:
                logger.warning(
                    "github_user_fetch_failed",
                    status_code=response.status_code,
                )
                raise UnauthorizedError("Failed to fetch GitHub user profile.")

            user_data: dict[str, Any] = response.json()
            return user_data

    @staticmethod
    async def get_primary_email(access_token: str) -> str | None:
        """Fetch the user's primary verified email from GitHub.

        GitHub's ``/user/emails`` endpoint returns all emails associated with
        the account. This method finds the first email that is both primary
        and verified. If none is found, it falls back to the first verified
        email (GitHub allows multiple verified emails).

        Args:
            access_token: The OAuth access token.

        Returns:
            The primary verified email address, or ``None`` if no verified
            email is found.
        """
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(
                EMAILS_URL,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )

            if response.status_code >= 400:
                logger.warning(
                    "github_email_fetch_failed",
                    status_code=response.status_code,
                )
                return None

            emails: list[dict[str, Any]] = response.json()

            # Prefer primary + verified
            for email in emails:
                if email.get("primary") and email.get("verified"):
                    return str(email["email"])

            # Fallback: first verified email
            for email in emails:
                if email.get("verified"):
                    return str(email["email"])

            return None

    @staticmethod
    async def upsert_user(
        session: AsyncSession,
        github_user: Mapping[str, Any],
        email: str,
    ) -> User:
        """Find or create a user from GitHub OAuth data.

        Idempotent upsert logic:
        1. If a user with this ``github_id`` exists → update last_login_at,
           avatar_url, return.
        2. If a user with this ``email`` exists and has no ``github_id`` →
           link the GitHub account (set github_id, avatar_url, mark email
           verified by GitHub).
        3. If a user with this ``email`` exists but has a *different*
           ``github_id`` → raise ConflictError (the email is already linked
           to another GitHub account).
        4. Otherwise → create a new user with an unguessable password hash
           (OAuth-only, no password login possible), email pre-verified.

        Args:
            session: SQLAlchemy async session.
            github_user: GitHub user dict from :meth:`get_github_user`.
            email: Primary verified email from :meth:`get_primary_email`.

        Returns:
            The existing or newly created :class:`User` instance.

        Raises:
            ConflictError: If the email belongs to a user already linked to
                a different GitHub account.
        """
        repo = UserRepository(session)
        github_id = str(github_user["id"])
        now = datetime.now(UTC)

        # 1. Existing user by GitHub ID
        existing = await repo.get_by_github_id(github_id)
        if existing:
            await repo.update(
                existing,
                last_login_at=now,
                avatar_url=github_user.get("avatar_url") or existing.avatar_url,
            )
            logger.info("oauth_github_login", user_id=str(existing.id), via="existing_github_id")
            return existing

        # 2. Existing user by email
        existing = await repo.get_by_email(email)
        if existing:
            if existing.github_id and existing.github_id != github_id:
                logger.warning(
                    "oauth_github_email_conflict",
                    user_id=str(existing.id),
                    existing_github_id=existing.github_id,
                    incoming_github_id=github_id,
                )
                raise ConflictError(
                    "This email is already linked to a different GitHub account. "
                    "Please sign in with the original GitHub account or use "
                    "email/password login."
                )
            await repo.update(
                existing,
                github_id=github_id,
                avatar_url=github_user.get("avatar_url") or existing.avatar_url,
                email_verified=True,
                last_login_at=now,
            )
            logger.info("oauth_github_login", user_id=str(existing.id), via="linked_email")
            return existing

        # 3. Create new user
        import secrets

        user = await repo.create(
            email=email,
            password_hash=f"$oauth${secrets.token_urlsafe(64)}",
            display_name=github_user.get("name") or github_user.get("login"),
        )
        # Set OAuth-specific fields (create only sets email, password_hash, display_name)
        user.github_id = github_id
        user.avatar_url = github_user.get("avatar_url")
        user.email_verified = True
        user.last_login_at = now
        await session.flush()

        logger.info("oauth_github_register", user_id=str(user.id), email=email)
        return user
