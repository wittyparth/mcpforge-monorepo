"""Billing models (F7 — Stripe).

- `Subscription` belongs to either a user OR a team (CHECK constraint
  enforces "at least one"). Stripe IDs are stored alongside the local
  state for reconciliation.
- `Invoice` belongs to a Subscription. The `stripe_invoice_id` is the
  link back to Stripe; we never store the PDF in the DB (we link to it).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.team import Team
    from app.models.user import User


class Subscription(Base, UUIDMixin, TimestampMixin):
    """A Stripe subscription. Belongs to a user OR a team, never both."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        CheckConstraint(
            "user_id IS NOT NULL OR team_id IS NOT NULL",
            name="ck_subscription_owner",
        ),
    )

    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    team_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=True
    )
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(
        String(100), unique=True, nullable=True
    )
    plan: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    current_period_start: Mapped[datetime | None] = mapped_column(nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False)

    invoices: Mapped[list[Invoice]] = relationship(
        "Invoice", back_populates="subscription", cascade="all, delete-orphan"
    )
    team: Mapped[Team | None] = relationship("Team", back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription {self.plan} {self.status}>"


class Invoice(Base, UUIDMixin, TimestampMixin):
    """A Stripe invoice linked to a subscription."""

    __tablename__ = "invoices"

    subscription_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
    )
    stripe_invoice_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="usd")
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    invoice_pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    hosted_invoice_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    subscription: Mapped[Subscription] = relationship("Subscription", back_populates="invoices")

    def __repr__(self) -> str:
        return f"<Invoice {self.stripe_invoice_id} {self.status}>"
