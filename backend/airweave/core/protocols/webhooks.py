"""Webhook protocols.

Four protocols based on consumer needs:
- WebhookPublisher: Internal use (event bus subscriber publishes events)
- WebhookAdmin: Infrastructure adapter (Svix CRUD for subscriptions + messages)
- EndpointVerifier: Verify webhook endpoint reachability before subscription
- WebhookService: High-level service the API layer injects (composes the above)

All WebhookAdmin methods raise WebhooksError on failure.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

if TYPE_CHECKING:
    from airweave.core.protocols.event_bus import DomainEvent

from uuid import UUID

from airweave.domains.webhooks.types import (
    DeliveryAttempt,
    EventMessage,
    HealthStatus,
    RecoveryTask,
    Subscription,
)


@runtime_checkable
class WebhookPublisher(Protocol):
    """Publish domain events to external webhook subscribers.

    Accepts domain events directly. The adapter is responsible for
    serializing the event into the format its backend requires.
    """

    async def publish_event(self, event: "DomainEvent") -> None:
        """Publish a domain event to all subscribed webhook endpoints."""
        ...


@runtime_checkable
class WebhookAdmin(Protocol):
    """Manage webhook subscriptions and view message history.

    Used by API endpoints. External user-facing.
    All methods raise WebhooksError on failure.
    """

    # -------------------------------------------------------------------------
    # Organization lifecycle
    # -------------------------------------------------------------------------

    # TODO: Implement create organization -> now implemented implicitly by SvixAdapter (decorator)

    async def delete_organization(self, org_id: UUID) -> None:
        """Delete an organization and all its webhook data.

        Best-effort: implementations should log errors rather than raise.
        """
        ...

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


@runtime_checkable
class EndpointVerifier(Protocol):
    """Verify that a webhook endpoint URL is reachable.

    Sends a lightweight HEAD request and accepts any HTTP response.
    The check only confirms the URL resolves and a server is listening.
    Used by domain operations before creating a subscription.

    Raises WebhooksError if the endpoint is unreachable or times out.
    """

    async def verify(self, url: str, timeout: float = 5.0) -> None:
        """Check that the given URL is reachable.

        Args:
            url: The webhook endpoint URL to verify.
            timeout: Seconds to wait for a response.

        Raises:
            WebhooksError: If the endpoint is not reachable.
        """
        ...


@runtime_checkable
class WebhookServiceProtocol(Protocol):
    """High-level webhook service for the API layer.

    Composes ``WebhookAdmin`` and ``EndpointVerifier`` behind a single
    interface so API endpoints inject exactly one dependency.  Business
    orchestration (health computation, verify-then-create, update-with-
    recovery) lives in the implementation; the protocol defines only what
    the API layer is allowed to call.
    """

    # -------------------------------------------------------------------------
    # Subscriptions (orchestrated)
    # -------------------------------------------------------------------------

    async def list_subscriptions_with_health(
        self,
        org_id: UUID,
    ) -> list[tuple[Subscription, HealthStatus, list[DeliveryAttempt]]]:
        """List subscriptions with computed health status."""
        ...

    async def get_subscription_detail(
        self,
        org_id: UUID,
        subscription_id: str,
        include_secret: bool = False,
    ) -> tuple[Subscription, list[DeliveryAttempt], Optional[str]]:
        """Get subscription with delivery attempts and optional secret."""
        ...

    async def create_subscription(
        self,
        org_id: UUID,
        url: str,
        event_types: list[str],
        secret: Optional[str] = None,
    ) -> Subscription:
        """Create a subscription, verifying the endpoint if configured."""
        ...

    async def update_subscription(
        self,
        org_id: UUID,
        subscription_id: str,
        url: Optional[str] = None,
        event_types: Optional[list[str]] = None,
        disabled: Optional[bool] = None,
        recover_since: Optional[datetime] = None,
    ) -> Subscription:
        """Update a subscription with optional recovery on re-enable."""
        ...

    async def delete_subscription(
        self,
        org_id: UUID,
        subscription_id: str,
    ) -> Subscription:
        """Delete a subscription. Returns the subscription before deletion."""
        ...

    # -------------------------------------------------------------------------
    # Messages
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

    # -------------------------------------------------------------------------
    # Recovery
    # -------------------------------------------------------------------------

    async def recover_messages(
        self,
        org_id: UUID,
        subscription_id: str,
        since: datetime,
        until: Optional[datetime] = None,
    ) -> RecoveryTask:
        """Recover failed messages for a subscription."""
        ...
