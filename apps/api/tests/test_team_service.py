"""Team service and endpoint tests (F7).

Tests both the service layer (unit) and the HTTP endpoints (integration).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ForbiddenError, ValidationError
from app.models.team import Team
from app.models.user import User
from app.repositories.team_repo import TeamRepository
from app.services.team_service import TeamService

TEAM_URL = "/api/v1/team"

# The email service function is imported locally inside
# ``TeamService.invite_member()``, so we patch the canonical location.
_EMAIL_SERVICE_PATH = "app.services.email_service.send_team_invitation_email"

# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def team_service(test_session: AsyncSession) -> TeamService:
    """Return a ``TeamService`` bound to the test session."""
    return TeamService(test_session)


@pytest.fixture
def team_repo(test_session: AsyncSession) -> TeamRepository:
    """Return a ``TeamRepository`` bound to the test session."""
    return TeamRepository(test_session)


@pytest.fixture
async def owner_user(test_session: AsyncSession) -> User:
    """Create a team owner user."""
    u = User(
        email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",
        plan="team",
    )
    test_session.add(u)
    await test_session.flush()
    return u


@pytest.fixture
async def second_user(test_session: AsyncSession) -> User:
    """Create a second user."""
    u = User(
        email=f"user2-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="test-hash",
        plan="team",
    )
    test_session.add(u)
    await test_session.flush()
    return u


@pytest.fixture
async def team_with_members(
    team_service: TeamService,
    owner_user: User,
    second_user: User,
) -> Team:
    """Create a team with two members (owner + second_user as editor)."""
    team = await team_service.create_team(
        owner_id=owner_user.id,
        name="Test Team",
    )
    from app.repositories.team_repo import TeamRepository as TeamRepo

    repo = TeamRepo(team_service.repo.session)
    await repo.create_membership(
        team_id=team.id,
        user_id=second_user.id,
        role="editor",
        invited_by=owner_user.id,
    )
    return team


# ── Service-level tests ──────────────────────────────────────────────────


class TestCreateTeam:
    """Tests for ``TeamService.create_team()``."""

    @pytest.mark.asyncio
    async def test_create_team_sets_owner_as_admin(
        self,
        team_service: TeamService,
        owner_user: User,
    ) -> None:
        """Creating a team should set the owner as an admin member."""
        team = await team_service.create_team(
            owner_id=owner_user.id,
            name="My Team",
        )

        assert team.name == "My Team"
        assert team.owner_id == owner_user.id

        membership = await team_service.repo.get_membership(team.id, owner_user.id)
        assert membership is not None
        assert membership.role == "admin"

    @pytest.mark.asyncio
    async def test_create_team_rejects_duplicate_team_for_user(
        self,
        team_service: TeamService,
        owner_user: User,
    ) -> None:
        """A user who already has a team cannot create another."""
        await team_service.create_team(owner_id=owner_user.id, name="First Team")

        with pytest.raises(ConflictError, match="already belong to a team"):
            await team_service.create_team(owner_id=owner_user.id, name="Second Team")


class TestInviteMember:
    """Tests for ``TeamService.invite_member()``."""

    @pytest.mark.asyncio
    async def test_invite_member_requires_admin_role(
        self,
        team_service: TeamService,
        team_with_members: Team,
        second_user: User,
    ) -> None:
        """Non-admin members cannot invite."""
        with pytest.raises(ForbiddenError, match="Only team admins"):
            await team_service.invite_member(
                team_id=team_with_members.id,
                inviter_id=second_user.id,
                email="new@example.com",
                role="viewer",
                base_url="http://test",
            )

    @pytest.mark.asyncio
    async def test_invite_member_sends_email(
        self,
        team_service: TeamService,
        team_with_members: Team,
        owner_user: User,
    ) -> None:
        """Inviting a member should send an invitation email."""
        with patch(
            _EMAIL_SERVICE_PATH,
            new_callable=AsyncMock,
        ) as mock_send:
            invitation = await team_service.invite_member(
                team_id=team_with_members.id,
                inviter_id=owner_user.id,
                email="new@example.com",
                role="viewer",
                base_url="http://test",
            )

            assert invitation.email == "new@example.com"
            assert invitation.role == "viewer"
            assert invitation.token is not None

            mock_send.assert_awaited_once()
            call_kwargs = mock_send.call_args.kwargs
            assert call_kwargs["email"] == "new@example.com"
            assert call_kwargs["token"] == invitation.token
            assert call_kwargs["team_name"] == team_with_members.name

    @pytest.mark.asyncio
    async def test_invite_member_rejects_duplicate_pending_invitation(
        self,
        team_service: TeamService,
        team_with_members: Team,
        owner_user: User,
    ) -> None:
        """Cannot invite the same email twice while first invite is pending."""
        with patch(
            _EMAIL_SERVICE_PATH,
            new_callable=AsyncMock,
        ):
            await team_service.invite_member(
                team_id=team_with_members.id,
                inviter_id=owner_user.id,
                email="new@example.com",
                role="viewer",
                base_url="http://test",
            )

            with pytest.raises(ConflictError, match="already exists"):
                await team_service.invite_member(
                    team_id=team_with_members.id,
                    inviter_id=owner_user.id,
                    email="new@example.com",
                    role="editor",
                    base_url="http://test",
                )

    @pytest.mark.asyncio
    async def test_invite_member_enforces_seat_limit(
        self,
        team_service: TeamService,
        owner_user: User,
        second_user: User,
    ) -> None:
        """Cannot invite more members than the plan allows."""
        # Set owner to free plan (max 1 member = just the owner)
        owner_user.plan = "free"
        await team_service.repo.session.flush()

        team = await team_service.create_team(
            owner_id=owner_user.id,
            name="Free Team",
        )

        with (
            patch(
                _EMAIL_SERVICE_PATH,
                new_callable=AsyncMock,
            ),
            pytest.raises(ValidationError, match="Member limit"),
        ):
                await team_service.invite_member(
                    team_id=team.id,
                    inviter_id=owner_user.id,
                    email="new@example.com",
                    role="viewer",
                    base_url="http://test",
                )


class TestAcceptInvitation:
    """Tests for ``TeamService.accept_invitation()``."""

    @pytest.mark.asyncio
    async def test_accept_invitation_creates_membership(
        self,
        team_service: TeamService,
        team_with_members: Team,
        owner_user: User,
    ) -> None:
        """Accepting a valid invitation creates a membership."""
        with patch(
            _EMAIL_SERVICE_PATH,
            new_callable=AsyncMock,
        ):
            invitation = await team_service.invite_member(
                team_id=team_with_members.id,
                inviter_id=owner_user.id,
                email="new@example.com",
                role="editor",
                base_url="http://test",
            )

        new_user_id = uuid.uuid4()
        from app.models.user import User as UserModel

        new_user = UserModel(
            id=new_user_id,
            email="new@example.com",
            password_hash="test-hash",
        )
        team_service.repo.session.add(new_user)
        await team_service.repo.session.flush()

        membership = await team_service.accept_invitation(
            token=invitation.token,
            user_id=new_user_id,
        )

        assert membership is not None
        assert membership.team_id == team_with_members.id
        assert membership.user_id == new_user_id
        assert membership.role == "editor"

        # Verify invitation is marked as accepted
        updated_invitation = await team_service.repo.get_invitation_by_token(invitation.token)
        assert updated_invitation is not None
        assert updated_invitation.accepted_at is not None

    @pytest.mark.asyncio
    async def test_accept_invitation_rejects_expired_token(
        self,
        team_service: TeamService,
        team_with_members: Team,
        owner_user: User,
    ) -> None:
        """Accepting an expired invitation should fail."""
        with patch(
            _EMAIL_SERVICE_PATH,
            new_callable=AsyncMock,
        ):
            invitation = await team_service.invite_member(
                team_id=team_with_members.id,
                inviter_id=owner_user.id,
                email="new@example.com",
                role="viewer",
                base_url="http://test",
            )

        # Freeze time 49 hours in the future (invitation expires in 48h)
        future = datetime.now(UTC) + timedelta(hours=49)
        with freeze_time(future), pytest.raises(ValidationError, match="expired"):
                await team_service.accept_invitation(
                    token=invitation.token,
                    user_id=uuid.uuid4(),
                )

    @pytest.mark.asyncio
    async def test_accept_invitation_rejects_already_accepted_token(
        self,
        team_service: TeamService,
        team_with_members: Team,
        owner_user: User,
    ) -> None:
        """Accepting an already-accepted invitation should fail."""
        with patch(
            _EMAIL_SERVICE_PATH,
            new_callable=AsyncMock,
        ):
            invitation = await team_service.invite_member(
                team_id=team_with_members.id,
                inviter_id=owner_user.id,
                email="new@example.com",
                role="viewer",
                base_url="http://test",
            )

        new_user_id = uuid.uuid4()
        from app.models.user import User as UserModel

        new_user = UserModel(
            id=new_user_id,
            email="new@example.com",
            password_hash="test-hash",
        )
        team_service.repo.session.add(new_user)
        await team_service.repo.session.flush()

        # First accept should succeed
        await team_service.accept_invitation(token=invitation.token, user_id=new_user_id)

        # Second accept should fail
        another_user_id = uuid.uuid4()
        another_user = UserModel(
            id=another_user_id,
            email="another@example.com",
            password_hash="test-hash",
        )
        team_service.repo.session.add(another_user)
        await team_service.repo.session.flush()

        with pytest.raises(ValidationError, match="already accepted"):
            await team_service.accept_invitation(
                token=invitation.token,
                user_id=another_user_id,
            )


class TestUpdateMemberRole:
    """Tests for ``TeamService.update_member_role()``."""

    @pytest.mark.asyncio
    async def test_update_member_role_admin_only(
        self,
        team_service: TeamService,
        team_with_members: Team,
        second_user: User,
        owner_user: User,
    ) -> None:
        """Only admins can update roles."""
        with pytest.raises(ForbiddenError, match="Only team admins"):
            await team_service.update_member_role(
                team_id=team_with_members.id,
                actor_id=second_user.id,
                target_user_id=owner_user.id,
                new_role="viewer",
            )

    @pytest.mark.asyncio
    async def test_update_member_role_cannot_demote_last_admin(
        self,
        team_service: TeamService,
        team_with_members: Team,
        owner_user: User,
    ) -> None:
        """Cannot demote the last admin in the team."""
        with pytest.raises(ForbiddenError, match="Cannot demote the last"):
            await team_service.update_member_role(
                team_id=team_with_members.id,
                actor_id=owner_user.id,
                target_user_id=owner_user.id,
                new_role="editor",
            )

    @pytest.mark.asyncio
    async def test_update_member_role_succeeds_for_admin(
        self,
        team_service: TeamService,
        team_with_members: Team,
        owner_user: User,
        second_user: User,
    ) -> None:
        """Admin can update another member's role."""
        membership = await team_service.update_member_role(
            team_id=team_with_members.id,
            actor_id=owner_user.id,
            target_user_id=second_user.id,
            new_role="admin",
        )

        assert membership.role == "admin"

        # Now demote second_user back (there are still 2 admins)
        membership = await team_service.update_member_role(
            team_id=team_with_members.id,
            actor_id=owner_user.id,
            target_user_id=second_user.id,
            new_role="viewer",
        )
        assert membership.role == "viewer"


