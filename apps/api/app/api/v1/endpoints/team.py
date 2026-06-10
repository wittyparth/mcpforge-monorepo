"""Team management endpoints (F7).

Every mutation writes an audit log entry recording the actor, action,
resource, IP address, and user agent.  Role-based access control is
enforced at the service layer.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import NotFoundError
from app.models.user import User
from app.schemas.team import (
    AuditLogResponse,
    PaginatedAuditLogResponse,
    TeamAcceptRequest,
    TeamCreateRequest,
    TeamInvitationResponse,
    TeamInviteRequest,
    TeamMemberResponse,
    TeamMemberUpdateRequest,
    TeamResponse,
    TeamRole,
    TeamUpdateRequest,
)
from app.services.team_service import TeamService

router = APIRouter(prefix="/team", tags=["team"])


@router.get("", response_model=TeamResponse)
async def get_team(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    """Get the current user's team."""
    svc = TeamService(session)
    team = await svc.get_team_for_user(current_user.id)
    if not team:
        raise NotFoundError("Team not found")

    member_count = await svc.repo.count_members(team.id)
    membership = await svc.repo.get_membership(team.id, current_user.id)
    current_user_role: TeamRole | None = cast(
        TeamRole | None, membership.role if membership else None
    )

    resp = TeamResponse.model_validate(team)
    resp.member_count = member_count
    resp.current_user_role = current_user_role
    return resp


@router.post("", response_model=TeamResponse, status_code=201)
async def create_team(
    body: TeamCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    """Create a new team for the current user."""
    svc = TeamService(session)
    team = await svc.create_team(
        owner_id=current_user.id,
        name=body.name,
    )

    member_count = await svc.repo.count_members(team.id)
    resp = TeamResponse.model_validate(team)
    resp.member_count = member_count
    resp.current_user_role = "admin"
    return resp


@router.patch("", response_model=TeamResponse)
async def update_team(
    body: TeamUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamResponse:
    """Update team name. Admin only."""
    svc = TeamService(session)
    team = await svc.get_team_for_user(current_user.id)
    if not team:
        raise NotFoundError("Team not found")

    updated = await svc.update_team(
        team_id=team.id,
        actor_id=current_user.id,
        name=body.name,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    member_count = await svc.repo.count_members(updated.id)
    membership = await svc.repo.get_membership(updated.id, current_user.id)
    resp = TeamResponse.model_validate(updated)
    resp.member_count = member_count
    resp.current_user_role = cast(
        TeamRole | None, membership.role if membership else None
    )
    return resp


@router.post("/invite", response_model=TeamInvitationResponse, status_code=201)
async def invite_member(
    body: TeamInviteRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamInvitationResponse:
    """Invite a user by email. Admin only."""
    svc = TeamService(session)
    team = await svc.get_team_for_user(current_user.id)
    if not team:
        raise NotFoundError("Team not found")

    base_url = str(request.base_url).rstrip("/")
    invitation = await svc.invite_member(
        team_id=team.id,
        inviter_id=current_user.id,
        email=body.email,
        role=body.role,
        base_url=base_url,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    resp = TeamInvitationResponse.model_validate(invitation)
    resp.token = invitation.token
    return resp


@router.post("/accept", response_model=TeamMemberResponse, status_code=201)
async def accept_invitation(
    body: TeamAcceptRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamMemberResponse:
    """Accept a team invitation by token."""
    svc = TeamService(session)
    membership = await svc.accept_invitation(
        token=body.token,
        user_id=current_user.id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    return TeamMemberResponse(
        user_id=membership.user_id,
        email=current_user.email,
        display_name=current_user.display_name,
        avatar_url=current_user.avatar_url,
        role=cast(TeamRole, membership.role),
        joined_at=membership.joined_at,
    )


@router.get("/members", response_model=list[TeamMemberResponse])
async def list_members(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TeamMemberResponse]:
    """List all team members."""
    svc = TeamService(session)
    team = await svc.get_team_for_user(current_user.id)
    if not team:
        raise NotFoundError("Team not found")

    members_data = await svc.list_members(team.id, current_user.id)
    return [TeamMemberResponse(**m) for m in members_data]


@router.patch("/members/{user_id}", response_model=TeamMemberResponse)
async def update_member(
    user_id: UUID,
    body: TeamMemberUpdateRequest,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TeamMemberResponse:
    """Update a member's role. Admin only."""
    svc = TeamService(session)
    team = await svc.get_team_for_user(current_user.id)
    if not team:
        raise NotFoundError("Team not found")

    membership = await svc.update_member_role(
        team_id=team.id,
        actor_id=current_user.id,
        target_user_id=user_id,
        new_role=body.role,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    # Look up user details
    from app.repositories.user_repo import UserRepository

    user_repo = UserRepository(session)
    user = await user_repo.get_by_id(user_id)

    return TeamMemberResponse(
        user_id=membership.user_id,
        email=user.email if user else "",
        display_name=user.display_name if user else None,
        avatar_url=user.avatar_url if user else None,
        role=cast(TeamRole, membership.role),
        joined_at=membership.joined_at,
    )


@router.delete("/members/{user_id}", status_code=204, response_model=None)
async def remove_member(
    user_id: UUID,
    request: Request,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Remove a team member. Admin only, or self-removal."""
    svc = TeamService(session)
    team = await svc.get_team_for_user(current_user.id)
    if not team:
        raise NotFoundError("Team not found")

    await svc.remove_member(
        team_id=team.id,
        actor_id=current_user.id,
        target_user_id=user_id,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@router.get("/audit-log", response_model=PaginatedAuditLogResponse)
async def audit_log(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    action: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PaginatedAuditLogResponse:
    """List audit log entries. Admin only."""
    svc = TeamService(session)
    team = await svc.get_team_for_user(current_user.id)
    if not team:
        raise NotFoundError("Team not found")

    items, total = await svc.list_audit_log(
        team_id=team.id,
        actor_id=current_user.id,
        skip=skip,
        limit=limit,
        action=action,
    )

    return PaginatedAuditLogResponse(
        items=[AuditLogResponse(**entry) for entry in items],
        total=total,
        skip=skip,
        limit=limit,
    )
