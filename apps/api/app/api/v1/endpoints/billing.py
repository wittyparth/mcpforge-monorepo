"""Stripe billing endpoints (F7) — route stubs."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.exceptions import NotImplementedFeatureError

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/plans", status_code=501)
async def list_plans() -> None:
    """List available plans (free, pro, team). Pending F7."""
    raise NotImplementedFeatureError("Billing: pending F7")


@router.post("/subscribe", status_code=501)
async def subscribe() -> None:
    """Subscribe to a plan (Pro or Team). Pending F7."""
    raise NotImplementedFeatureError("Billing: pending F7")


@router.post("/portal", status_code=501)
async def customer_portal() -> None:
    """Get a Stripe customer portal link. Pending F7."""
    raise NotImplementedFeatureError("Billing: pending F7")


@router.post("/webhook", status_code=501)
async def stripe_webhook() -> None:
    """Stripe webhook receiver. Pending F7."""
    raise NotImplementedFeatureError("Billing: pending F7")