class TestRemoveMember:
    """Tests for ``TeamService.remove_member()``."""

    @pytest.mark.asyncio
    async def test_remove_member_admin_only(
        self,
        team_service: TeamService,
        team_with_members: Team,
        second_user: User,
    ) -> None:
        """Non-admin cannot remove other members."""
        with pytest.raises(ForbiddenError, match="Only team admins"):
            await team_service.remove_member(
                team_id=team_with_members.id,
                actor_id=second_user.id,
                target_user_id=team_with_members.owner_id,
            )

    @pytest.mark.asyncio
    async def test_remove_member_cannot_remove_last_admin(
        self,
        team_service: TeamService,
        team_with_members: Team,
        owner_user: User,
    ) -> None:
        """Cannot remove the last admin from the team."""
        with pytest.raises(ForbiddenError, match="Cannot remove the last"):
            await team_service.remove_member(
                team_id=team_with_members.id,
                actor_id=owner_user.id,
                target_user_id=owner_user.id,
            )

    @pytest.mark.asyncio
    async def test_remove_member_self_removal(
        self,
        team_service: TeamService,
        team_with_members: Team,
        owner_user: User,
        second_user: User,
    ) -> None:
        """A non-admin member can remove themselves."""
        # First, add a third admin so we have another admin besides owner
        repo = team_service.repo
        third_user_id = uuid.uuid4()
        from app.models.user import User as UserModel

        third_user = UserModel(
            id=third_user_id,
            email="third@example.com",
            password_hash="test-hash",
        )
        repo.session.add(third_user)
        await repo.session.flush()

        await repo.create_membership(
            team_id=team_with_members.id,
            user_id=third_user_id,
            role="admin",
            invited_by=owner_user.id,
        )

        # second_user (editor) removes themselves
        await team_service.remove_member(
            team_id=team_with_members.id,
            actor_id=second_user.id,
            target_user_id=second_user.id,
        )

        removed = await repo.get_membership(team_with_members.id, second_user.id)
        assert removed is None


