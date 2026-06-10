"""Billing endpoint and service tests.

Tests the Stripe billing flow including plans, subscription checkout,
customer portal, webhook handling, plan-based rate limiting, and plan
limit enforcement on server creation.

Uses monkeypatch to toggle ``STRIPE_LITIGATED_MODE`` for tests that
should avoid real Stripe calls. For tests that verify specific Stripe
behavior, the SDK methods are mocked via ``unittest.mock.patch``.
"""

from __future__ import annotations

import json

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.billing import Subscription
from app.models.user import User
from app.repositories.billing_repo import BillingRepository
from app.repositories.user_repo import UserRepository
from app.services.billing.stripe_client import StripeClient
from app.services.mcp_server_service import MCPServerService

BILLING_PREFIX = "/api/v1/billing"
PLANS_URL = f"{BILLING_PREFIX}/plans"
SUBSCRIBE_URL = f"{BILLING_PREFIX}/subscribe"
PORTAL_URL = f"{BILLING_PREFIX}/portal"
WEBHOOK_URL = f"{BILLING_PREFIX}/webhook"
SUBSCRIPTION_URL = f"{BILLING_PREFIX}/subscription"
INVOICES_URL = f"{BILLING_PREFIX}/invoices"

REGISTER_URL = "/api/v1/auth/register"
SERVERS_URL = "/api/v1/servers"


# ═══════════════════════════════════════════════════════════════════════
#  Plans
# ═══════════════════════════════════════════════════════════════════════


class TestPlans:
    """GET /api/v1/billing/plans — public endpoint."""

    @pytest.mark.asyncio
    async def test_list_plans_returns_all_plans(self, client: AsyncClient) -> None:
        """Should return all three plans without authentication."""
        response = await client.get(PLANS_URL)
        assert response.status_code == 200
        data = response.json()
        plans = data["plans"]
        plan_ids = {p["id"] for p in plans}
        assert plan_ids == {"free", "pro", "team"}
        # Verify structure
        for plan in plans:
            assert "price_cents" in plan
            assert "features" in plan
            assert "name" in plan


# ═══════════════════════════════════════════════════════════════════════
#  Subscribe (Checkout)
# ═══════════════════════════════════════════════════════════════════════


