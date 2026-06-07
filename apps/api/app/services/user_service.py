"""User management business logic."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repo import UserRepository


class UserService:
    """Service-layer logic for user profile operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.user_repo = UserRepository(session)

    async def get_profile(self, user_id: UUID) -> object:
        """Get a user's public profile."""
        return await self.user_repo.get_by_id(user_id)

    async def update_profile(
        self,
        user_id: UUID,
        display_name: str | None = None,
        avatar_url: str | None = None,
    ) -> object:
        """Update a user's profile fields."""
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            # This shouldn't happen if `get_current_user` already validated
            from app.core.exceptions import NotFoundError
            raise NotFoundError("User not found")

        kwargs: dict[str, object] = {}
        if display_name is not None:
            kwargs["display_name"] = display_name
        if avatar_url is not None:
            kwargs["avatar_url"] = avatar_url

        return await self.user_repo.update(user, **kwargs)
