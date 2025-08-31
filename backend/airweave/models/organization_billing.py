"""Organization billing model."""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.core.config import settings
from airweave.models._base import Base

if TYPE_CHECKING:
    from airweave.models.organization import Organization


class OrganizationBilling(Base):
    """Organization billing model."""

    __tablename__ = "organization_billing"

    # Foreign key to organization
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"), unique=True
    )

    # Stripe IDs
    stripe_customer_id: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Billing plan and status
    billing_plan: Mapped[str] = mapped_column(
        String(50), default=lambda: settings.DEFAULT_BILLING_PLAN, nullable=False
    )
    billing_status: Mapped[str] = mapped_column(String(50), default="ACTIVE", nullable=False)

    # Trial tracking - now only used for tracking Stripe's trial
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # Grace period tracking for when payment method is not set
    grace_period_ends_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    payment_method_added: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Subscription period tracking
    current_period_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    current_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Pending plan change tracking (for downgrades)
    pending_plan_change: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pending_plan_change_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # Billing contact
    billing_email: Mapped[str] = mapped_column(String, nullable=False)

    # Payment information
    payment_method_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_payment_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_payment_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=False), nullable=True
    )

    # Metadata for additional billing info
    billing_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, default={})

    # Relationship back to organization
    organization: Mapped["Organization"] = relationship("Organization", back_populates="billing")
