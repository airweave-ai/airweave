"""Webhook protocols.

Two protocols based on consumer needs:
- WebhookPublisher: Internal use (event bus subscriber publishes events)
- WebhookAdmin: External API (users manage subscriptions, view history)

All WebhookAdmin methods raise WebhooksError on failure.
"""

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable
from uuid import UUID

from airweave.domains.webhooks.types import (
    DeliveryAttempt,
    EventMessage,
    RecoveryTask,
    Subscription,
)


@runtime_checkable
class WebhookPublisher(Protocol):
    """Publish domain events to external webhook subscribers.

    Generic interface: accepts any event_type string and payload dict.
    The event bus subscriber builds the payload from domain events;
    the adapter just delivers it.
    """

    async def publish_event(
        self,
        org_id: UUID,
        event_type: str,
        payload: dict,
    ) -> None:
        """Publish an event to all subscribed webhook endpoints."""
        ...


@runtime_checkable
class WebhookAdmin(Protocol):
    """Manage webhook subscriptions and view message history.

    Used by API endpoints. External user-facing.
    All methods raise WebhooksError on failure.
    """

    # -------------------------------------------------------------------------
    # Subscriptions
    # -------------------------------------------------------------------------

    async def list_subscriptions(
        self,
        org_id: UUID,
    ) -> list[Subscription]:
        """List all subscriptions for an organization."""
        ...

    async def get_subscription(
        self,
        org_id: UUID,
        subscription_id: str,
    ) -> Subscription:
        """Get a specific subscription."""
        ...

    async def create_subscription(
        self,
        org_id: UUID,
        url: str,
        event_types: list[str],
        secret: Optional[str] = None,
    ) -> Subscription:
        """Create a new subscription."""
        ...

    async def update_subscription(
        self,
        org_id: UUID,
        subscription_id: str,
        url: Optional[str] = None,
        event_types: Optional[list[str]] = None,
        disabled: Optional[bool] = None,
    ) -> Subscription:
        """Update a subscription."""
        ...

    async def delete_subscription(
        self,
        org_id: UUID,
        subscription_id: str,
    ) -> None:
        """Delete a subscription."""
        ...

    async def get_subscription_secret(
        self,
        org_id: UUID,
        subscription_id: str,
    ) -> str:
        """Get the signing secret for a subscription."""
        ...

    async def recover_messages(
        self,
        org_id: UUID,
        subscription_id: str,
        since: datetime,
        until: Optional[datetime] = None,
    ) -> RecoveryTask:
        """Recover failed messages for a subscription."""
        ...

    # -------------------------------------------------------------------------
    # Message history
    # -------------------------------------------------------------------------

    async def get_messages(
        self,
        org_id: UUID,
        event_types: Optional[list[str]] = None,
    ) -> list[EventMessage]:
        """Get event messages for an organization."""
        ...

    async def get_message(
        self,
        org_id: UUID,
        message_id: str,
    ) -> EventMessage:
        """Get a specific message."""
        ...

    async def get_message_attempts(
        self,
        org_id: UUID,
        message_id: str,
    ) -> list[DeliveryAttempt]:
        """Get delivery attempts for a message."""
        ...

    async def get_subscription_attempts(
        self,
        org_id: UUID,
        subscription_id: str,
        limit: int = 100,
    ) -> list[DeliveryAttempt]:
        """Get delivery attempts for a subscription."""
        ...
