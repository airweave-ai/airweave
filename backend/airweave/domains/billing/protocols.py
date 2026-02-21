"""Billing domain protocols.

BillingServiceProtocol — the only thing billing endpoints need injected.
BillingWebhookProtocol — single method for webhook event processing.
"""

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.schemas.organization_billing import SubscriptionInfo


@runtime_checkable
class BillingServiceProtocol(Protocol):
    """Public billing service interface.

    8 public methods — the only thing billing API endpoints need injected.
    """

    async def start_subscription_checkout(
        self,
        db: AsyncSession,
        plan: str,
        success_url: str,
        cancel_url: str,
        ctx: ApiContext,
    ) -> str:
        """Start a subscription checkout flow. Returns checkout URL."""
        ...

    async def start_yearly_prepay_checkout(
        self,
        db: AsyncSession,
        *,
        plan: str,
        success_url: str,
        cancel_url: str,
        ctx: ApiContext,
    ) -> str:
        """Start a yearly prepay checkout flow. Returns checkout URL."""
        ...

    async def update_subscription_plan(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        new_plan: str,
        period: str = "monthly",
    ) -> str:
        """Update subscription to a new plan. Returns status message."""
        ...

    async def cancel_subscription(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Cancel subscription at period end. Returns status message."""
        ...

    async def reactivate_subscription(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Reactivate a canceled subscription. Returns status message."""
        ...

    async def cancel_pending_plan_change(
        self,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> str:
        """Cancel a pending plan change. Returns status message."""
        ...

    async def create_customer_portal_session(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        return_url: str,
    ) -> str:
        """Create Stripe customer portal session. Returns portal URL."""
        ...

    async def get_subscription_info(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        at: Optional[datetime] = None,
    ) -> SubscriptionInfo:
        """Get comprehensive subscription information."""
        ...


@runtime_checkable
class BillingWebhookProtocol(Protocol):
    """Webhook processing interface — verifies signature and processes event."""

    async def process_webhook(self, db: AsyncSession, payload: bytes, signature: str) -> None:
        """Verify webhook signature and process the resulting event."""
        ...
