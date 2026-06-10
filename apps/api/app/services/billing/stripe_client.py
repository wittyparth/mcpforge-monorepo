"""Stripe API client wrapper.

Wraps the synchronous ``stripe`` SDK with async-compatible helpers and
litigated-mode support so the application can run in development / CI
without a real Stripe account.

In litigated mode (``STRIPE_LITIGATED_MODE=True``), all methods return
hardcoded mock data so that frontend and integration tests function
without Stripe credentials.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Sentinel used to detect "no secret key configured"
_NO_KEY: str = ""


class StripeClient:
    """Thin async wrapper around the Stripe Python SDK.

    Every method that calls the Stripe API runs synchronously inside
    ``asyncio.to_thread`` so the event loop is never blocked.

    Litigated mode: When ``settings.STRIPE_LITIGATED_MODE`` is ``True``,
    all methods return minimal mock responses. No network calls are made.
    """

    def __init__(self) -> None:
        self._litigated = settings.STRIPE_LITIGATED_MODE
        self._api_key = settings.STRIPE_SECRET_KEY or _NO_KEY

        if not self._litigated and self._api_key:
            import stripe as _stripe

            _stripe.api_key = self._api_key
            self._stripe = _stripe
        else:
            self._stripe = None

    # ── Helpers ────────────────────────────────────────────────────────

    @property
    def _available(self) -> bool:
        """True if we can call the real Stripe API."""
        return bool(self._stripe) and not self._litigated

    async def _call(self, method: Any, *args: Any, **kwargs: Any) -> Any:
        """Run a synchronous Stripe SDK call in a thread pool."""
        return await asyncio.to_thread(method, *args, **kwargs)

    # ── Customer operations ────────────────────────────────────────────

    async def create_customer(
        self, email: str, name: str | None = None, user_id: str | None = None
    ) -> str:
        """Create a Stripe customer and return its ID.

        Args:
            email: The customer's email address.
            name: Optional display name.
            user_id: The internal MCPForge user UUID (stored in metadata).

        Returns:
            The Stripe customer ID (``cus_...``).
        """
        if not self._available:
            mock_id = f"cus_mock_{user_id or 'unknown'}"
            logger.info("stripe_litigated_create_customer", customer_id=mock_id, email=email)
            return mock_id

        metadata: dict[str, str] = {}
        if user_id:
            metadata["user_id"] = user_id

        assert self._stripe is not None
        customer = await self._call(
            self._stripe.Customer.create,
            email=email,
            name=name,
            metadata=metadata,
        )
        customer_id: str = customer.id
        logger.info("stripe_customer_created", customer_id=customer_id, email=email)
        return customer_id

    # ── Checkout sessions ──────────────────────────────────────────────

    async def create_checkout_session(
        self,
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        quantity: int = 1,
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Create a Stripe Checkout Session in subscription mode.

        Returns the session URL to which the user should be redirected.
        """
        if not self._available:
            mock_url = f"https://checkout.stripe.com/mock/cs_test_{customer_id[-8:]}"
            logger.info("stripe_litigated_checkout_session", url=mock_url)
            return mock_url

        assert self._stripe is not None
        session = await self._call(
            self._stripe.checkout.Session.create,
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": quantity}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata=metadata or {},
        )
        assert session.url is not None
        session_url: str = session.url
        logger.info("stripe_checkout_session_created", session_id=session.id)
        return session_url

    async def get_checkout_session(self, session_id: str) -> dict[str, Any]:
        """Retrieve a Stripe Checkout Session by ID."""
        if not self._available:
            return {"id": session_id, "customer": "cus_mock", "status": "complete"}

        assert self._stripe is not None
        session = await self._call(
            self._stripe.checkout.Session.retrieve,
            session_id,
        )
        return dict(session)

    # ── Customer portal ────────────────────────────────────────────────

    async def create_portal_session(self, customer_id: str, return_url: str) -> str:
        """Create a Stripe Billing Portal session.

        Returns the portal URL.
        """
        if not self._available:
            mock_url = f"https://billing.stripe.com/mock/session/{customer_id[-8:]}"
            logger.info("stripe_litigated_portal_session", url=mock_url)
            return mock_url

        assert self._stripe is not None
        session = await self._call(
            self._stripe.billing_portal.Session.create,
            customer=customer_id,
            return_url=return_url,
        )
        assert session.url is not None
        portal_url: str = session.url
        logger.info("stripe_portal_session_created", session_id=session.id)
        return portal_url

    # ── Subscription operations ────────────────────────────────────────

    async def get_subscription(self, stripe_sub_id: str) -> dict[str, Any]:
        """Retrieve a subscription by its Stripe ID."""
        if not self._available:
            return {
                "id": stripe_sub_id,
                "status": "active",
                "items": {"data": [{"price": {"id": "price_mock"}}]},
                "cancel_at_period_end": False,
                "current_period_end": 9999999999,
                "current_period_start": 1000000000,
                "customer": "cus_mock",
                "metadata": {},
            }

        assert self._stripe is not None
        sub = await self._call(
            self._stripe.Subscription.retrieve,
            stripe_sub_id,
        )
        return dict(sub)

    async def cancel_subscription(
        self, stripe_sub_id: str, at_period_end: bool = True
    ) -> dict[str, Any]:
        """Cancel a subscription.

        By default the cancellation takes effect at the end of the current
        billing period.
        """
        if not self._available:
            return {
                "id": stripe_sub_id,
                "status": "active" if at_period_end else "canceled",
                "cancel_at_period_end": at_period_end,
            }

        assert self._stripe is not None
        sub = await self._call(
            self._stripe.Subscription.update,
            stripe_sub_id,
            cancel_at_period_end=at_period_end,
        )
        return dict(sub)

    # ── Webhook signature verification ─────────────────────────────────

    def verify_webhook_signature(self, payload: bytes, sig_header: str) -> dict[str, Any]:
        """Verify a Stripe webhook signature and return the event object.

        Raises:
            ValueError: If the signature is invalid or Stripe is not configured.
        """
        if self._litigated:
            # In litigated mode, accept the raw payload as JSON directly.
            import json
            data: Any = json.loads(payload.decode("utf-8"))
            return dict(data)

        if not settings.STRIPE_WEBHOOK_SECRET:
            raise ValueError("STRIPE_WEBHOOK_SECRET is not configured")

        import stripe as _stripe

        try:
            event = _stripe.Webhook.construct_event(
                payload,
                sig_header,
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except _stripe.error.SignatureVerificationError as exc:
            logger.warning("stripe_webhook_signature_invalid", error=str(exc))
            raise ValueError("Invalid webhook signature") from exc

        result_event: dict[str, Any] = dict(event)
        return result_event
