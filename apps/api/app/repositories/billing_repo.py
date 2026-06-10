"""Billing data access layer.

Provides CRUD for Subscription and Invoice models as well as webhook
event idempotency helpers backed by Redis.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_pool
from app.models.billing import Invoice, Subscription

_WEBHOOK_TTL_SECONDS = 7 * 86400  # 7 days
_WEBHOOK_KEY_PREFIX = "wh_event:"


class BillingRepository:
    """Repository for Subscription and Invoice operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── Subscription CRUD ──────────────────────────────────────────────

    async def create_subscription(
        self,
        user_id: UUID | None = None,
        team_id: UUID | None = None,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        plan: str = "free",
        status: str = "incomplete",
        current_period_start: datetime | None = None,
        current_period_end: datetime | None = None,
    ) -> Subscription:
        """Create a new subscription record."""
        sub = Subscription(
            user_id=user_id,
            team_id=team_id,
            stripe_customer_id=stripe_customer_id,
            stripe_subscription_id=stripe_subscription_id,
            plan=plan,
            status=status,
            current_period_start=current_period_start,
            current_period_end=current_period_end,
        )
        self.session.add(sub)
        await self.session.flush()
        return sub

    async def get_subscription_by_stripe_id(
        self,
        stripe_subscription_id: str,
    ) -> Subscription | None:
        """Look up a subscription by its Stripe subscription ID."""
        result = await self.session.execute(
            select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_subscription_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_active_subscription_for_user(
        self,
        user_id: UUID,
    ) -> Subscription | None:
        """Return the active subscription for a user, if any."""
        result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.status.in_({"active", "trialing", "past_due"}),
            )
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_active_subscription_for_team(
        self,
        team_id: UUID,
    ) -> Subscription | None:
        """Return the active subscription for a team, if any."""
        result = await self.session.execute(
            select(Subscription)
            .where(
                Subscription.team_id == team_id,
                Subscription.status.in_({"active", "trialing", "past_due"}),
            )
            .order_by(Subscription.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_subscription_status(
        self,
        stripe_subscription_id: str,
        status: str,
        cancel_at_period_end: bool = False,
        current_period_end: datetime | None = None,
    ) -> Subscription | None:
        """Update subscription fields matched by Stripe subscription ID."""
        sub = await self.get_subscription_by_stripe_id(stripe_subscription_id)
        if not sub:
            return None
        sub.status = status
        sub.cancel_at_period_end = cancel_at_period_end
        if current_period_end is not None:
            sub.current_period_end = current_period_end
        await self.session.flush()
        return sub

    # ── Invoice CRUD ──────────────────────────────────────────────────

    async def create_invoice(
        self,
        subscription_id: UUID,
        stripe_invoice_id: str,
        amount_cents: int,
        currency: str = "usd",
        status: str = "pending",
        invoice_pdf_url: str | None = None,
        hosted_invoice_url: str | None = None,
    ) -> Invoice:
        """Create a new invoice record."""
        inv = Invoice(
            subscription_id=subscription_id,
            stripe_invoice_id=stripe_invoice_id,
            amount_cents=amount_cents,
            currency=currency,
            status=status,
            invoice_pdf_url=invoice_pdf_url,
            hosted_invoice_url=hosted_invoice_url,
        )
        self.session.add(inv)
        await self.session.flush()
        return inv

    async def get_invoice_by_stripe_id(self, stripe_invoice_id: str) -> Invoice | None:
        """Look up an invoice by its Stripe invoice ID."""
        result = await self.session.execute(
            select(Invoice).where(Invoice.stripe_invoice_id == stripe_invoice_id),
        )
        return result.scalar_one_or_none()

    async def list_invoices_for_user(
        self,
        user_id: UUID,
        skip: int = 0,
        limit: int = 20,
    ) -> list[Invoice]:
        """List invoices for a user's subscriptions."""
        result = await self.session.execute(
            select(Invoice)
            .join(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Invoice.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_invoices_for_user(self, user_id: UUID) -> int:
        """Count invoices for a user's subscriptions."""
        result = await self.session.execute(
            select(Invoice)
            .join(Subscription)
            .where(Subscription.user_id == user_id)
        )
        return len(list(result.scalars().all()))

    # ── Webhook idempotency (Redis-backed) ─────────────────────────────

    async def webhook_event_exists(self, stripe_event_id: str) -> bool:
        """Check whether a Stripe event has already been processed."""
        from redis.asyncio import Redis

        pool = await get_redis_pool()
        redis = Redis.from_pool(pool)
        try:
            exists = await redis.exists(f"{_WEBHOOK_KEY_PREFIX}{stripe_event_id}")
            return bool(exists)
        finally:
            await redis.close()

    async def record_webhook_event(self, stripe_event_id: str, event_type: str) -> None:
        """Store a Stripe event ID for idempotency with a 7-day TTL."""
        from redis.asyncio import Redis

        pool = await get_redis_pool()
        redis = Redis.from_pool(pool)
        try:
            await redis.setex(
                f"{_WEBHOOK_KEY_PREFIX}{stripe_event_id}",
                _WEBHOOK_TTL_SECONDS,
                event_type,
            )
        finally:
            await redis.close()

    # ── User helpers ───────────────────────────────────────────────────

    async def get_user_by_stripe_customer_id(self, stripe_customer_id: str) -> Any | None:
        """Look up a user by their Stripe customer ID."""
        from app.models.user import User

        result = await self.session.execute(
            select(User).where(User.stripe_customer_id == stripe_customer_id),
        )
        return result.scalar_one_or_none()
