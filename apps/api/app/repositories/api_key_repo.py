"""API key data access layer.

All DB queries related to API keys live here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey


class ApiKeyRepository:
    """Repository for ApiKey CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        user_id: UUID,
        team_id: UUID | None,
        name: str,
        key_prefix: str,
        key_hash: str,
        scopes: list[str],
        expires_at: datetime | None = None,
    ) -> ApiKey:
        """Create a new API key."""
        api_key = ApiKey(
            user_id=user_id,
            team_id=team_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes,
            expires_at=expires_at,
        )
        self.session.add(api_key)
        await self.session.flush()
        return api_key

    async def list_for_user(
        self,
        user_id: UUID,
        include_revoked: bool = False,
    ) -> list[ApiKey]:
        """List API keys for a user.

        Args:
            user_id: The user's UUID.
            include_revoked: If True, include revoked keys.

        Returns:
            List of ApiKey objects ordered by creation date descending.
        """
        stmt = (
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .order_by(ApiKey.created_at.desc())
        )
        if not include_revoked:
            stmt = stmt.where(ApiKey.revoked_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, key_id: UUID) -> ApiKey | None:
        """Get an API key by its UUID."""
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.id == key_id)
        )
        return result.scalar_one_or_none()

    async def get_by_hash(self, key_hash: str) -> ApiKey | None:
        """Get an API key by its SHA-256 hash.

        Used during authentication.
        """
        result = await self.session.execute(
            select(ApiKey).where(ApiKey.key_hash == key_hash)
        )
        return result.scalar_one_or_none()

    async def touch(self, key_id: UUID) -> None:
        """Update last_used_at to now (fire and forget)."""
        await self.session.execute(
            update(ApiKey)
            .where(ApiKey.id == key_id)
            .values(last_used_at=datetime.now(UTC))
        )
        await self.session.flush()

    async def revoke(self, key_id: UUID) -> None:
        """Set revoked_at to now."""
        await self.session.execute(
            update(ApiKey)
            .where(ApiKey.id == key_id)
            .values(revoked_at=datetime.now(UTC))
        )
        await self.session.flush()

    async def list_for_team(
        self,
        team_id: UUID,
        include_revoked: bool = False,
    ) -> list[ApiKey]:
        """List API keys for a team.

        Args:
            team_id: The team's UUID.
            include_revoked: If True, include revoked keys.

        Returns:
            List of ApiKey objects ordered by creation date descending.
        """
        stmt = (
            select(ApiKey)
            .where(ApiKey.team_id == team_id)
            .order_by(ApiKey.created_at.desc())
        )
        if not include_revoked:
            stmt = stmt.where(ApiKey.revoked_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_active_for_user(self, user_id: UUID) -> int:
        """Count active (non-revoked) API keys for a user.

        Used for plan limit enforcement.
        """
        stmt = (
            select(ApiKey)
            .where(ApiKey.user_id == user_id)
            .where(ApiKey.revoked_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return len(result.scalars().all())
