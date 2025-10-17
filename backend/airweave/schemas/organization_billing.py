"""Organization billing schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

if TYPE_CHECKING:
    from airweave.schemas.billing_period import BillingPeriod


class BillingPlan(str, Enum):
    """Billing plan tiers."""

    TRIAL = "trial"
    DEVELOPER = "developer"
    PRO = "pro"
    TEAM = "team"
    ENTERPRISE = "enterprise"

    @classmethod
    def normalize(cls, value: str) -> "BillingPlan":
        """Normalize billing plan values from database to enum.

        Handles legacy uppercase values and STARTUP -> PRO mapping.
        """
        if not value:
            return cls.TRIAL

        # Map old database values to new enum values
        value_lower = value.lower()
        mapping = {
            "trial": cls.TRIAL,
            "developer": cls.DEVELOPER,
            "pro": cls.PRO,
            "startup": cls.PRO,  # Legacy mapping
            "team": cls.TEAM,
            "enterprise": cls.ENTERPRISE,
        }

        return mapping.get(value_lower, cls.TRIAL)


class BillingStatus(str, Enum):
    """Billing subscription status."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    PAUSED = "paused"
    TRIALING = "trialing"
    TRIAL_EXPIRED = "trial_expired"
    GRACE_PERIOD = "grace_period"

    @classmethod
    def normalize(cls, value: str) -> "BillingStatus":
        """Normalize billing status values from database to enum.

        Handles legacy uppercase values.
        """
        if not value:
            return cls.ACTIVE

        # Map old database values to new enum values
        value_lower = value.lower()
        mapping = {
            "active": cls.ACTIVE,
            "past_due": cls.PAST_DUE,
            "canceled": cls.CANCELED,
            "paused": cls.PAUSED,
            "trialing": cls.TRIALING,
            "trial_expired": cls.TRIAL_EXPIRED,
            "grace_period": cls.GRACE_PERIOD,
        }

        return mapping.get(value_lower, cls.ACTIVE)


