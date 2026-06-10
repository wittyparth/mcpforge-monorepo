"""Team management business logic (F7).

Handles team CRUD, member invitations with 48h tokens, role-based access
control (viewer < editor < admin), ownership transfer, and audit logging
for all team mutations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.team import Team, TeamInvitation, TeamMembership
from app.repositories.team_repo import TeamRepository
from app.repositories.user_repo import UserRepository

logger = get_logger(__name__)

# Role hierarchy: higher number = more permissions
ROLE_HIERARCHY: dict[str, int] = {
    "viewer": 1,
    "editor": 2,
    "admin": 3,
}

# Plan limits indexed by user.plan value
PLAN_LIMITS: dict[str, dict[str, int]] = {
    "free": {"max_teams": 1, "max_members": 1},
    "pro": {"max_teams": 3, "max_members": 5},
    "team": {"max_teams": 10, "max_members": 20},
}


class TeamService:
    """Service-layer logic for team management."""

    def __init__(self, session: AsyncSession) -> None:
        self.repo = TeamRepository(session)
        self.user_repo = UserRepository(session)

    # ── Permission helpers ──────────────────────────────────────────────

    async def check_permission(self, user_id: UUID, team_id: UUID, required_role: str) -> bool:
        """Check if a user has at least ``required_role`` in the team.

        Returns ``True`` if the user is a member with a role >= required_role
        in the hierarchy, ``False`` otherwise.
        """
        membership = await self.repo.get_membership(team_id, user_id)
        if not membership:
            return False
        user_level = ROLE_HIERARCHY.get(membership.role, 0)
        required_level = ROLE_HIERARCHY.get(required_role, 0)
        return user_level >= required_level

    async def assert_admin(self, user_id: UUID, team_id: UUID) -> TeamMembership:
        """Raise ``ForbiddenError`` if the user is not an admin in the team."""
        membership = await self.repo.get_membership(team_id, user_id)
        if not membership or membership.role != "admin":
            raise ForbiddenError("Only team admins can perform this action")
        return membership

    async def assert_member(self, user_id: UUID, team_id: UUID) -> TeamMembership:
        """Raise ``ForbiddenError`` if the user is not a team member."""
        membership = await self.repo.get_membership(team_id, user_id)
        if not membership:
            raise ForbiddenError("You are not a member of this team")
        return membership

    async def _count_admins(self, team_id: UUID) -> int:
        """Count the number of admin members in the team."""
        members = await self.repo.list_members(team_id)
        return sum(1 for m in members if m.role == "admin")

    async def _write_audit_log(
        self,
        team_id: UUID,
        actor_id: UUID,
        action: str,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Write an audit log entry for a team mutation."""
        await self.repo.create_audit_log(
            team_id=team_id,
            user_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        logger.info(
            "team_audit",
            team_id=str(team_id),
            actor=str(actor_id),
            action=action,
        )

    # ── Team CRUD ───────────────────────────────────────────────────────

    async def create_team(self, owner_id: UUID, name: str) -> Team:
        """Create a new team with the creator as admin.

        Validates:
        - Name is 1-200 characters (Pydantic handles this).
        - User doesn't already belong to a team.
        - User's plan allows creating a new team.

        Raises:
            ConflictError: If the user already belongs to a team.
            ValidationError: If the plan limit is reached.
        """
        existing_team = await self.repo.get_team_for_user(owner_id)
        if existing_team:
            raise ConflictError("You already belong to a team")

        user = await self.user_repo.get_by_id(owner_id)
        if not user:
            raise NotFoundError("User not found")

        plan_limits = PLAN_LIMITS.get(user.plan, PLAN_LIMITS["free"])
        current_teams = await self.repo.count_user_teams(owner_id)
        if current_teams >= plan_limits["max_teams"]:
            raise ValidationError(
                f"Team limit reached for {user.plan} plan "
                f"({plan_limits['max_teams']} max)"
            )

        team = await self.repo.create_team(name=name, owner_id=owner_id)

        # Inherit the plan from the creating user so invite-time checks
        # (max_members) reflect the user's current billing tier.
        team.plan = user.plan
        await self.repo.session.flush()

        logger.info("team_created", team_id=str(team.id), owner_id=str(owner_id), plan=team.plan)
        return team

    async def get_team_for_user(self, user_id: UUID) -> Team | None:
        """Get the team the user belongs to (or ``None``)."""
        return await self.repo.get_team_for_user(user_id)

    async def update_team(
        self,
        team_id: UUID,
        actor_id: UUID,
        name: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Team:
        """Update team name. Admin only."""
        await self.assert_admin(actor_id, team_id)

        team = await self.repo.get_team_by_id(team_id)
        if not team:
            raise NotFoundError("Team not found")

        updated = await self.repo.update_team(team, name=name)

        await self._write_audit_log(
            team_id=team_id,
            actor_id=actor_id,
            action="team.update",
            resource_type="team",
            resource_id=team_id,
            metadata={"name": name},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return updated

    # ── Invitations ─────────────────────────────────────────────────────

    async def invite_member(
        self,
        team_id: UUID,
        inviter_id: UUID,
        email: str,
        role: str,
        base_url: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TeamInvitation:
        """Invite a user by email to join the team.

        Validates:
        - Inviter is an admin.
        - Member count < plan limit.
        - No pending invitation exists for the same email.

        Side effect: Sends an invitation email.
        """
        await self.assert_admin(inviter_id, team_id)

        team = await self.repo.get_team_by_id(team_id)
        if not team:
            raise NotFoundError("Team not found")

        # Check member count < plan limit (use team's plan, not owner's personal plan)
        plan_limits = PLAN_LIMITS.get(team.plan, PLAN_LIMITS["free"])
        member_count = await self.repo.count_members(team_id)
        if member_count >= plan_limits["max_members"]:
            raise ValidationError(
                f"Member limit reached ({plan_limits['max_members']} max "
                f"for {team.plan} plan)"
            )

        # Check for existing pending invitation for same email
        existing = await self.repo.list_invitations(team_id)
        for inv in existing:
            # Strip tzinfo for SQLite compatibility (it doesn't store timezone).
            now = datetime.now(UTC).replace(tzinfo=None)
            if inv.email == email and inv.expires_at.replace(tzinfo=None) > now:
                raise ConflictError("Pending invitation already exists for this email")

        invitation = await self.repo.create_invitation(
            team_id=team_id,
            email=email,
            role=role,
            invited_by=inviter_id,
        )

        # Send invitation email
        inviter = await self.user_repo.get_by_id(inviter_id)
        inviter_name = inviter.display_name if inviter and inviter.display_name else "A team member"

        from app.services.email_service import send_team_invitation_email

        await send_team_invitation_email(
            email=email,
            team_name=team.name,
            inviter_name=inviter_name,
            token=invitation.token,
            base_url=base_url,
        )

        await self._write_audit_log(
            team_id=team_id,
            actor_id=inviter_id,
            action="team.invite",
            resource_type="invitation",
            resource_id=invitation.id,
            metadata={"email": email, "role": role},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "team_member_invited",
            team_id=str(team_id),
            email=email,
            role=role,
            invited_by=str(inviter_id),
        )

        return invitation

    async def accept_invitation(
        self,
        token: str,
        user_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TeamMembership:
        """Accept a team invitation by token.

        Creates a new membership and marks the invitation as accepted.
        """
        membership = await self.repo.accept_invitation(token=token, user_id=user_id)

        await self._write_audit_log(
            team_id=membership.team_id,
            actor_id=user_id,
            action="team.accept",
            resource_type="membership",
            resource_id=None,
            metadata={},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "team_member_accepted",
            team_id=str(membership.team_id),
            user_id=str(user_id),
        )

        return membership

    # ── Member management ───────────────────────────────────────────────

    async def list_members(self, team_id: UUID, actor_id: UUID) -> list[dict[str, Any]]:
        """List team members with user details. Actor must be a member."""
        await self.assert_member(actor_id, team_id)
        return await self.repo.list_members_with_users(team_id)

    async def update_member_role(
        self,
        team_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        new_role: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TeamMembership:
        """Update a member's role. Admin only.

        Raises:
            ForbiddenError: If the actor is not an admin, or if the target
                is the last admin and ``new_role`` is not admin.
        """
        await self.assert_admin(actor_id, team_id)

        # Prevent demoting the last admin
        if new_role != "admin":
            target_membership = await self.repo.get_membership(team_id, target_user_id)
            if target_membership and target_membership.role == "admin":
                admin_count = await self._count_admins(team_id)
                if admin_count <= 1:
                    raise ForbiddenError(
                        "Cannot demote the last team admin. "
                        "Transfer ownership first or promote another member to admin."
                    )

        membership = await self.repo.update_member_role(team_id, target_user_id, new_role)

        await self._write_audit_log(
            team_id=team_id,
            actor_id=actor_id,
            action="team.member.role_update",
            resource_type="membership",
            resource_id=None,
            metadata={"target_user_id": str(target_user_id), "new_role": new_role},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return membership

    async def remove_member(
        self,
        team_id: UUID,
        actor_id: UUID,
        target_user_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Remove a member from the team.

        Actor must be an admin, OR the actor is removing themselves.
        Cannot remove the last admin (must transfer ownership first).
        """
        is_self_removal = actor_id == target_user_id
        if not is_self_removal:
            await self.assert_admin(actor_id, team_id)

        # Prevent removing the last admin
        target_membership = await self.repo.get_membership(team_id, target_user_id)
        if target_membership and target_membership.role == "admin":
            admin_count = await self._count_admins(team_id)
            if admin_count <= 1:
                raise ForbiddenError(
                    "Cannot remove the last team admin. "
                    "Transfer ownership first."
                )

        await self.repo.remove_member(team_id, target_user_id)

        await self._write_audit_log(
            team_id=team_id,
            actor_id=actor_id,
            action="team.member.remove",
            resource_type="membership",
            resource_id=None,
            metadata={"target_user_id": str(target_user_id)},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "team_member_removed",
            team_id=str(team_id),
            user_id=str(target_user_id),
            removed_by=str(actor_id),
        )

    async def transfer_ownership(
        self,
        team_id: UUID,
        current_owner_id: UUID,
        new_owner_id: UUID,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Team:
        """Transfer team ownership to another member.

        The current owner is demoted to admin. The new owner is promoted
        to admin (they must already be a member).

        Raises:
            ForbiddenError: If the caller is not the current owner.
            NotFoundError: If the team or new owner membership is not found.
        """
        team = await self.repo.get_team_by_id(team_id)
        if not team:
            raise NotFoundError("Team not found")

        if team.owner_id != current_owner_id:
            raise ForbiddenError("Only the team owner can transfer ownership")

        # Verify new owner is a member
        new_owner_membership = await self.repo.get_membership(team_id, new_owner_id)
        if not new_owner_membership:
            raise NotFoundError("New owner is not a member of this team")

        # Update team owner
        team.owner_id = new_owner_id
        await self.repo.session.flush()

        # Demote current owner to admin
        await self.repo.update_member_role(team_id, current_owner_id, "admin")

        # Ensure new owner is admin
        if new_owner_membership.role != "admin":
            await self.repo.update_member_role(team_id, new_owner_id, "admin")

        await self._write_audit_log(
            team_id=team_id,
            actor_id=current_owner_id,
            action="team.ownership_transfer",
            resource_type="team",
            resource_id=team_id,
            metadata={"new_owner_id": str(new_owner_id)},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        logger.info(
            "team_ownership_transferred",
            team_id=str(team_id),
            from_user=str(current_owner_id),
            to_user=str(new_owner_id),
        )

        return team

    # ── Audit log ───────────────────────────────────────────────────────

    async def list_audit_log(
        self,
        team_id: UUID,
        actor_id: UUID,
        skip: int = 0,
        limit: int = 20,
        action: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """List audit log entries. Admin only."""
        await self.assert_admin(actor_id, team_id)
        return await self.repo.list_audit_log_with_users(
            team_id=team_id,
            skip=skip,
            limit=limit,
            action=action,
        )
