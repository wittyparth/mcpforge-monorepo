"""Credential data access layer — encrypted API credentials for MCP servers.

All DB queries related to credentials live here.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.credential import Credential


class CredentialRepository:
    """Repository for Credential CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        server_id: UUID,
        user_id: UUID,
        env_var_name: str,
        encrypted_value: bytes,
        auth_scheme: str = "bearer",
        auth_header_name: str | None = None,
        encryption_key_id: str | None = None,
    ) -> Credential:
        """Create a new encrypted credential."""
        cred = Credential(
            server_id=server_id,
            user_id=user_id,
            env_var_name=env_var_name,
            encrypted_value=encrypted_value,
            auth_scheme=auth_scheme,
            auth_header_name=auth_header_name,
            encryption_key_id=encryption_key_id,
        )
        self.session.add(cred)
        await self.session.commit()
        await self.session.refresh(cred)
        return cred

    async def get_by_id(self, cred_id: UUID) -> Credential | None:
        """Get a credential by its UUID."""
        result = await self.session.execute(
            select(Credential).where(Credential.id == cred_id)
        )
        return result.scalar_one_or_none()

    async def get_by_server(self, server_id: UUID) -> list[Credential]:
        """Get all credentials for a server (newest first)."""
        result = await self.session.execute(
            select(Credential)
            .where(Credential.server_id == server_id)
            .order_by(Credential.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_server_and_env(
        self,
        server_id: UUID,
        env_var_name: str,
    ) -> Credential | None:
        """Get a specific credential for a server by env var name."""
        result = await self.session.execute(
            select(Credential).where(
                Credential.server_id == server_id,
                Credential.env_var_name == env_var_name,
            )
        )
        return result.scalar_one_or_none()

    async def delete(self, cred: Credential) -> None:
        """Delete a credential."""
        await self.session.delete(cred)
        await self.session.commit()

    async def rotate(
        self,
        cred: Credential,
        new_encrypted_value: bytes,
        rotated_by: UUID | None = None,
    ) -> Credential:
        """Rotate a credential's encrypted value and update rotation metadata."""
        cred.encrypted_value = new_encrypted_value
        cred.rotated_at = datetime.now(UTC)
        if rotated_by is not None:
            cred.rotated_by = rotated_by
        await self.session.commit()
        await self.session.refresh(cred)
        return cred