class TestCheckPermission:
    """Tests for ``TeamService.check_permission()``."""

    @pytest.mark.asyncio
    async def test_check_permission_role_hierarchy(
        self,
        team_service: TeamService,
        team_with_members: Team,
        owner_user: User,
        second_user: User,
    ) -> None:
        """Test all 9 combinations of (user_role, required_role)."""
        # owner_user is admin, second_user is editor
        scenarios: list[tuple[str, str, bool, User]] = [
            # (user's role, required role, expected result, user)
            ("admin", "viewer", True, owner_user),
            ("admin", "editor", True, owner_user),
            ("admin", "admin", True, owner_user),
            ("editor", "viewer", True, second_user),
            ("editor", "editor", True, second_user),
            ("editor", "admin", False, second_user),
            ("viewer", "viewer", True, None),  # will be set up below
            ("viewer", "editor", False, None),
            ("viewer", "admin", False, None),
        ]

        # Create a viewer membership first
        viewer_user_id = uuid.uuid4()
        from app.models.user import User as UserModel

        viewer_user = UserModel(
            id=viewer_user_id,
            email="viewer@example.com",
            password_hash="test-hash",
            plan="team",
        )
        team_service.repo.session.add(viewer_user)
        await team_service.repo.session.flush()

        await team_service.repo.create_membership(
            team_id=team_with_members.id,
            user_id=viewer_user_id,
            role="viewer",
            invited_by=owner_user.id,
        )

        for user_role, required_role, expected, user in scenarios:
            actual_user = user if user is not None else viewer_user
            result = await team_service.check_permission(
                user_id=actual_user.id,
                team_id=team_with_members.id,
                required_role=required_role,
            )
            assert result == expected, (
                f"Expected {user_role} >= {required_role} → {expected}, got {result}"
            )

    @pytest.mark.asyncio
    async def test_check_permission_returns_false_for_non_member(
        self,
        team_service: TeamService,
        team_with_members: Team,
    ) -> None:
        """A non-member should always have False permission."""
        non_member_id = uuid.uuid4()
        result = await team_service.check_permission(
            user_id=non_member_id,
            team_id=team_with_members.id,
            required_role="viewer",
        )
        assert result is False


