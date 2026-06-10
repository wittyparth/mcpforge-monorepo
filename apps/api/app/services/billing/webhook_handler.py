"""Stripe webhook event dispatcher.

Verifies the webhook signature, deduplicates by event ID (7-day Redis
window), then dispatches to the appropriate ``subscription_sync``
handler.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories.billing_repo import BillingRepository
from app.services.billing import subscription_sync
from app.services.billing.stripe_client import StripeClient

logger = get_logger(__name__)

# Map Stripe event types → handler functions.
# Each handler receives (session, event_data_object).
_EVENT_HANDLERS: dict[str, Any] = {
    "customer.subscription.created": subscription_sync.on_subscription_updated,
    "customer.subscription.updated": subscription_sync.on_subscription_updated,
    "customer.subscription.deleted": subscription_sync.on_subscription_deleted,
    "invoice.payment_succeeded": subscription_sync.on_payment_succeeded,
    "invoice.payment_failed": subscription_sync.on_payment_failed,
}


async def handle(
    session: AsyncSession,
    raw_payload: bytes,
    sig_header: str,
) -> None:
    """Verify, deduplicate, and dispatch a Stripe webhook event.

    Args:
        session: An active database session.
        raw_payload: The raw request body (bytes) from Stripe.
        sig_header: The value of the ``stripe-signature`` header.

    Raises:
        ValueError: If the signature is invalid.
    """
    stripe_client = StripeClient()

    # 1. Verify signature & parse event
    event: dict[str, Any] = stripe_client.verify_webhook_signature(raw_payload, sig_header)
    event_id: str = event.get("id", "")
    event_type: str = event.get("type", "")
    event_data: dict[str, Any] = event.get("data", {}).get("object", {})

    if not event_id:
        logger.warning("stripe_webhook_missing_event_id")
        return

    # 2. Idempotency check
    repo = BillingRepository(session)
    already_processed = await repo.webhook_event_exists(event_id)
    if already_processed:
        logger.info("stripe_webhook_already_processed", event_id=event_id, type=event_type)
        return

    # 3. Record event ID (prevents duplicate processing)
    await repo.record_webhook_event(event_id, event_type)

    # 4. Dispatch to handler
    handler = _EVENT_HANDLERS.get(event_type)
    if handler is None:
        logger.info("stripe_webhook_unhandled_type", type=event_type, event_id=event_id)
        return

    try:
        await handler(session, event_data)
        logger.info(
            "stripe_webhook_handled",
            event_id=event_id,
            type=event_type,
            handler=handler.__name__,
        )
    except Exception:
        logger.exception(
            "stripe_webhook_handler_failed",
            event_id=event_id,
            type=event_type,
            handler=handler.__name__,
        )
        raise
