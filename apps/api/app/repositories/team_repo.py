"""Team data access layer (F7).

All methods operate on the injected ``AsyncSession`` and follow the same
SQLAlchemy 2.0 async patterns as the existing ``MCPServerRepository``.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.audit_log import AuditLog
from app.models.team import Team, TeamInvitation, TeamMembership
from app.models.user import User


class TeamRepository:
    """Repository for Team / TeamMembership / TeamInvitation / AuditLog CRUD."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Team ────────────────────────────────────────────────────────────

    async def create_team(self, name: str, owner_id: UUID) -> Team:
        """Create a team and an admin membership for the owner in one transaction."""
        team = Team(name=name, owner_id=owner_id)
        self.session.add(team)
        await self.session.flush()

        membership = TeamMembership(
            team_id=team.id,
            user_id=owner_id,
            role="admin",
            joined_at=datetime.now(UTC),
            invited_by=owner_id,
        )
        self.session.add(membership)
        await self.session.flush()

        return team

    async def get_team_by_id(self, team_id: UUID) -> Team | None:
        """Get a team by its UUID."""
        result = await self.session.execute(select(Team).where(Team.id == team_id))
        return result.scalar_one_or_none()

    async def get_team_for_user(self, user_id: UUID) -> Team | None:
        """Get the team a user belongs to (joins team_memberships)."""
        result = await self.session.execute(
            select(Team)
            .join(TeamMembership, TeamMembership.team_id == Team.id)
            .where(TeamMembership.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_team(self, team: Team, **kwargs: object) -> Team:
        """Update team fields in-place."""
        for key, value in kwargs.items():
            if hasattr(team, key):
                setattr(team, key, value)
        await self.session.flush()
        return team

    async def count_user_teams(self, user_id: UUID) -> int:
        """Count the number of teams a user is a member of (owner)."""
        result = await self.session.execute(
            select(func.count())
            .select_from(TeamMembership)
            .where(TeamMembership.user_id == user_id)
        )
        return result.scalar_one()

    # ── Memberships ─────────────────────────────────────────────────────

    async def get_membership(self, team_id: UUID, user_id: UUID) -> TeamMembership | None:
        """Get a specific membership record."""
        result = await self.session.execute(
            select(TeamMembership).where(
                TeamMembership.team_id == team_id,
                TeamMembership.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_membership_by_user_id(self, user_id: UUID) -> TeamMembership | None:
        """Get a membership by user ID (any team)."""
        result = await self.session.execute(
            select(TeamMembership).where(TeamMembership.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_members(self, team_id: UUID) -> list[TeamMembership]:
        """List all members of a team ordered by join date."""
        result = await self.session.execute(
            select(TeamMembership)
            .where(TeamMembership.team_id == team_id)
            .order_by(TeamMembership.joined_at)
        )
        return list(result.scalars().all())

    async def list_members_with_users(self, team_id: UUID) -> list[dict[str, Any]]:
        """List all members of a team with user details (email, display_name, avatar_url)."""
        result = await self.session.execute(
            select(
                TeamMembership.user_id,
                TeamMembership.role,
                TeamMembership.joined_at,
                TeamMembership.invited_by,
                User.email,
                User.display_name,
                User.avatar_url,
            )
            .select_from(TeamMembership)
            .join(User, User.id == TeamMembership.user_id)
            .where(TeamMembership.team_id == team_id)
            .order_by(TeamMembership.joined_at)
        )
        rows = result.all()
        return [
            {
                "user_id": row.user_id,
                "role": row.role,
                "joined_at": row.joined_at,
                "email": row.email,
                "display_name": row.display_name,
                "avatar_url": row.avatar_url,
            }
            for row in rows
        ]

    async def create_membership(
        self,
        team_id: UUID,
        user_id: UUID,
        role: str,
        invited_by: UUID | None = None,
    ) -> TeamMembership:
        """Create a new team membership."""
        membership = TeamMembership(
            team_id=team_id,
            user_id=user_id,
            role=role,
            joined_at=datetime.now(UTC),
            invited_by=invited_by,
        )
        self.session.add(membership)
        await self.session.flush()
        return membership

    async def update_member_role(self, team_id: UUID, user_id: UUID, role: str) -> TeamMembership:
        """Update a member's role."""
        membership = await self.get_membership(team_id, user_id)
        if not membership:
            raise NotFoundError("Member not found")
        membership.role = role
        await self.session.flush()
        return membership

    async def remove_member(self, team_id: UUID, user_id: UUID) -> None:
        """Remove a member from the team."""
        membership = await self.get_membership(team_id, user_id)
        if not membership:
            raise NotFoundError("Member not found")
        await self.session.delete(membership)
        await self.session.flush()

    async def count_members(self, team_id: UUID) -> int:
        """Count members in a team."""
        result = await self.session.execute(
            select(func.count())
            .select_from(TeamMembership)
            .where(TeamMembership.team_id == team_id)
        )
        return result.scalar_one()

    async def get_user_team_ids(self, user_id: UUID) -> list[UUID]:
        """Get all team IDs the user is a member of."""
        result = await self.session.execute(
            select(TeamMembership.team_id).where(TeamMembership.user_id == user_id)
        )
        return [row[0] for row in result.all()]

    # ── Invitations ─────────────────────────────────────────────────────

    async def list_invitations(
        self, team_id: UUID, include_accepted: bool = False
    ) -> list[TeamInvitation]:
        """List invitations for a team.

        By default only returns pending (non-accepted) invitations.
        """
        query = select(TeamInvitation).where(TeamInvitation.team_id == team_id)
        if not include_accepted:
            query = query.where(TeamInvitation.accepted_at.is_(None))
        query = query.order_by(TeamInvitation.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_invitation_by_token(self, token: str) -> TeamInvitation | None:
        """Get an invitation by its unique token."""
        result = await self.session.execute(
            select(TeamInvitation).where(TeamInvitation.token == token)
        )
        return result.scalar_one_or_none()

    async def create_invitation(
        self,
        team_id: UUID,
        email: str,
        role: str,
        invited_by: UUID,
    ) -> TeamInvitation:
        """Create a pending invitation with a 48-hour expiry."""
        token = secrets.token_urlsafe(32)
        invitation = TeamInvitation(
            team_id=team_id,
            email=email,
            role=role,
            token=token,
            invited_by=invited_by,
            expires_at=datetime.now(UTC) + timedelta(hours=48),
        )
        self.session.add(invitation)
        await self.session.flush()
        return invitation

    async def accept_invitation(self, token: str, user_id: UUID) -> TeamMembership:
        """Validate and accept an invitation.

        Validates that the token exists, is not expired, and is not already
        accepted. Creates a TeamMembership, marks the invitation as accepted.

        Raises:
            NotFoundError: If the token is invalid.
            ValidationError: If expired or already accepted.
        """
        from app.core.exceptions import ValidationError

        invitation = await self.get_invitation_by_token(token)
        if not invitation:
            raise NotFoundError("Invitation not found")

        if invitation.expires_at < datetime.now(UTC):
            raise ValidationError("Invitation has expired")

        if invitation.accepted_at is not None:
            raise ValidationError("Invitation already accepted")

        membership = TeamMembership(
            team_id=invitation.team_id,
            user_id=user_id,
            role=invitation.role,
            joined_at=datetime.now(UTC),
            invited_by=invitation.invited_by,
        )
        self.session.add(membership)

        invitation.accepted_at = datetime.now(UTC)
        await self.session.flush()

        return membership

    # ── Audit Log ───────────────────────────────────────────────────────

    async def create_audit_log(
        self,
        team_id: UUID,
        user_id: UUID,
        action: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        """Create an append-only audit log entry."""
        entry = AuditLog(
            team_id=team_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.now(UTC),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_audit_log(
        self,
        team_id: UUID,
        skip: int = 0,
        limit: int = 20,
        action: str | None = None,
    ) -> tuple[list[AuditLog], int]:
        """List audit log entries for a team (paginated, optional action filter)."""
        base_query = select(AuditLog).where(AuditLog.team_id == team_id)
        count_query = (
            select(func.count()).select_from(AuditLog).where(AuditLog.team_id == team_id)
        )

        if action:
            base_query = base_query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        result = await self.session.execute(
            base_query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        )
        items = list(result.scalars().all())

        return items, total

    async def list_audit_log_with_users(
        self,
        team_id: UUID,
        skip: int = 0,
        limit: int = 20,
        action: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List audit log entries with user email (paginated, optional action filter)."""
        from sqlalchemy.orm import joinedload

        base_query = (
            select(AuditLog)
            .options(joinedload(AuditLog.team))
            .where(AuditLog.team_id == team_id)
        )
        count_query = (
            select(func.count()).select_from(AuditLog).where(AuditLog.team_id == team_id)
        )

        if action:
            base_query = base_query.where(AuditLog.action == action)
            count_query = count_query.where(AuditLog.action == action)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        result = await self.session.execute(
            base_query.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
        )
        items = list(result.scalars().all())

        # Build enriched response with user email
        enriched = []
        for entry in items:
            user_email: str | None = None
            if entry.user_id:
                user_result = await self.session.execute(
                    select(User.email).where(User.id == entry.user_id)
                )
                user_row = user_result.scalar_one_or_none()
                user_email = user_row if user_row else None
            enriched.append(
                {
                    "id": entry.id,
                    "user_id": entry.user_id,
                    "user_email": user_email,
                    "action": entry.action,
                    "resource_type": entry.resource_type,
                    "resource_id": entry.resource_id,
                    "metadata": entry.metadata_,
                    "ip_address": entry.ip_address,
                    "user_agent": entry.user_agent,
                    "created_at": entry.created_at,
                }
            )

        return enriched, total
