"""Stripe billing endpoints (F7).

Endpoints:
- GET  /billing/plans        — list available plans (public)
- POST /billing/subscribe    — create a Stripe Checkout session
- POST /billing/portal       — create a Stripe Customer Portal session
- POST /billing/webhook      — receive Stripe webhook events (no auth)
- GET  /billing/subscription — get the current user's active subscription
- GET  /billing/invoices     — list invoices for the current user's subscription
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.core.logging import get_logger
from app.models.user import User
from app.repositories.billing_repo import BillingRepository
from app.schemas.billing import (
    CheckoutResponse,
    InvoiceResponse,
    InvoicesListResponse,
    PlanInfo,
    PlansResponse,
    PortalRequest,
    PortalResponse,
    SubscribeRequest,
    SubscriptionResponse,
)
from app.services.billing import webhook_handler
from app.services.billing.plan_limits import PLAN_DETAILS
from app.services.billing.stripe_client import StripeClient

logger = get_logger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


def _price_id_for_plan(plan: str, period: str) -> str | None:
    """Resolve the Stripe price ID for a given plan and billing period."""
    if plan == "pro":
        if period == "monthly":
            return settings.STRIPE_PRICE_PRO_MONTHLY
        return settings.STRIPE_PRICE_PRO_YEARLY
    if plan == "team":
        return settings.STRIPE_PRICE_TEAM_SEAT_MONTHLY
    return None


# ── Public endpoints ───────────────────────────────────────────────────


@router.get("/plans", response_model=PlansResponse)
async def list_plans() -> PlansResponse:
    """List available plans (free, pro, team). No authentication required."""
    plans_list: list[PlanInfo] = []
    for detail in PLAN_DETAILS:
        plan_id_val: object | None = detail.get("id")
        if not isinstance(plan_id_val, str) or plan_id_val not in ("free", "pro", "team"):
            continue
        features_raw = detail.get("features", [])
        features_list: list[str] = list(features_raw) if isinstance(features_raw, list) else []
        price_obj = detail.get("monthly_price_cents", 0)
        price_cents_val = price_obj if isinstance(price_obj, int) else 0
        plans_list.append(
            PlanInfo(
                id=plan_id_val,
                name=str(detail.get("name", "")),
                price_cents=price_cents_val,
                period="monthly_per_seat" if plan_id_val == "team" else "monthly",
                features=features_list,
                popular=(plan_id_val == "pro"),
                min_seats=2 if plan_id_val == "team" else None,
            )
        )
    return PlansResponse(plans=plans_list)


# ── Authenticated endpoints ───────────────────────────────────────────


@router.post("/subscribe", response_model=CheckoutResponse)
async def subscribe(
    body: SubscribeRequest,
    user: User = Depends(get_current_user),
) -> CheckoutResponse:
    """Create a Stripe Checkout session for subscribing to a plan.

    If the user does not yet have a Stripe customer ID, one is created
    first.
    """
    stripe_client = StripeClient()

    # Resolve price ID
    price_id = _price_id_for_plan(body.plan, body.billing_period)
    if not price_id:
        msg = f"No price configured for plan '{body.plan}' / '{body.billing_period}'"
        raise HTTPException(status_code=400, detail=msg)

    # Ensure the user has a Stripe customer ID
    customer_id = user.stripe_customer_id
    if not customer_id:
        customer_id = await stripe_client.create_customer(
            email=user.email,
            name=user.display_name,
            user_id=str(user.id),
        )
        from app.api.deps import get_db as _get_db
        from app.repositories.user_repo import UserRepository

        async for session in _get_db():
            repo = UserRepository(session)
            user.stripe_customer_id = customer_id
            await repo.update(user, stripe_customer_id=customer_id)
            break

    success_url = f"{settings.FRONTEND_URL}/dashboard/billing?success=true"
    cancel_url = f"{settings.FRONTEND_URL}/dashboard/billing?canceled=true"

    quantity = body.seats if body.plan == "team" else 1
    checkout_url = await stripe_client.create_checkout_session(
        customer_id=customer_id,
        price_id=price_id,
        success_url=success_url,
        cancel_url=cancel_url,
        quantity=quantity,
    )

    logger.info(
        "checkout_session_created",
        user_id=str(user.id),
        plan=body.plan,
        checkout_url=checkout_url,
    )

    return CheckoutResponse(checkout_url=checkout_url, session_id=f"cs_{user.id}")


@router.post("/portal", response_model=PortalResponse)
async def customer_portal(
    body: PortalRequest,
    user: User = Depends(get_current_user),
) -> PortalResponse:
    """Create a Stripe Customer Portal session for managing the subscription."""
    stripe_client = StripeClient()
    return_url = body.return_url or f"{settings.FRONTEND_URL}/dashboard/billing"

    # Ensure the user has a Stripe customer ID
    customer_id = user.stripe_customer_id
    if not customer_id:
        customer_id = await stripe_client.create_customer(
            email=user.email,
            name=user.display_name,
            user_id=str(user.id),
        )
        from app.api.deps import get_db as _get_db
        from app.repositories.user_repo import UserRepository

        async for session in _get_db():
            repo = UserRepository(session)
            user.stripe_customer_id = customer_id
            await repo.update(user, stripe_customer_id=customer_id)
            break

    portal_url = await stripe_client.create_portal_session(
        customer_id=customer_id,
        return_url=return_url,
    )

    logger.info("portal_session_created", user_id=str(user.id), portal_url=portal_url)

    return PortalResponse(portal_url=portal_url)


# ── Webhook (no auth) ────────────────────────────────────────────────


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    """Receive Stripe webhook events.

    Signature-verified and idempotent via 7-day Redis TTL on event IDs.
    No authentication required.
    """
    raw_payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not sig_header:
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    try:
        await webhook_handler.handle(session, raw_payload, sig_header)
    except ValueError as exc:
        logger.warning("webhook_signature_invalid", error=str(exc))
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"received": True}


# ── Subscription details ─────────────────────────────────────────────


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> SubscriptionResponse:
    """Get the current user's active subscription.

    Raises 404 if no active subscription is found.
    """
    repo = BillingRepository(session)
    sub = await repo.get_active_subscription_for_user(user.id)
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription found")

    return SubscriptionResponse(
        id=sub.id,
        plan=sub.plan,
        status=sub.status,
        current_period_start=sub.current_period_start,
        current_period_end=sub.current_period_end,
        cancel_at_period_end=sub.cancel_at_period_end,
    )


# ── Invoice history ──────────────────────────────────────────────────


@router.get("/invoices", response_model=InvoicesListResponse)
async def list_invoices(
    skip: int = 0,
    limit: int = 20,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> InvoicesListResponse:
    """List invoices for the current user's subscription (paginated)."""
    repo = BillingRepository(session)
    invoices = await repo.list_invoices_for_user(user.id, skip=skip, limit=limit)
    total = await repo.count_invoices_for_user(user.id)

    return InvoicesListResponse(
        items=[
            InvoiceResponse(
                id=inv.id,
                amount_cents=inv.amount_cents,
                currency=inv.currency,
                status=inv.status,
                invoice_pdf_url=inv.invoice_pdf_url,
                hosted_invoice_url=inv.hosted_invoice_url,
                created_at=inv.created_at,
            )
            for inv in invoices
        ],
        total=total,
        skip=skip,
        limit=limit,
    )