class TestTransferOwnership:
    """Tests for ``TeamService.transfer_ownership()``."""

    @pytest.mark.asyncio
    async def test_transfer_ownership_demotes_previous_to_admin(
        self,
        team_service: TeamService,
        team_with_members: Team,
        owner_user: User,
        second_user: User,
    ) -> None:
        """Transferring ownership demotes the old owner to admin."""
        team = await team_service.transfer_ownership(
            team_id=team_with_members.id,
            current_owner_id=owner_user.id,
            new_owner_id=second_user.id,
        )

        assert team.owner_id == second_user.id

        old_owner_membership = await team_service.repo.get_membership(
            team.id, owner_user.id
        )
        assert old_owner_membership is not None
        assert old_owner_membership.role == "admin"

        new_owner_membership = await team_service.repo.get_membership(
            team.id, second_user.id
        )
        assert new_owner_membership is not None
        assert new_owner_membership.role == "admin"

    @pytest.mark.asyncio
    async def test_transfer_ownership_requires_current_owner(
        self,
        team_service: TeamService,
        team_with_members: Team,
        second_user: User,
    ) -> None:
        """Only the current owner can transfer ownership."""
        non_owner_id = uuid.uuid4()
        with pytest.raises(ForbiddenError, match="Only the team owner"):
            await team_service.transfer_ownership(
                team_id=team_with_members.id,
                current_owner_id=non_owner_id,
                new_owner_id=second_user.id,
            )