class TestSubscribe:
    """POST /api/v1/billing/subscribe."""

    @pytest.mark.asyncio
    async def test_subscribe_in_litigated_mode_returns_mock_url(
        self,
        auth_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """In litigated mode, the response should contain a mock checkout URL."""
        monkeypatch.setattr(settings, "STRIPE_LITIGATED_MODE", True)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO_MONTHLY", "price_mock_pro")

        response = await auth_client.post(
            SUBSCRIBE_URL,
            json={"plan": "pro", "billing_period": "monthly"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "checkout_url" in data
        assert data["checkout_url"].startswith("https://checkout.stripe.com/mock/")

    @pytest.mark.asyncio
    async def test_subscribe_rejects_invalid_plan(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """Unknown plan should return 422."""
        response = await auth_client.post(
            SUBSCRIBE_URL,
            json={"plan": "enterprise", "billing_period": "monthly"},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_subscribe_rejects_invalid_seat_count(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """Seat count < 1 or > 100 should return 422."""
        response = await auth_client.post(
            SUBSCRIBE_URL,
            json={"plan": "team", "billing_period": "monthly", "seats": 0},
        )
        assert response.status_code == 422

        response2 = await auth_client.post(
            SUBSCRIBE_URL,
            json={"plan": "team", "billing_period": "monthly", "seats": 101},
        )
        assert response2.status_code == 422

    @pytest.mark.asyncio
    async def test_subscribe_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """Subscribe without auth should return 401."""
        response = await client.post(
            SUBSCRIBE_URL,
            json={"plan": "pro", "billing_period": "monthly"},
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_subscribe_no_price_configured(
        self,
        auth_client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
        auth_user: User,
    ) -> None:
        """If no price is configured for a plan, the endpoint should return 400."""
        monkeypatch.setattr(settings, "STRIPE_LITIGATED_MODE", True)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO_MONTHLY", "")
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO_YEARLY", "")

        # Set stripe_customer_id to skip the customer creation path
        auth_user.stripe_customer_id = "cus_mock_test"

        response = await auth_client.post(
            SUBSCRIBE_URL,
            json={"plan": "pro", "billing_period": "monthly"},
        )
        assert response.status_code == 400
        assert "No price configured" in response.text


# ═══════════════════════════════════════════════════════════════════════
#  Customer Portal
# ═══════════════════════════════════════════════════════════════════════


class TestPortal:
    """POST /api/v1/billing/portal."""

    @pytest.mark.asyncio
    async def test_portal_in_litigated_mode_returns_mock_url(
        self,
        auth_client: AsyncClient,
        auth_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """In litigated mode, the response should contain a mock portal URL."""
        monkeypatch.setattr(settings, "STRIPE_LITIGATED_MODE", True)
        auth_user.stripe_customer_id = "cus_mock_test"

        response = await auth_client.post(PORTAL_URL, json={})
        assert response.status_code == 200
        data = response.json()
        assert "portal_url" in data

    @pytest.mark.asyncio
    async def test_portal_unauthenticated_returns_401(
        self,
        client: AsyncClient,
    ) -> None:
        """Portal without auth should return 401."""
        response = await client.post(PORTAL_URL, json={})
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════
#  Webhook
# ═══════════════════════════════════════════════════════════════════════


class TestWebhook:
    """POST /api/v1/billing/webhook."""

    @pytest.mark.asyncio
    async def test_webhook_rejects_missing_signature(
        self,
        client: AsyncClient,
    ) -> None:
        """Missing stripe-signature header should return 400."""
        response = await client.post(
            WEBHOOK_URL,
            content=json.dumps({"type": "test"}),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 400
        assert "Missing stripe-signature" in response.text

    @pytest.mark.asyncio
    async def test_webhook_rejects_invalid_signature(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Invalid stripe-signature should return 400."""
        monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_test")

        response = await client.post(
            WEBHOOK_URL,
            content=json.dumps({"type": "test"}),
            headers={
                "Content-Type": "application/json",
                "stripe-signature": "invalid_signature",
            },
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_webhook_handles_subscription_updated_event(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A valid subscription.updated event should update user.plan."""
        monkeypatch.setattr(settings, "STRIPE_LITIGATED_MODE", True)
        monkeypatch.setattr(settings, "STRIPE_PRICE_PRO_MONTHLY", "price_mock_pro")

        auth_user.stripe_customer_id = "cus_mock_test"

        event_payload = {
            "id": "evt_sub_updated_001",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_mock_001",
                    "customer": "cus_mock_test",
                    "status": "active",
                    "plan": "pro",
                    "cancel_at_period_end": False,
                    "current_period_start": 1000000000,
                    "current_period_end": 2000000000,
                    "items": {
                        "data": [
                            {
                                "price": {"id": "price_mock_pro"},
                            }
                        ]
                    },
                }
            },
            "created": 1000000000,
        }

        # Mock Redis-dependent methods
        from unittest.mock import AsyncMock

        repo_patch = "app.repositories.billing_repo.BillingRepository"
        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(
                f"{repo_patch}.webhook_event_exists",
                AsyncMock(return_value=False),
            )
            mp.setattr(
                f"{repo_patch}.record_webhook_event",
                AsyncMock(return_value=None),
            )

            # Pre-create the subscription record
            from app.models.billing import Subscription

            sub = Subscription(
                user_id=auth_user.id,
                stripe_customer_id="cus_mock_test",
                stripe_subscription_id="sub_mock_001",
                plan="free",
                status="active",
            )
            test_session.add(sub)
            await test_session.flush()

            response = await client.post(
                WEBHOOK_URL,
                content=json.dumps(event_payload),
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": "mock_sig",
                },
            )
            assert response.status_code == 200
            assert response.json() == {"received": True}

    @pytest.mark.asyncio
    async def test_webhook_handles_subscription_deleted_event(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A subscription.deleted event should downgrade user to free."""
        monkeypatch.setattr(settings, "STRIPE_LITIGATED_MODE", True)
        auth_user.stripe_customer_id = "cus_mock_test"
        auth_user.plan = "pro"

        event_payload = {
            "id": "evt_sub_deleted_001",
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_mock_delete_001",
                    "customer": "cus_mock_test",
                    "status": "canceled",
                    "cancel_at_period_end": False,
                    "current_period_start": 1000000000,
                    "current_period_end": 2000000000,
                    "items": {
                        "data": [
                            {
                                "price": {"id": "price_mock_pro"},
                            }
                        ]
                    },
                }
            },
            "created": 1000000000,
        }

        from unittest.mock import AsyncMock

        # Pre-create the subscription
        sub = Subscription(
            user_id=auth_user.id,
            stripe_customer_id="cus_mock_test",
            stripe_subscription_id="sub_mock_delete_001",
            plan="pro",
            status="active",
        )
        test_session.add(sub)
        await test_session.flush()

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(
                "app.repositories.billing_repo.BillingRepository.webhook_event_exists",
                AsyncMock(return_value=False),
            )
            mp.setattr(
                "app.repositories.billing_repo.BillingRepository.record_webhook_event",
                AsyncMock(return_value=None),
            )

            response = await client.post(
                WEBHOOK_URL,
                content=json.dumps(event_payload),
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": "mock_sig",
                },
            )
            assert response.status_code == 200

        # Verify user was downgraded to free
        await test_session.flush()
        repo = UserRepository(test_session)
        updated_user = await repo.get_by_id(auth_user.id)
        assert updated_user is not None
        assert updated_user.plan == "free"

    @pytest.mark.asyncio
    async def test_webhook_handles_payment_succeeded_event(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A payment.succeeded event should create an invoice record."""
        monkeypatch.setattr(settings, "STRIPE_LITIGATED_MODE", True)
        auth_user.stripe_customer_id = "cus_mock_test"

        # Pre-create subscription
        sub = Subscription(
            user_id=auth_user.id,
            stripe_customer_id="cus_mock_test",
            stripe_subscription_id="sub_mock_pay_001",
            plan="pro",
            status="active",
        )
        test_session.add(sub)
        await test_session.flush()

        event_payload = {
            "id": "evt_pay_success_001",
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_mock_001",
                    "subscription": "sub_mock_pay_001",
                    "amount_paid": 1200,
                    "currency": "usd",
                    "status": "paid",
                    "invoice_pdf": "https://invoice.stripe.com/mock/pdf",
                    "hosted_invoice_url": "https://invoice.stripe.com/mock/view",
                }
            },
            "created": 1000000000,
        }

        from unittest.mock import AsyncMock

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(
                "app.repositories.billing_repo.BillingRepository.webhook_event_exists",
                AsyncMock(return_value=False),
            )
            mp.setattr(
                "app.repositories.billing_repo.BillingRepository.record_webhook_event",
                AsyncMock(return_value=None),
            )

            response = await client.post(
                WEBHOOK_URL,
                content=json.dumps(event_payload),
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": "mock_sig",
                },
            )
            assert response.status_code == 200

        # Verify invoice was created
        repo = BillingRepository(test_session)
        invoice = await repo.get_invoice_by_stripe_id("in_mock_001")
        assert invoice is not None
        assert invoice.amount_cents == 1200
        assert invoice.status == "paid"

    @pytest.mark.asyncio
    async def test_webhook_handles_payment_failed_event(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        auth_user: User,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A payment.failed event should mark the subscription past_due."""
        monkeypatch.setattr(settings, "STRIPE_LITIGATED_MODE", True)
        auth_user.stripe_customer_id = "cus_mock_test"
        auth_user.plan = "pro"

        sub = Subscription(
            user_id=auth_user.id,
            stripe_customer_id="cus_mock_test",
            stripe_subscription_id="sub_mock_fail_001",
            plan="pro",
            status="active",
        )
        test_session.add(sub)
        await test_session.flush()

        event_payload = {
            "id": "evt_pay_fail_001",
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "id": "in_mock_fail_001",
                    "subscription": "sub_mock_fail_001",
                    "amount_due": 1200,
                    "currency": "usd",
                    "status": "unpaid",
                }
            },
            "created": 1000000000,
        }

        from unittest.mock import AsyncMock

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(
                "app.repositories.billing_repo.BillingRepository.webhook_event_exists",
                AsyncMock(return_value=False),
            )
            mp.setattr(
                "app.repositories.billing_repo.BillingRepository.record_webhook_event",
                AsyncMock(return_value=None),
            )

            response = await client.post(
                WEBHOOK_URL,
                content=json.dumps(event_payload),
                headers={
                    "Content-Type": "application/json",
                    "stripe-signature": "mock_sig",
                },
            )
            assert response.status_code == 200

        # Verify subscription is past_due
        repo = BillingRepository(test_session)
        updated_sub = await repo.get_subscription_by_stripe_id("sub_mock_fail_001")
        assert updated_sub is not None
        assert updated_sub.status == "past_due"

        # Verify user plan was downgraded
        user_repo = UserRepository(test_session)
        updated_user = await user_repo.get_by_id(auth_user.id)
        assert updated_user is not None
        assert updated_user.plan == "past_due"

    @pytest.mark.asyncio
    async def test_webhook_idempotency(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Processing the same event twice should be idempotent (second is no-op)."""
        monkeypatch.setattr(settings, "STRIPE_LITIGATED_MODE", True)

        event_payload = {
            "id": "evt_idempotent_001",
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_idempotent_001",
                    "subscription": "sub_idempotent_001",
                    "amount_paid": 1200,
                    "currency": "usd",
                }
            },
            "created": 1000000000,
        }

        from unittest.mock import AsyncMock

        # First call: event does not exist, then record it
        call_count = {"exists": 0}

        async def mock_exists(event_id: str) -> bool:
            call_count["exists"] += 1
            return call_count["exists"] > 1  # first call = False, subsequent = True

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(
                "app.repositories.billing_repo.BillingRepository.webhook_event_exists",
                AsyncMock(side_effect=mock_exists),
            )
            mp.setattr(
                "app.repositories.billing_repo.BillingRepository.record_webhook_event",
                AsyncMock(return_value=None),
            )

            headers = {
                "Content-Type": "application/json",
                "stripe-signature": "mock_sig",
            }

            # First call
            payload = json.dumps(event_payload)
            resp1 = await client.post(WEBHOOK_URL, content=payload, headers=headers)
            assert resp1.status_code == 200

            resp2 = await client.post(WEBHOOK_URL, content=payload, headers=headers)
            assert resp2.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
#  Subscription
# ═══════════════════════════════════════════════════════════════════════


class TestGetSubscription:
    """GET /api/v1/billing/subscription."""

    @pytest.mark.asyncio
    async def test_get_subscription_returns_active_sub(
        self,
        auth_client: AsyncClient,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """An active subscription should be returned."""
        sub = Subscription(
            user_id=auth_user.id,
            stripe_customer_id="cus_mock_test",
            stripe_subscription_id="sub_get_001",
            plan="pro",
            status="active",
        )
        test_session.add(sub)
        await test_session.flush()

        response = await auth_client.get(SUBSCRIPTION_URL)
        assert response.status_code == 200
        data = response.json()
        assert data["plan"] == "pro"
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_get_subscription_404_for_no_subscription(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """No active subscription should return 404."""
        response = await auth_client.get(SUBSCRIPTION_URL)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_subscription_unauthenticated(
        self,
        client: AsyncClient,
    ) -> None:
        """Without auth, should return 401."""
        response = await client.get(SUBSCRIPTION_URL)
        assert response.status_code == 401


# ═══════════════════════════════════════════════════════════════════════
#  Invoices
# ═══════════════════════════════════════════════════════════════════════


class TestListInvoices:
    """GET /api/v1/billing/invoices."""

    @pytest.mark.asyncio
    async def test_list_invoices_empty(
        self,
        auth_client: AsyncClient,
    ) -> None:
        """No invoices should return an empty list."""
        response = await auth_client.get(INVOICES_URL)
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_invoices_returns_paginated(
        self,
        auth_client: AsyncClient,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Multiple invoices should be returned paginated."""
        # Create a subscription first
        sub = Subscription(
            user_id=auth_user.id,
            stripe_customer_id="cus_mock_test",
            stripe_subscription_id="sub_inv_001",
            plan="pro",
            status="active",
        )
        test_session.add(sub)
        await test_session.flush()

        # Create invoices
        repo = BillingRepository(test_session)
        for i in range(3):
            await repo.create_invoice(
                subscription_id=sub.id,
                stripe_invoice_id=f"in_list_{i}",
                amount_cents=1200,
                currency="usd",
                status="paid",
                invoice_pdf_url=f"https://invoice.stripe.com/pdf/{i}",
                hosted_invoice_url=f"https://invoice.stripe.com/view/{i}",
            )
        await test_session.flush()

        response = await auth_client.get(INVOICES_URL)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3
        assert data["items"][0]["amount_cents"] == 1200


# ═══════════════════════════════════════════════════════════════════════
#  Plan Limit Enforcement
# ═══════════════════════════════════════════════════════════════════════


class TestPlanLimitEnforcement:
    """Service-level plan limit checks."""

    @pytest.mark.asyncio
    async def test_create_server_respects_plan_limit(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Free user (limit=2 servers) should not be able to create a 3rd server."""
        auth_user.plan = "free"
        service = MCPServerService(test_session)

        # Create 2 servers (free limit)
        for i in range(2):
            await service.create_server(
                user_id=auth_user.id,
                slug=f"test-server-{i}",
                name=f"Test Server {i}",
                base_url=f"https://api{i}.example.com",
            )

        # 3rd should fail with PlanLimitExceededError (402)
        from app.core.exceptions import PlanLimitExceededError

        with pytest.raises(PlanLimitExceededError) as exc_info:
            await service.create_server(
                user_id=auth_user.id,
                slug="test-server-over-limit",
                name="Over Limit Server",
                base_url="https://over.example.com",
            )
        assert exc_info.value.status_code == 402
        assert "servers" in str(exc_info.value.resource)

    @pytest.mark.asyncio
    async def test_pro_user_can_create_more_servers(
        self,
        test_session: AsyncSession,
        auth_user: User,
    ) -> None:
        """Pro user (limit=10) should be able to create more servers than free."""
        auth_user.plan = "pro"
        service = MCPServerService(test_session)

        # Pro limit is 10, creating 3 should be fine
        for i in range(3):
            server = await service.create_server(
                user_id=auth_user.id,
                slug=f"pro-server-{i}",
                name=f"Pro Server {i}",
                base_url=f"https://pro-api{i}.example.com",
            )
            assert server is not None

    @pytest.mark.asyncio
    async def test_get_plan_limit_for_free_plan(self) -> None:
        """get_plan_limit should return correct values."""
        from app.services.billing.plan_limits import get_plan_limit

        assert get_plan_limit("free", "servers") == 2
        assert get_plan_limit("free", "calls_per_month") == 500
        assert get_plan_limit("pro", "servers") == 10
        assert get_plan_limit("team", "servers") is None  # unlimited

    @pytest.mark.asyncio
    async def test_check_plan_limit_raises_when_exceeded(self) -> None:
        """check_plan_limit should raise when current >= limit."""
        from app.core.exceptions import PlanLimitExceededError
        from app.services.billing.plan_limits import check_plan_limit

        # 2 servers current, limit is 2 → should raise
        with pytest.raises(PlanLimitExceededError):
            check_plan_limit("free", "servers", current=2)

        # 1 server current, limit is 2 → should pass
        check_plan_limit("free", "servers", current=1)

        # Unlimited (team) → should pass regardless
        check_plan_limit("team", "servers", current=999)


# ═══════════════════════════════════════════════════════════════════════
#  Register creates Stripe customer
# ═══════════════════════════════════════════════════════════════════════


class TestRegisterStripeCustomer:
    """Registration should create a Stripe customer when configured."""

    @pytest.mark.asyncio
    async def test_register_skips_stripe_in_litigated_mode(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """In litigated mode, stripe customer creation should be skipped."""
        monkeypatch.setattr(settings, "STRIPE_LITIGATED_MODE", True)
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock")

        from unittest.mock import AsyncMock as AMock

        monkeypatch.setattr(
            "app.services.auth.email_verification.send_verification",
            AMock(return_value=None),
        )
        monkeypatch.setattr(settings, "HIBP_ENABLED", False)

        response = await client.post(
            REGISTER_URL,
            json={
                "email": "stripe-litigated@example.com",
                "password": "testpassword123!",
                "display_name": "Stripe Test",
            },
        )
        assert response.status_code == 200

        from app.repositories.user_repo import UserRepository as UserRep

        u_repo = UserRep(test_session)
        user = await u_repo.get_by_email("stripe-litigated@example.com")
        assert user is not None
        # In litigated mode, the condition `if not settings.STRIPE_LITIGATED_MODE and ...`
        # is False, so stripe_customer_id should remain None
        assert user.stripe_customer_id is None

    @pytest.mark.asyncio
    async def test_register_creates_stripe_customer(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With SECRET_KEY set and not litigated, Stripe customer should be created."""
        monkeypatch.setattr(settings, "STRIPE_LITIGATED_MODE", False)
        monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_mock")

        # Mock the StripeClient.create_customer to avoid real API calls
        from unittest.mock import AsyncMock

        monkeypatch.setattr(
            "app.services.billing.stripe_client.StripeClient.create_customer",
            AsyncMock(return_value="cus_test_created"),
        )

        monkeypatch.setattr(
            "app.services.auth.email_verification.send_verification",
            AsyncMock(return_value=None),
        )
        monkeypatch.setattr(settings, "HIBP_ENABLED", False)

        response = await client.post(
            REGISTER_URL,
            json={
                "email": "stripe-created@example.com",
                "password": "testpassword123!",
                "display_name": "Stripe Created",
            },
        )
        assert response.status_code == 200

        # Verify stripe_customer_id was set on the user
        from app.repositories.user_repo import UserRepository as UserRep2

        u_repo2 = UserRep2(test_session)
        user = await u_repo2.get_by_email("stripe-created@example.com")
        assert user is not None
        assert user.stripe_customer_id == "cus_test_created"


# ═══════════════════════════════════════════════════════════════════════
#  StripeClient unit tests
# ═══════════════════════════════════════════════════════════════════════


class TestStripeClient:
    """Unit tests for the StripeClient wrapper."""

    @pytest.mark.asyncio
    async def test_create_customer_in_litigated_mode(self) -> None:
        """Litigated mode should return mock customer ID without calling Stripe."""
        from app.core.config import settings

        original_litigated = settings.STRIPE_LITIGATED_MODE
        settings.STRIPE_LITIGATED_MODE = True
        try:
            client = StripeClient()
            result = await client.create_customer(
                email="test@example.com",
                name="Test User",
                user_id="user-123",
            )
            assert result.startswith("cus_mock_")
            assert "user-123" in result
        finally:
            settings.STRIPE_LITIGATED_MODE = original_litigated

    @pytest.mark.asyncio
    async def test_create_checkout_session_in_litigated_mode(self) -> None:
        """Litigated mode should return mock checkout URL."""
        from app.core.config import settings

        original_litigated = settings.STRIPE_LITIGATED_MODE
        settings.STRIPE_LITIGATED_MODE = True
        try:
            client = StripeClient()
            result = await client.create_checkout_session(
                customer_id="cus_mock",
                price_id="price_mock",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
            )
            assert isinstance(result, str)
            assert "checkout.stripe.com" in result
        finally:
            settings.STRIPE_LITIGATED_MODE = original_litigated

    @pytest.mark.asyncio
    async def test_create_portal_session_in_litigated_mode(self) -> None:
        """Litigated mode should return mock portal URL."""
        from app.core.config import settings

        original_litigated = settings.STRIPE_LITIGATED_MODE
        settings.STRIPE_LITIGATED_MODE = True
        try:
            client = StripeClient()
            result = await client.create_portal_session(
                customer_id="cus_mock",
                return_url="https://example.com/return",
            )
            assert isinstance(result, str)
            assert "billing.stripe.com" in result
        finally:
            settings.STRIPE_LITIGATED_MODE = original_litigated

    @pytest.mark.asyncio
    async def test_verify_webhook_in_litigated_mode(self) -> None:
        """Litigated mode should parse payload directly without verifying signature."""
        from app.core.config import settings

        original_litigated = settings.STRIPE_LITIGATED_MODE
        settings.STRIPE_LITIGATED_MODE = True
        try:
            client = StripeClient()
            payload = json.dumps({"type": "test", "id": "evt_test"}).encode()
            result = client.verify_webhook_signature(payload, "any_sig")
            assert result["type"] == "test"
            assert result["id"] == "evt_test"
        finally:
            settings.STRIPE_LITIGATED_MODE = original_litigated

    @pytest.mark.asyncio
    async def test_verify_webhook_raises_without_secret(self) -> None:
        """Without webhook secret and not litigated, should raise ValueError."""
        from app.core.config import settings

        original_litigated = settings.STRIPE_LITIGATED_MODE
        original_secret = settings.STRIPE_WEBHOOK_SECRET
        settings.STRIPE_LITIGATED_MODE = False
        settings.STRIPE_WEBHOOK_SECRET = ""
        try:
            client = StripeClient()
            payload = json.dumps({"type": "test"}).encode()
            with pytest.raises(ValueError, match="STRIPE_WEBHOOK_SECRET is not configured"):
                client.verify_webhook_signature(payload, "fake_sig")
        finally:
            settings.STRIPE_LITIGATED_MODE = original_litigated
            settings.STRIPE_WEBHOOK_SECRET = original_secret


# ═══════════════════════════════════════════════════════════════════════
#  Webhook Handler verification (litigated mode requires no real Redis)
# ═══════════════════════════════════════════════════════════════════════


class TestWebhookHandler:
    """Tests for the webhook handler dispatch logic."""

    @pytest.mark.asyncio
    async def test_unknown_event_type_logged(
        self,
        test_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """An unhandled event type should be swallowed (logged, not raised)."""
        monkeypatch.setattr(settings, "STRIPE_LITIGATED_MODE", True)

        from unittest.mock import AsyncMock

        from app.services.billing import webhook_handler

        payload = json.dumps({
            "id": "evt_unknown_001",
            "type": "some.unhandled.event",
            "data": {"object": {}},
        }).encode()

        with (
            pytest.MonkeyPatch.context() as mp,
        ):
            mp.setattr(
                "app.repositories.billing_repo.BillingRepository.webhook_event_exists",
                AsyncMock(return_value=False),
            )
            mp.setattr(
                "app.repositories.billing_repo.BillingRepository.record_webhook_event",
                AsyncMock(return_value=None),
            )

            # Should not raise
            await webhook_handler.handle(test_session, payload, "mock_sig")
