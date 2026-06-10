"""Plan limit constants and helpers.

Defines the resource limits for each subscription tier and provides
convenience functions to check whether a user's current plan allows
a given operation.
"""

from __future__ import annotations

from app.core.exceptions import PlanLimitExceededError

PLAN_LIMITS: dict[str, dict[str, int | None]] = {
    "free": {
        "servers": 2,
        "calls_per_month": 500,
        "calls_per_hour": 60,
        "ai_credits_per_month": 3,
        "team_seats": 1,
        "api_keys": 5,
    },
    "pro": {
        "servers": 10,
        "calls_per_month": 10_000,
        "calls_per_hour": 1_000,
        "ai_credits_per_month": 100,
        "team_seats": 5,
        "api_keys": 20,
    },
    "team": {
        "servers": None,  # unlimited
        "calls_per_month": 100_000,
        "calls_per_hour": 10_000,
        "ai_credits_per_month": 1_000,
        "team_seats": 20,
        "api_keys": 50,
    },
}

# Plan display info for the /billing/plans endpoint
PLAN_DETAILS: list[dict[str, object]] = [
    {
        "id": "free",
        "name": "Free",
        "monthly_price_cents": 0,
        "yearly_price_cents": None,
        "features": [
            "Up to 2 MCP servers",
            "500 API calls per month",
            "3 AI enhancement credits",
            "1 team seat",
            "5 API keys",
        ],
        "limits": PLAN_LIMITS["free"],
        "stripe_price_id_monthly": None,
        "stripe_price_id_yearly": None,
    },
    {
        "id": "pro",
        "name": "Pro",
        "monthly_price_cents": 1200,  # $12
        "yearly_price_cents": 12000,  # $120 ($10/mo)
        "features": [
            "Up to 10 MCP servers",
            "10,000 API calls per month",
            "100 AI enhancement credits",
            "5 team seats",
            "20 API keys",
            "Priority support",
        ],
        "limits": PLAN_LIMITS["pro"],
        "stripe_price_id_monthly": None,  # populated at runtime from settings
        "stripe_price_id_yearly": None,
    },
    {
        "id": "team",
        "name": "Team",
        "monthly_price_cents": 2900,  # $29/seat/mo
        "yearly_price_cents": 29000,  # $290/seat/yr
        "features": [
            "Unlimited MCP servers",
            "100,000 API calls per month",
            "1,000 AI enhancement credits",
            "20 team seats",
            "50 API keys",
            "Priority support",
            "Audit logs",
            "SSO (coming soon)",
        ],
        "limits": PLAN_LIMITS["team"],
        "stripe_price_id_monthly": None,
        "stripe_price_id_yearly": None,
    },
]


def get_plan_limit(plan: str, resource: str) -> int | None:
    """Return the numeric limit for a given plan and resource.

    Returns ``None`` when the resource is unlimited.
    Raises ``KeyError`` if the plan or resource does not exist.
    """
    return PLAN_LIMITS[plan][resource]


def check_plan_limit(
    plan: str,
    resource: str,
    current: int,
) -> None:
    """Raise ``PlanLimitExceededError`` if ``current >= limit``.

    If the plan has no limit for this resource (``None``), the check
    passes silently.
    """
    limit = get_plan_limit(plan, resource)
    if limit is not None and current >= limit:
        raise PlanLimitExceededError(
            message=(
                f"Your {plan} plan allows up to {limit} {resource}. "
                "Upgrade to increase this limit."
            ),
            resource=resource,
            current=current,
            limit=limit,
        )