class TestAuditLog:
    """Tests for audit logging on team mutations."""

    @pytest.mark.asyncio
    async def test_audit_log_captures_team_events(
        self,
        team_service: TeamService,
        owner_user: User,
    ) -> None:
        """Verify audit log captures team.create, team.invite, team.accept."""
        # 1. Create team
        team = await team_service.create_team(
            owner_id=owner_user.id,
            name="Audited Team",
        )

        # 2. Invite someone (mock email)
        with patch(
            _EMAIL_SERVICE_PATH,
            new_callable=AsyncMock,
        ):
            invitation = await team_service.invite_member(
                team_id=team.id,
                inviter_id=owner_user.id,
                email="audited@example.com",
                role="editor",
                base_url="http://test",
                ip_address="127.0.0.1",
                user_agent="test-agent",
            )

        # 3. Accept invitation
        new_user_id = uuid.uuid4()
        from app.models.user import User as UserModel

        new_user = UserModel(
            id=new_user_id,
            email="audited@example.com",
            password_hash="test-hash",
        )
        team_service.repo.session.add(new_user)
        await team_service.repo.session.flush()

        await team_service.accept_invitation(
            token=invitation.token,
            user_id=new_user_id,
            ip_address="127.0.0.2",
            user_agent="test-agent-2",
        )

        # Read audit log as admin
        items, total = await team_service.list_audit_log(
            team_id=team.id,
            actor_id=owner_user.id,
            skip=0,
            limit=20,
        )

        assert total >= 2

        actions = [entry["action"] for entry in items]
        assert "team.invite" in actions, f"Expected team.invite, got {actions}"
        assert "team.accept" in actions, f"Expected team.accept, got {actions}"

        # Verify audit log entry details
        invite_entries = [e for e in items if e["action"] == "team.invite"]
        assert len(invite_entries) >= 1
        entry = invite_entries[0]
        assert entry["ip_address"] == "127.0.0.1"
        assert entry["user_agent"] == "test-agent"
        assert entry["metadata"]["email"] == "audited@example.com"

    @pytest.mark.asyncio
    async def test_list_audit_log_requires_admin(
        self,
        team_service: TeamService,
        team_with_members: Team,
        second_user: User,
    ) -> None:
        """Only admins can list audit log."""
        with pytest.raises(ForbiddenError, match="Only team admins"):
            await team_service.list_audit_log(
                team_id=team_with_members.id,
                actor_id=second_user.id,
                skip=0,
                limit=20,
            )


class TestListMembers:
    """Tests for ``TeamService.list_members()``."""

    @pytest.mark.asyncio
    async def test_list_members_requires_membership(
        self,
        team_service: TeamService,
        team_with_members: Team,
    ) -> None:
        """Listing members requires the actor to be a team member."""
        non_member_id = uuid.uuid4()
        with pytest.raises(ForbiddenError, match="not a member"):
            await team_service.list_members(
                team_id=team_with_members.id,
                actor_id=non_member_id,
            )

    @pytest.mark.asyncio
    async def test_list_members_returns_all_with_details(
        self,
        team_service: TeamService,
        team_with_members: Team,
        owner_user: User,
    ) -> None:
        """Listing members returns all members with user details."""
        members = await team_service.list_members(
            team_id=team_with_members.id,
            actor_id=owner_user.id,
        )

        assert len(members) == 2
        emails = {m["email"] for m in members}
        assert owner_user.email in emails


# ── Endpoint-level tests ────────────────────────────────────────────────


class TestTeamEndpoints:
    """HTTP endpoint tests for team management."""

    TEAM_URL = TEAM_URL

    @pytest.mark.asyncio
    async def test_create_team_endpoint(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """POST /api/v1/team creates a team."""
        response = await auth_client.post(
            self.TEAM_URL,
            json={"name": "My API Team"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "My API Team"
        assert data["member_count"] == 1
        assert data["current_user_role"] == "admin"

    @pytest.mark.asyncio
    async def test_get_team(
        self,
        auth_client: AsyncClient,
        auth_user: User,
        test_session: AsyncSession,
    ) -> None:
        """GET /api/v1/team returns the user's team."""
        # Create team first
        await auth_client.post(
            self.TEAM_URL,
            json={"name": "My Team"},
        )

        # Get team
        response = await auth_client.get(self.TEAM_URL)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "My Team"
        assert data["current_user_role"] == "admin"
        assert data["member_count"] == 1

    @pytest.mark.asyncio
    async def test_get_team_404_when_no_team(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """GET /api/v1/team returns 404 when user has no team."""
        response = await auth_client.get(self.TEAM_URL)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invite_endpoint_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """POST /api/v1/team/invite requires authentication."""
        response = await client.post(
            f"{self.TEAM_URL}/invite",
            json={"email": "test@example.com", "role": "editor"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_accept_endpoint_requires_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """POST /api/v1/team/accept requires authentication."""
        response = await client.post(
            f"{self.TEAM_URL}/accept",
            json={"token": "some-token"},
        )
        assert response.status_code == 401
