"""API key service (F7 — programmatic access).

Handles creation, authentication, revocation, and scope checking for
API keys. Uses SHA-256 hashing (not bcrypt) because API keys are
high-entropy random strings — bcrypt's work factor would be wasted.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import (
    ForbiddenError,
    NotFoundError,
    PlanLimitExceededError,
    ValidationError,
)
from app.models.api_key import ApiKey
from app.models.user import User
from app.repositories.api_key_repo import ApiKeyRepository
from app.repositories.user_repo import UserRepository


class ApiKeyService:
    """Service for API key CRUD and authentication."""

    PREFIX = "mcpforge_live_"
    VALID_SCOPES: frozenset[str] = frozenset({
        "servers:read",
        "servers:write",
        "analytics:read",
        "admin",
    })
    SCOPE_DESCRIPTIONS: dict[str, str] = {
        "servers:read": "Read server configurations and tools",
        "servers:write": "Create, update, and delete servers",
        "analytics:read": "Read analytics data",
        "admin": "All permissions",
    }

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ApiKeyRepository(session)
        self.user_repo = UserRepository(session)

    async def create_key(
        self,
        user_id: UUID,
        name: str,
        scopes: list[str],
        expires_in_days: int | None = None,
        team_id: UUID | None = None,
    ) -> tuple[ApiKey, str]:
        """Create a new API key.

        Args:
            user_id: The owning user's UUID.
            name: A human-readable label (1-100 chars).
            scopes: List of permission scopes.
            expires_in_days: Optional days until expiry.
            team_id: Optional team to scope the key to.

        Returns:
            Tuple of (ApiKey ORM object, plaintext_key).
            The plaintext is only returned once and cannot be retrieved again.

        Raises:
            ValidationError: If any scope is invalid or name is empty.
            PlanLimitExceededError: If the user has reached the max keys limit.
        """
        if not name or len(name.strip()) == 0:
            raise ValidationError(message="API key name is required")

        invalid_scopes = set(scopes) - self.VALID_SCOPES
        if invalid_scopes:
            raise ValidationError(
                message=f"Invalid scopes: {', '.join(sorted(invalid_scopes))}. "
                f"Valid scopes: {', '.join(sorted(self.VALID_SCOPES))}",
            )

        active_count = await self.repo.count_active_for_user(user_id)
        if active_count >= settings.MAX_API_KEYS_PER_USER:
            raise PlanLimitExceededError(
                message=f"Maximum of {settings.MAX_API_KEYS_PER_USER} API keys reached. "
                "Revoke an existing key or upgrade your plan for more.",
                resource="api_keys",
                current=active_count,
                limit=settings.MAX_API_KEYS_PER_USER,
            )

        random_part = secrets.token_urlsafe(24)
        plaintext = self.PREFIX + random_part

        key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        key_prefix = plaintext[:12]

        expires_at: datetime | None = None
        if expires_in_days is not None:
            expires_at = datetime.now(UTC) + timedelta(days=expires_in_days)

        api_key = await self.repo.create(
            user_id=user_id,
            team_id=team_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes,
            expires_at=expires_at,
        )

        return api_key, plaintext

    async def authenticate(self, plaintext: str) -> User | None:
        """Authenticate a user via an API key.

        Accepts a plaintext API key (e.g. from ``Authorization: Bearer mcpforge_live_...``),
        hashes it, looks up the stored hash, and returns the owning user.

        Args:
            plaintext: The full API key string.

        Returns:
            The owning User, or None if the key is invalid/revoked/expired.
        """
        if not plaintext.startswith(self.PREFIX):
            return None

        key_hash = hashlib.sha256(plaintext.encode()).hexdigest()
        api_key = await self.repo.get_by_hash(key_hash)

        if api_key is None:
            return None

        if api_key.revoked_at is not None:
            return None

        if api_key.expires_at is not None and api_key.expires_at < datetime.now(UTC):
            return None

        try:
            await self.repo.touch(api_key.id)
            await self.session.flush()
        except Exception:
            pass

        user = await self.user_repo.get_by_id(api_key.user_id)
        return user

    @staticmethod
    def check_scope(api_key: ApiKey, required_scope: str) -> bool:
        """Check if an API key has a given scope (or the admin scope).

        Args:
            api_key: The ApiKey object (with scopes loaded).
            required_scope: The scope to check for.

        Returns:
            True if the key has the scope or the ``admin`` scope.
        """
        return required_scope in api_key.scopes or "admin" in api_key.scopes

    async def revoke_key(self, key_id: UUID, user_id: UUID) -> None:
        """Revoke an API key, verifying ownership.

        Args:
            key_id: The API key's UUID.
            user_id: The requesting user's UUID.

        Raises:
            NotFoundError: If the key does not exist.
            ForbiddenError: If the key is not owned by the user.
        """
        api_key = await self.repo.get_by_id(key_id)
        if api_key is None:
            raise NotFoundError(message="API key not found")

        if api_key.user_id != user_id:
            raise ForbiddenError(message="You do not own this API key")

        await self.repo.revoke(key_id)
        await self.session.flush()
