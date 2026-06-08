"""User data access layer.

All DB queries related to users live here.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Repository for User CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, email: str, password_hash: str, display_name: str | None = None) -> User:
        """Create a new user."""
        user = User(
            email=email,
            password_hash=password_hash,
            display_name=display_name,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_id(self, user_id: UUID) -> User | None:
        """Get a user by their UUID."""
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by their email address."""
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_github_id(self, github_id: str) -> User | None:
        """Get a user by their GitHub ID."""
        result = await self.session.execute(select(User).where(User.github_id == github_id))
        return result.scalar_one_or_none()

    async def update(
        self,
        user: User,
        **kwargs: object,
    ) -> User:
        """Update user fields in-place."""
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        await self.session.flush()
        return user

    async def update_hash(self, user: User, new_hash: str) -> User:
        """Update a user's password hash (for rehash-on-login)."""
        user.password_hash = new_hash
        await self.session.flush()
        return user

    async def decrement_credits(self, user_id: UUID, amount: int = 1) -> int:
        """Decrement ai_enhancement_credits by amount, return remaining or negative if exhausted."""
        from sqlalchemy import update

        from app.models.user import User

        result = await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .where(User.ai_enhancement_credits >= amount)  # prevent going below 0
            .values(ai_enhancement_credits=User.ai_enhancement_credits - amount)
            .returning(User.ai_enhancement_credits)
        )
        remaining = result.scalar_one_or_none()
        if remaining is None:
            # Not enough credits or user not found
            return -1
        await self.session.flush()
        return remaining

    async def delete(self, user: User) -> None:
        """Delete a user."""
        await self.session.delete(user)
        await self.session.flush()
