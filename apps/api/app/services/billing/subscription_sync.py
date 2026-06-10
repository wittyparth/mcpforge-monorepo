"""Keep the local database in sync with Stripe subscription state.

Each webhook event from Stripe is processed by the corresponding ``on_*``
function, which maps Stripe price IDs to MCPForge plan names and updates
the local ``Subscription`` and ``User`` records accordingly.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.billing import Subscription
from app.models.user import User
from app.repositories.billing_repo import BillingRepository
from app.repositories.user_repo import UserRepository

logger = get_logger(__name__)

# Map Stripe price IDs → MCPForge plan names.
# Populated at runtime from settings so they can differ per-environment.
_PRICE_TO_PLAN: dict[str, str] | None = None


def _get_price_to_plan() -> dict[str, str]:
    """Build the price → plan mapping from settings (lazy)."""
    global _PRICE_TO_PLAN
    if _PRICE_TO_PLAN is None:
        mapping: dict[str, str] = {}
        if settings.STRIPE_PRICE_PRO_MONTHLY:
            mapping[settings.STRIPE_PRICE_PRO_MONTHLY] = "pro"
        if settings.STRIPE_PRICE_PRO_YEARLY:
            mapping[settings.STRIPE_PRICE_PRO_YEARLY] = "pro"
        if settings.STRIPE_PRICE_TEAM_SEAT_MONTHLY:
            mapping[settings.STRIPE_PRICE_TEAM_SEAT_MONTHLY] = "team"
        _PRICE_TO_PLAN = mapping
    return _PRICE_TO_PLAN


def _extract_plan_from_subscription(stripe_sub: dict[str, Any]) -> str | None:
    """Extract the MCPForge plan name from a Stripe subscription object.

    Looks at the first price item's ID and matches it against the
    configured price IDs. Returns ``None`` if no price matches (unknown
    plan).
    """
    price_to_plan = _get_price_to_plan()
    items = stripe_sub.get("items", {}).get("data", [])
    for item in items:
        price_id = item.get("price", {}).get("id")
        if price_id and price_id in price_to_plan:
            return price_to_plan[price_id]
    return None


def _ts_from_stripe(stripe_timestamp: int | None) -> datetime | None:
    """Convert a Stripe Unix timestamp to a Python ``datetime``."""
    if stripe_timestamp is None:
        return None
    return datetime.fromtimestamp(stripe_timestamp, tz=UTC)


async def sync_subscription(
    session: AsyncSession,
    stripe_sub: dict[str, Any],
) -> Subscription | None:
    """Upsert a Subscription record from a Stripe subscription object.

    Creates a new record if none exists for the Stripe subscription ID;
    otherwise updates the existing record.
    """
    repo = BillingRepository(session)
    stripe_id: str = stripe_sub["id"]
    plan = _extract_plan_from_subscription(stripe_sub)

    if plan is None:
        logger.warning(
            "stripe_unknown_price_id",
            stripe_sub_id=stripe_id,
            items=stripe_sub.get("items"),
        )
        return None

    existing = await repo.get_subscription_by_stripe_id(stripe_id)
    if existing:
        existing.status = stripe_sub.get("status", existing.status)
        existing.cancel_at_period_end = stripe_sub.get("cancel_at_period_end", False)
        existing.current_period_start = _ts_from_stripe(stripe_sub.get("current_period_start"))
        existing.current_period_end = _ts_from_stripe(stripe_sub.get("current_period_end"))
        if not existing.stripe_customer_id:
            existing.stripe_customer_id = stripe_sub.get("customer")
        existing.plan = plan
        await session.flush()
        return existing

    # New subscription — find the owning user via customer ID
    customer_id: str = stripe_sub.get("customer", "")
    user = await repo.get_user_by_stripe_customer_id(customer_id)
    if user is None:
        logger.warning(
            "stripe_unknown_customer",
            stripe_sub_id=stripe_id,
            customer_id=customer_id,
        )
        return None

    sub = await repo.create_subscription(
        user_id=user.id,
        stripe_customer_id=customer_id,
        stripe_subscription_id=stripe_id,
        plan=plan,
        status=stripe_sub.get("status", "active"),
        current_period_start=_ts_from_stripe(stripe_sub.get("current_period_start")),
        current_period_end=_ts_from_stripe(stripe_sub.get("current_period_end")),
    )
    return sub


def _update_user_plan(session: AsyncSession, user: User, plan: str, status: str) -> None:
    """Update a user's plan field in-place (does NOT flush)."""
    if status in ("active", "trialing"):
        user.plan = plan
    elif status in ("past_due", "incomplete"):
        user.plan = "past_due"
    elif status in ("canceled", "unpaid"):
        user.plan = "free"


