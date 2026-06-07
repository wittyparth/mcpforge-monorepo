"""Team management endpoints (F7) — route stubs."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.core.exceptions import NotImplementedFeatureError

router = APIRouter(prefix="/team", tags=["team"])


@router.get("", status_code=501)
async def get_team() -> None:
    """Get the current user's team. Pending F7."""
    raise NotImplementedFeatureError("Teams: pending F7")


@router.post("", status_code=501)
async def create_team() -> None:
    """Create a new team. Pending F7."""
    raise NotImplementedFeatureError("Teams: pending F7")


@router.patch("", status_code=501)
async def update_team() -> None:
    """Update team name/plan. Pending F7."""
    raise NotImplementedFeatureError("Teams: pending F7")


@router.post("/invite", status_code=501)
async def invite_member() -> None:
    """Invite a user by email. Pending F7."""
    raise NotImplementedFeatureError("Teams: pending F7")


@router.get("/members", status_code=501)
async def list_members() -> None:
    """List all team members. Pending F7."""
    raise NotImplementedFeatureError("Teams: pending F7")


@router.patch("/members/{user_id}", status_code=501)
async def update_member(user_id: UUID) -> None:
    """Update a member's role. Pending F7."""
    raise NotImplementedFeatureError("Teams: pending F7")


@router.delete("/members/{user_id}", status_code=501)
async def remove_member(user_id: UUID) -> None:
    """Remove a member. Pending F7."""
    raise NotImplementedFeatureError("Teams: pending F7")


@router.get("/audit-log", status_code=501)
async def audit_log() -> None:
    """List audit log entries. Pending F7."""
    raise NotImplementedFeatureError("Teams: pending F7")
