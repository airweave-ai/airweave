"""Webhook protocols.

Two protocols based on consumer needs:
- WebhookPublisher: Internal use (sync domain publishes events)
- WebhookAdmin: External API (users manage subscriptions, view history)

All WebhookAdmin methods raise WebhooksError on failure.
"""

from datetime import datetime
from typing import Optional, Protocol
from uuid import UUID

from airweave.domains.webhooks.types import (
    DeliveryAttempt,
    EventMessage,
    RecoveryTask,
    Subscription,
)


class WebhookPublisher(Protocol):
    """Publish sync events to webhook subscribers.

    Used by sync domain / event bus subscriber. Internal only.
    """

    async def publish_sync_event(
        self,
        org_id: UUID,
        source_connection_id: UUID,
        sync_job_id: UUID,
        sync_id: UUID,
        collection_id: UUID,
        collection_name: str,
        collection_readable_id: str,
        source_type: str,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """Publish a sync lifecycle event to all subscribed webhooks."""
        ...


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