async def on_subscription_updated(
    session: AsyncSession,
    stripe_sub: dict[str, Any],
) -> None:
    """Handle ``customer.subscription.updated`` (and ``created``).

    Syncs the local subscription record and updates the owning user's
    plan.
    """
    sub = await sync_subscription(session, stripe_sub)
    if not sub:
        return

    user_repo = UserRepository(session)
    if sub.user_id:
        user = await user_repo.get_by_id(sub.user_id)
        if user:
            _update_user_plan(session, user, sub.plan, sub.status)
            await session.flush()
            logger.info(
                "subscription_updated",
                user_id=str(sub.user_id),
                plan=sub.plan,
                status=sub.status,
                stripe_sub_id=sub.stripe_subscription_id,
            )


async def on_subscription_deleted(
    session: AsyncSession,
    stripe_sub: dict[str, Any],
) -> None:
    """Handle ``customer.subscription.deleted``.

    Marks the local subscription as canceled and downgrades the user to
    the free plan if the cancellation has taken effect (past period end).
    """
    repo = BillingRepository(session)
    stripe_id: str = stripe_sub["id"]
    sub = await repo.get_subscription_by_stripe_id(stripe_id)

    if not sub:
        logger.warning("subscription_deleted_unknown", stripe_sub_id=stripe_id)
        return

    sub.status = "canceled"
    sub.cancel_at_period_end = False
    await session.flush()

    user_repo = UserRepository(session)
    if sub.user_id:
        user = await user_repo.get_by_id(sub.user_id)
        if user:
            user.plan = "free"
            await session.flush()
            logger.info(
                "subscription_cancelled",
                user_id=str(sub.user_id),
                stripe_sub_id=stripe_id,
            )


async def on_payment_succeeded(
    session: AsyncSession,
    stripe_invoice: dict[str, Any],
) -> None:
    """Handle ``invoice.payment_succeeded``.

    Creates or updates the local Invoice record and logs the event.
    """
    repo = BillingRepository(session)
    stripe_invoice_id: str = stripe_invoice["id"]

    existing = await repo.get_invoice_by_stripe_id(stripe_invoice_id)
    if existing:
        existing.status = "paid"
        await session.flush()
        return

    # Find the subscription
    stripe_sub_id = stripe_invoice.get("subscription")
    if not stripe_sub_id:
        logger.warning("invoice_no_subscription", invoice_id=stripe_invoice_id)
        return

    sub = await repo.get_subscription_by_stripe_id(stripe_sub_id)
    if not sub:
        logger.warning("invoice_unknown_subscription", stripe_sub_id=stripe_sub_id)
        return

    amount_cents = stripe_invoice.get("amount_paid", 0) or stripe_invoice.get("total", 0)
    invoice = await repo.create_invoice(
        subscription_id=sub.id,
        stripe_invoice_id=stripe_invoice_id,
        amount_cents=amount_cents,
        currency=stripe_invoice.get("currency", "usd"),
        status="paid",
        invoice_pdf_url=stripe_invoice.get("invoice_pdf"),
        hosted_invoice_url=stripe_invoice.get("hosted_invoice_url"),
    )

    logger.info(
        "payment_succeeded",
        user_id=str(sub.user_id) if sub.user_id else None,
        amount_cents=amount_cents,
        invoice_id=invoice.id,
    )


async def on_payment_failed(
    session: AsyncSession,
    stripe_invoice: dict[str, Any],
) -> None:
    """Handle ``invoice.payment_failed``.

    Records the failed invoice, sets the subscription status to
    ``past_due``, and logs a warning.
    """
    repo = BillingRepository(session)
    stripe_invoice_id: str = stripe_invoice["id"]
    stripe_sub_id = stripe_invoice.get("subscription")

    if not stripe_sub_id:
        logger.warning("payment_failed_no_subscription", invoice_id=stripe_invoice_id)
        return

    sub = await repo.get_subscription_by_stripe_id(stripe_sub_id)
    if not sub:
        logger.warning("payment_failed_unknown_subscription", stripe_sub_id=stripe_sub_id)
        return

    amount_cents = stripe_invoice.get("amount_due", 0)
    existing = await repo.get_invoice_by_stripe_id(stripe_invoice_id)
    if not existing:
        await repo.create_invoice(
            subscription_id=sub.id,
            stripe_invoice_id=stripe_invoice_id,
            amount_cents=amount_cents,
            currency=stripe_invoice.get("currency", "usd"),
            status="unpaid",
            invoice_pdf_url=stripe_invoice.get("invoice_pdf"),
            hosted_invoice_url=stripe_invoice.get("hosted_invoice_url"),
        )

    # Mark subscription as past_due
    sub.status = "past_due"
    await session.flush()

    # Downgrade user plan
    user_repo = UserRepository(session)
    if sub.user_id:
        user = await user_repo.get_by_id(sub.user_id)
        if user:
            user.plan = "past_due"
            await session.flush()

    logger.warning(
        "payment_failed",
        user_id=str(sub.user_id) if sub.user_id else None,
        invoice_id=stripe_invoice_id,
        amount_cents=amount_cents,
    )
