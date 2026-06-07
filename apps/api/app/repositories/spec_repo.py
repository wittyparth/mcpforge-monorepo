"""Spec source data access layer (F1 — OpenAPI ingestion).

All DB queries related to OpenAPI spec sources live here.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.spec import SpecSource


class SpecRepository:
    """Repository for SpecSource CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: UUID,
        source_type: str,
        source_url: str | None = None,
        r2_key: str | None = None,
        title: str | None = None,
        version: str | None = None,
        openapi_version: str | None = None,
        endpoint_count: int | None = None,
        spec_size_bytes: int | None = None,
    ) -> SpecSource:
        """Create a new spec source record."""
        spec = SpecSource(
            user_id=user_id,
            source_type=source_type,
            source_url=source_url,
            r2_key=r2_key,
            title=title,
            version=version,
            openapi_version=openapi_version,
            endpoint_count=endpoint_count,
            spec_size_bytes=spec_size_bytes,
        )
        self.session.add(spec)
        await self.session.commit()
        await self.session.refresh(spec)
        return spec

    async def get_by_id(self, spec_id: UUID) -> SpecSource | None:
        """Get a spec source by its UUID."""
        result = await self.session.execute(
            select(SpecSource).where(SpecSource.id == spec_id)
        )
        return result.scalar_one_or_none()

    async def get_by_user_and_hash(
        self, user_id: UUID, sha256: str
    ) -> SpecSource | None:
        """Find a spec by user ID and SHA-256 hash of its content.

        The r2_key is namespaced as ``{user_id}/{sha256}.json`` so we match
        on the prefix pattern.
        """
        result = await self.session.execute(
            select(SpecSource).where(
                SpecSource.user_id == user_id,
                SpecSource.r2_key.like(f"{user_id}/{sha256}%"),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self,
        user_id: UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> list[SpecSource]:
        """List specs belonging to a user (paginated, newest first)."""
        result = await self.session.execute(
            select(SpecSource)
            .where(SpecSource.user_id == user_id)
            .order_by(SpecSource.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        spec: SpecSource,
        status: str,
        error: str | None = None,
    ) -> SpecSource:
        """Update a spec source's fetch status and optional error message."""
        spec.fetch_status = status
        if error is not None:
            spec.fetch_error = error
        await self.session.commit()
        await self.session.refresh(spec)
        return spec

    async def delete(self, spec: SpecSource) -> None:
        """Delete a spec source."""
        await self.session.delete(spec)
        await self.session.commit()
