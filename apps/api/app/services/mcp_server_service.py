"""MCP server management business logic."""

from __future__ import annotations

import copy
import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.logging import get_logger
from app.models.mcp_server import MCPServer
from app.models.server_version import ServerVersion
from app.repositories.mcp_server_repo import MCPServerRepository
from app.repositories.team_repo import TeamRepository
from app.repositories.user_repo import UserRepository
from app.services.billing.plan_limits import check_plan_limit
from app.services.team_service import ROLE_HIERARCHY

logger = get_logger(__name__)

_SLUGIFY_REGEX = re.compile(r"[^a-z0-9\s-]")
_SLUGIFY_WS_REGEX = re.compile(r"[\s_]+")
_SLUGIFY_HYPHEN_REGEX = re.compile(r"-+")


def _slugify(name: str, max_length: int = 50) -> str:
    """Convert a name into a URL-safe kebab-case slug."""
    slug = name.lower()
    slug = _SLUGIFY_REGEX.sub("", slug)
    slug = _SLUGIFY_WS_REGEX.sub("-", slug)
    slug = _SLUGIFY_HYPHEN_REGEX.sub("-", slug)
    slug = slug.strip("-")
    return slug[:max_length] or "server"


class MCPServerService:
    """Service-layer logic for MCP server CRUD operations.

    Team-aware: servers may be owned directly (via ``user_id``) or owned
    by a team (via ``team_id``). Team-owned servers require the caller
    to have the appropriate role (viewer for read, editor for write,
    admin for delete).
    """

    def __init__(self, session: AsyncSession) -> None:
        self.server_repo = MCPServerRepository(session)
        self.user_repo = UserRepository(session)
        self.team_repo = TeamRepository(session)

    async def _check_team_permission(
        self, user_id: UUID, team_id: UUID, required_role: str
    ) -> bool:
        """Check if a user has at least ``required_role`` in a team.

        Returns ``True`` if the user has sufficient permissions.
        """
        membership = await self.team_repo.get_membership(team_id, user_id)
        if not membership:
            return False
        user_level = ROLE_HIERARCHY.get(membership.role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 0)
        return user_level >= required_level

    async def get_server_with_access_check(
        self,
        server_id: UUID,
        user_id: UUID,
        required_role: str = "viewer",
    ) -> MCPServer:
        """Get a server and verify the user has at least the required role.

        If the server has a ``team_id``, checks team permissions. Otherwise
        falls back to direct ownership.
        """
        server = await self.get_server(server_id)
        if server.team_id:
            if not await self._check_team_permission(user_id, server.team_id, required_role):
                raise ForbiddenError(
                    "You do not have sufficient permissions for this server"
                )
        elif server.user_id != user_id:
            raise ForbiddenError("You do not own this server")
        return server

    async def create_server(
        self,
        user_id: UUID,
        slug: str,
        name: str,
        base_url: str,
        description: str | None = None,
        spec_url: str | None = None,
        auth_scheme: str = "none",
        auth_header_name: str | None = None,
        tools_config: dict[str, Any] | None = None,
        transport_mode: str = "sse",
        team_id: UUID | None = None,
    ) -> MCPServer:
        """Create a new MCP server.

        If ``team_id`` is provided, the server will be owned by the team
        (the team must exist and the user must be a member). When the user
        belongs to a team and no ``team_id`` is given, the server is
        created under the user's personal ownership.

        Raises:
            ConflictError: If the slug is already taken.
        """
        existing = await self.server_repo.get_by_slug(slug)
        if existing:
            raise ConflictError(f"Slug '{slug}' is already in use")

        user = await self.user_repo.get_by_id(user_id)
        if user:
            count = await self.server_repo.count_by_user(user_id)
            check_plan_limit(user.plan, "servers", count)

        return await self.server_repo.create(
            user_id=user_id,
            slug=slug,
            name=name,
            base_url=base_url,
            description=description,
            spec_url=spec_url,
            auth_scheme=auth_scheme,
            auth_header_name=auth_header_name,
            tools_config=tools_config,
            transport_mode=transport_mode,
            team_id=team_id,
        )

    async def get_server(self, server_id: UUID) -> MCPServer:
        """Get a server by ID.

        Raises:
            NotFoundError: If the server doesn't exist.
        """
        server = await self.server_repo.get_by_id(server_id)
        if not server:
            raise NotFoundError("Server not found")
        return server

    async def get_server_by_slug(self, slug: str) -> MCPServer:
        """Get a server by slug.

        Raises:
            NotFoundError: If the server doesn't exist.
        """
        server = await self.server_repo.get_by_slug(slug)
        if not server:
            raise NotFoundError("Server not found")
        return server

    async def list_user_servers(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[MCPServer]:
        """List servers for a user, including team-owned servers."""
        team_ids = await self.team_repo.get_user_team_ids(user_id)
        return await self.server_repo.list_by_user_or_team(
            user_id, team_ids, skip=skip, limit=limit
        )

    async def _create_version_snapshot(
        self,
        server: MCPServer,
        changed_by: UUID | None = None,
        change_note: str | None = None,
    ) -> ServerVersion:
        """Snapshot the current server config into a ServerVersion row.

        This captures the state *before* a mutation so that it can be
        restored via rollback.
        """
        version = ServerVersion(
            server_id=server.id,
            version=server.version,
            tools_config=copy.deepcopy(server.tools_config),
            changed_by=changed_by,
            change_note=change_note,
        )
        self.server_repo.session.add(version)
        await self.server_repo.session.flush()
        return version

    async def update_server(
        self,
        server_id: UUID,
        user_id: UUID,
        **kwargs: object,
    ) -> MCPServer:
        """Update a server, verifying ownership or team editor+ permissions.

        Before applying the update, the current state is snapshotted into
        a ``ServerVersion`` row so the change is reversible via rollback.
        After a successful update the server's cached configuration is
        invalidated so subsequent gateway requests pick up the new state.

        Raises:
            NotFoundError: If the server doesn't exist.
            ForbiddenError: If the user doesn't have sufficient permissions.
        """
        server = await self.get_server(server_id)
        if server.team_id:
            if not await self._check_team_permission(user_id, server.team_id, "editor"):
                raise ForbiddenError("You do not have permission to update this server")
        elif server.user_id != user_id:
            raise ForbiddenError("You do not own this server")

        # Snapshot current state before mutating
        await self._create_version_snapshot(
            server,
            changed_by=user_id,
            change_note="Updated via API",
        )

        updated = await self.server_repo.update(server, **kwargs)

        # Increment version after successful update
        updated.version = (updated.version or 1) + 1
        await self.server_repo.session.flush()

        # Invalidate the server config cache so the gateway picks up
        # the new state (status, tools_config, etc.) on the next request.
        if kwargs:
            try:
                from redis.asyncio import Redis

                from app.core.redis import get_redis_pool
                from app.services.server_config_cache import ServerConfigCache

                pool = await get_redis_pool()
                redis = Redis.from_pool(pool)
                await ServerConfigCache.invalidate(updated.slug, redis)
                await redis.close()
            except Exception:
                logger.warning(
                    "cache_invalidation_failed",
                    server_id=str(server_id),
                    slug=updated.slug,
                )

        return updated

    async def duplicate_server(
        self,
        source_server_id: UUID,
        new_owner_user_id: UUID,
        new_name: str,
        new_slug: str,
        team_id: UUID | None = None,
    ) -> MCPServer:
        """Duplicate an existing server.

        Copies all configuration fields (``tools_config`` with a deep copy)
        but does **not** copy credentials. The new server starts with
        ``status`` = "building" and ``version`` = 1.

        Raises:
            NotFoundError: If the source server doesn't exist.
            ForbiddenError: If the user lacks editor+ access on the source.
            ConflictError: If the slug is taken (should not happen since
                ``duplicate_server`` appends ``-copy-N`` suffixes).
            PlanLimitExceededError: If the user's plan server limit is reached.
        """
        source = await self.get_server_with_access_check(
            source_server_id, new_owner_user_id, "editor",
        )

        # Check plan limit for the new owner
        user = await self.user_repo.get_by_id(new_owner_user_id)
        if user:
            count = await self.server_repo.count_by_user(new_owner_user_id)
            check_plan_limit(user.plan, "servers", count)

        # Ensure slug is unique
        slug = new_slug
        existing = await self.server_repo.get_by_slug(slug)
        suffix = 1
        while existing:
            slug = f"{new_slug}-copy-{suffix}"
            existing = await self.server_repo.get_by_slug(slug)
            suffix += 1

        # Deep copy tools_config, do NOT copy credentials
        tools_config = copy.deepcopy(source.tools_config)

        return await self.server_repo.create(
            user_id=new_owner_user_id,
            slug=slug,
            name=new_name,
            base_url=source.base_url,
            description=source.description,
            spec_url=source.spec_url,
            auth_scheme=source.auth_scheme,
            auth_header_name=source.auth_header_name,
            tools_config=tools_config,
            transport_mode=source.transport_mode,
            team_id=team_id or source.team_id,
        )

    async def list_versions(
        self,
        server_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[ServerVersion], int]:
        """List version history for a server, newest first.

        Returns (items, total) where items are ordered by version DESC.
        User email enrichment is handled at the endpoint layer.
        """
        count_result = await self.server_repo.session.execute(
            select(func.count())
            .select_from(ServerVersion)
            .where(ServerVersion.server_id == server_id)
        )
        total: int = count_result.scalar_one()

        result = await self.server_repo.session.execute(
            select(ServerVersion)
            .where(ServerVersion.server_id == server_id)
            .order_by(ServerVersion.version.desc())
            .offset(skip)
            .limit(limit)
        )
        items = list(result.scalars().all())
        return items, total

    async def rollback_to_version(
        self,
        server_id: UUID,
        target_version: int,
        actor_id: UUID,
    ) -> MCPServer:
        """Rollback a server to a previous version snapshot.

        Before restoring, the current state is itself snapshotted into a
        new ``ServerVersion`` row so the rollback is reversible. The
        server's ``version`` counter is incremented.

        Raises:
            NotFoundError: If the server or target version doesn't exist.
            ForbiddenError: If the user lacks editor+ access.
        """
        # Verify access (editor+)
        server = await self.get_server_with_access_check(
            server_id, actor_id, "editor",
        )

        # Look up the target version snapshot
        target_result = await self.server_repo.session.execute(
            select(ServerVersion).where(
                ServerVersion.server_id == server_id,
                ServerVersion.version == target_version,
            )
        )
        target_snapshot = target_result.scalar_one_or_none()
        if not target_snapshot:
            raise NotFoundError(f"Version {target_version} not found for this server")

        # Snapshot current state (so rollback is reversible)
        await self._create_version_snapshot(
            server,
            changed_by=actor_id,
            change_note=f"Rollback from version {server.version} to version {target_version}",
        )

        # Restore target version's tools_config
        server.tools_config = copy.deepcopy(target_snapshot.tools_config)
        server.version = (server.version or 1) + 1
        await self.server_repo.session.flush()

        return server

    async def delete_server(self, server_id: UUID, user_id: UUID) -> None:
        """Delete a server, verifying ownership or team admin permissions.

        Raises:
            NotFoundError: If the server doesn't exist.
            ForbiddenError: If the user doesn't have sufficient permissions.
        """
        server = await self.get_server(server_id)
        if server.team_id:
            if not await self._check_team_permission(user_id, server.team_id, "admin"):
                raise ForbiddenError(
                    "Only team admins can delete this server"
                )
        elif server.user_id != user_id:
            raise ForbiddenError("You do not own this server")
        await self.server_repo.delete(server)