class PaymentStatus(str, Enum):
    """Payment status."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PENDING = "pending"

    @classmethod
    def normalize(cls, value: str) -> "PaymentStatus":
        """Normalize payment status values from database to enum.

        Handles legacy uppercase values.
        """
        if not value:
            return cls.PENDING

        # Map old database values to new enum values
        value_lower = value.lower()
        mapping = {
            "succeeded": cls.SUCCEEDED,
            "failed": cls.FAILED,
            "pending": cls.PENDING,
        }

        return mapping.get(value_lower, cls.PENDING)


class OrganizationBillingBase(BaseModel):
    """Organization billing base schema."""

    billing_plan: BillingPlan = Field(default=BillingPlan.TRIAL, description="Current billing plan")
    billing_status: BillingStatus = Field(
        default=BillingStatus.ACTIVE, description="Current billing status"
    )
    billing_email: str = Field(..., description="Billing contact email")

    @field_validator("billing_plan", mode="before")
    @classmethod
    def normalize_billing_plan(cls, v: Any) -> BillingPlan:
        """Normalize billing plan from database format."""
        if isinstance(v, BillingPlan):
            return v
        if isinstance(v, str):
            return BillingPlan.normalize(v)
        return BillingPlan.TRIAL

    @field_validator("billing_status", mode="before")
    @classmethod
    def normalize_billing_status(cls, v: Any) -> BillingStatus:
        """Normalize billing status from database format."""
        if isinstance(v, BillingStatus):
            return v
        if isinstance(v, str):
            return BillingStatus.normalize(v)
        return BillingStatus.ACTIVE


class OrganizationBillingCreate(OrganizationBillingBase):
    """Organization billing creation schema."""

    stripe_customer_id: str = Field(..., description="Stripe customer ID")
    trial_ends_at: Optional[datetime] = Field(None, description="Trial end date")
    grace_period_ends_at: Optional[datetime] = Field(None, description="Grace period end date")


class OrganizationBillingUpdate(BaseModel):
    """Organization billing update schema."""

    billing_plan: Optional[BillingPlan] = None
    billing_status: Optional[BillingStatus] = None
    billing_email: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    payment_method_id: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    grace_period_ends_at: Optional[datetime] = None
    payment_method_added: Optional[bool] = None
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: Optional[bool] = None
    pending_plan_change: Optional[BillingPlan] = None
    pending_plan_change_at: Optional[datetime] = None
    last_payment_status: Optional[PaymentStatus] = None
    last_payment_at: Optional[datetime] = None
    billing_metadata: Optional[Dict[str, Any]] = None
    # Yearly prepay fields
    has_yearly_prepay: Optional[bool] = None
    yearly_prepay_started_at: Optional[datetime] = None
    yearly_prepay_expires_at: Optional[datetime] = None
    yearly_prepay_amount_cents: Optional[int] = None
    yearly_prepay_coupon_id: Optional[str] = None
    yearly_prepay_payment_intent_id: Optional[str] = None


class OrganizationBillingInDBBase(OrganizationBillingBase):
    """Organization billing base schema in the database."""

    model_config = {"from_attributes": True}

    id: UUID
    organization_id: UUID
    stripe_customer_id: str
    stripe_subscription_id: Optional[str] = None
    trial_ends_at: Optional[datetime] = None
    grace_period_ends_at: Optional[datetime] = None
    payment_method_added: bool = False
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False
    # Pending plan change fields (take effect at renewal)
    pending_plan_change: Optional[BillingPlan] = None
    pending_plan_change_at: Optional[datetime] = None
    payment_method_id: Optional[str] = None
    last_payment_status: Optional[str] = None
    last_payment_at: Optional[datetime] = None
    billing_metadata: Optional[Dict[str, Any]] = None
    # Yearly prepay fields
    has_yearly_prepay: bool = False
    yearly_prepay_started_at: Optional[datetime] = None
    yearly_prepay_expires_at: Optional[datetime] = None
    yearly_prepay_amount_cents: Optional[int] = None
    yearly_prepay_coupon_id: Optional[str] = None
    yearly_prepay_payment_intent_id: Optional[str] = None
    created_at: datetime
    modified_at: datetime

    @field_validator("pending_plan_change", mode="before")
    @classmethod
    def normalize_pending_plan(cls, v: Any) -> Optional[BillingPlan]:
        """Normalize pending plan change from database format."""
        if v is None:
            return None
        if isinstance(v, BillingPlan):
            return v
        if isinstance(v, str):
            return BillingPlan.normalize(v)
        return None

    @field_validator("last_payment_status", mode="before")
    @classmethod
    def normalize_payment_status(cls, v: Any) -> Optional[str]:
        """Normalize payment status from database format to lowercase."""
        if v is None:
            return None
        if isinstance(v, str):
            return v.lower()
        return None


class OrganizationBilling(OrganizationBillingInDBBase):
    """Organization billing schema with current period information.

    This schema is enriched with the current active billing period for
    efficient access to rate limits and billing status without additional queries.
    """

    current_period: Optional["BillingPeriod"] = Field(
        None,
        description="Current active billing period",
    )


class PlanLimits(BaseModel):
    """Plan limits configuration."""

    source_connections: int = Field(..., description="Number of allowed source connections")
    entities_per_month: int = Field(..., description="Number of entities allowed per month")
    sync_frequency_minutes: int = Field(..., description="Minimum sync frequency in minutes")
    team_members: int = Field(..., description="Number of allowed team members")


class SubscriptionInfo(BaseModel):
    """Subscription information response."""

    plan: str = Field(..., description="Current billing plan")
    status: str = Field(..., description="Subscription status")
    trial_ends_at: Optional[datetime] = Field(None, description="Trial end date")
    grace_period_ends_at: Optional[datetime] = Field(None, description="Grace period end date")
    current_period_start: Optional[datetime] = Field(
        None, description="Current billing period start"
    )
    current_period_end: Optional[datetime] = Field(None, description="Current billing period end")
    cancel_at_period_end: bool = Field(
        False, description="Whether subscription will cancel at period end"
    )
    limits: Dict[str, Any] = Field(..., description="Plan limits")
    is_oss: bool = Field(False, description="Whether using OSS version")
    has_active_subscription: bool = Field(
        False, description="Whether has active Stripe subscription"
    )
    in_trial: bool = Field(False, description="Whether currently in trial period")
    in_grace_period: bool = Field(False, description="Whether currently in grace period")
    payment_method_added: bool = Field(False, description="Whether payment method is added")
    requires_payment_method: bool = Field(
        False, description="Whether payment method is required now"
    )
    # Add pending plan change info
    pending_plan_change: Optional[str] = Field(
        None, description="Plan that will take effect at period end"
    )
    pending_plan_change_at: Optional[datetime] = Field(
        None, description="When the pending plan change takes effect"
    )
    # Yearly prepay summary fields
    has_yearly_prepay: bool = Field(
        False, description="Whether organization has an active yearly prepay credit"
    )
    yearly_prepay_started_at: Optional[datetime] = Field(
        None, description="When yearly prepay was started"
    )
    yearly_prepay_expires_at: Optional[datetime] = Field(
        None, description="When yearly prepay expires"
    )
    yearly_prepay_amount_cents: Optional[int] = Field(
        None, description="Total amount (in cents) credited for yearly prepay"
    )
    yearly_prepay_coupon_id: Optional[str] = Field(
        None, description="Coupon ID used for yearly prepay"
    )
    yearly_prepay_payment_intent_id: Optional[str] = Field(
        None, description="Payment intent ID used for yearly prepay"
    )


# Request/Response schemas for API endpoints
class CheckoutSessionRequest(BaseModel):
    """Request to create a checkout session."""

    plan: str = Field(..., description="Plan to subscribe to (developer, startup)")
    success_url: str = Field(..., description="URL to redirect on successful payment")
    cancel_url: str = Field(..., description="URL to redirect on cancellation")


class CheckoutSessionResponse(BaseModel):
    """Response with checkout session URL."""

    checkout_url: str = Field(..., description="Stripe checkout URL")


class CustomerPortalRequest(BaseModel):
    """Request to create customer portal session."""

    return_url: str = Field(..., description="URL to return to after portal session")


class CustomerPortalResponse(BaseModel):
    """Response with customer portal URL."""

    portal_url: str = Field(..., description="Stripe customer portal URL")


class CancelSubscriptionRequest(BaseModel):
    """Request to cancel subscription.

    Subscription will be canceled at the end of the current billing period.
    For immediate cancellation, delete the organization instead.
    """

    # No fields needed - always cancels at period end


class UpdatePlanRequest(BaseModel):
    """Request to update subscription plan."""

    plan: str = Field(..., description="New plan (developer, startup)")
    period: Optional[str] = Field(
        default="monthly",
        description="Billing period for the plan: 'monthly' or 'yearly'",
    )


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str = Field(..., description="Response message")
