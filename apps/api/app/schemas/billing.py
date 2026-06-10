"""Pydantic schemas for the Stripe billing flow (F7)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PlanInfo(BaseModel):
    """A single plan as returned by GET /api/v1/billing/plans."""

    id: str
    name: str
    price_cents: int
    currency: str = "usd"
    period: str = "monthly"
    features: list[str]
    popular: bool = False
    min_seats: int | None = None


class PlansResponse(BaseModel):
    """Response for GET /api/v1/billing/plans."""

    plans: list[PlanInfo]


class SubscribeRequest(BaseModel):
    """POST /api/v1/billing/subscribe — subscribe to a plan."""

    plan: Literal["pro", "team"]
    billing_period: Literal["monthly", "yearly"] = "monthly"
    seats: int = Field(default=1, ge=1, le=100, description="Number of seats (team plan only)")


class CheckoutResponse(BaseModel):
    """Response for a successful checkout session creation."""

    checkout_url: str
    session_id: str


class PortalRequest(BaseModel):
    """POST /api/v1/billing/portal — get a Stripe customer portal link."""

    return_url: str | None = None


class PortalResponse(BaseModel):
    """Response for a successful portal session creation."""

    portal_url: str


class SubscriptionResponse(BaseModel):
    """A user's current subscription."""

    id: UUID
    plan: str
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    cancel_at_period_end: bool = False


class InvoiceResponse(BaseModel):
    """A single invoice."""

    id: UUID
    amount_cents: int
    currency: str
    status: str
    invoice_pdf_url: str | None = None
    hosted_invoice_url: str | None = None
    created_at: datetime


class InvoicesListResponse(BaseModel):
    """Paginated list of invoices."""

    items: list[InvoiceResponse]
    total: int
    skip: int = 0
    limit: int = 20
