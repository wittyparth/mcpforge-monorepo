"""Pydantic schemas for the Stripe billing flow (F7)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PlanInfo(BaseModel):
    """A single plan as returned by GET /api/v1/billing/plans."""

    id: Literal["free", "pro", "team"]
    name: str
    monthly_price_cents: int
    yearly_price_cents: int | None
    features: list[str]
    limits: dict[str, int] = Field(
        default_factory=dict,
        description="e.g., {'servers': 2, 'monthly_calls': 500}",
    )
    stripe_price_id_monthly: str | None = None
    stripe_price_id_yearly: str | None = None


class SubscribeRequest(BaseModel):
    """POST /api/v1/billing/subscribe — subscribe to a plan."""

    plan: Literal["pro", "team"]
    billing_cycle: Literal["monthly", "yearly"] = "monthly"
    seats: int = Field(default=1, ge=1, le=100, description="Only used for team plan")
    stripe_payment_method_id: str | None = Field(
        default=None,
        description="Stripe payment method ID; if null, the user is redirected to Stripe Checkout.",
    )


class SubscribeResponse(BaseModel):
    """Response for a subscribe request."""

    subscription_id: UUID
    plan: str
    status: str
    checkout_url: str | None = Field(
        default=None, description="URL to redirect to if user needs to complete payment via Stripe Checkout",
    )
    client_secret: str | None = Field(
        default=None, description="Stripe SetupIntent client secret for inline payment",
    )


class PortalResponse(BaseModel):
    """POST /api/v1/billing/portal — Stripe customer portal link."""

    url: str
    expires_at: datetime


class WebhookEvent(BaseModel):
    """Schema for Stripe webhook payloads (POST /api/v1/billing/webhook).

    This is a minimal schema; the full Stripe event types live in the
    `stripe` SDK. We accept a dict and validate structurally.
    """

    id: str
    type: str
    data: dict[str, object]
    created: datetime

    model_config = ConfigDict(extra="allow")
