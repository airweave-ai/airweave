"""Fake webhook adapters for testing.

Records operations for assertions without touching Svix.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import UUID, uuid4

from airweave.domains.webhooks.types import (
    DeliveryAttempt,
    EventMessage,
    HealthStatus,
    RecoveryTask,
    Subscription,
)

if TYPE_CHECKING:
    from airweave.core.protocols.event_bus import DomainEvent


class FakeWebhookPublisher:
    """Test implementation of WebhookPublisher.

    Records all published events for assertions.

    Usage:
        fake = FakeWebhookPublisher()
        subscriber = WebhookEventSubscriber(publisher=fake)
        await subscriber.handle(some_event)

        assert fake.has_event("sync.completed")
        event = fake.get_events("sync.completed")[0]
        assert event.sync_id == expected_sync_id
    """

    def __init__(self) -> None:
        """Initialize with empty event list."""
        self.events: list["DomainEvent"] = []

    async def publish_event(self, event: "DomainEvent") -> None:
        """Record a published event."""
        self.events.append(event)

    # Test helpers

    def has_event(self, event_type: str) -> bool:
        """Check if any event of the given type was published."""
        return any(e.event_type == event_type for e in self.events)

    def get_events(self, event_type: str) -> list["DomainEvent"]:
        """Get all events of the given type."""
        return [e for e in self.events if e.event_type == event_type]

    def clear(self) -> None:
        """Clear all recorded events."""
        self.events.clear()


class FakeWebhookAdmin:
    """Test implementation of WebhookAdmin.

    Records all operations for assertions without touching Svix.

    Usage:
        fake = FakeWebhookAdmin()
        container = Container(..., webhook_admin=fake)

        # After calling code that creates a subscription:
        fake.assert_subscription_created("https://example.com/hook")
    """

    def __init__(self) -> None:
        """Initialize with empty state."""
        self.subscriptions: dict[str, Subscription] = {}
        self.messages: list[EventMessage] = []
        self.deleted_orgs: list[UUID] = []
        self.recovered: list[tuple[UUID, str, datetime]] = []

    # -------------------------------------------------------------------------
    # Organization lifecycle
    # -------------------------------------------------------------------------

    async def delete_organization(self, org_id: UUID) -> None:
        """Record organization deletion."""
        self.deleted_orgs.append(org_id)

    # -------------------------------------------------------------------------
    # Subscriptions
    # -------------------------------------------------------------------------

    async def list_subscriptions(self, org_id: UUID) -> list[Subscription]:
        """Return all recorded subscriptions."""
        return list(self.subscriptions.values())

    async def get_subscription(self, org_id: UUID, subscription_id: str) -> Subscription:
        """Return a specific subscription by ID."""
        sub = self.subscriptions.get(subscription_id)
        if sub is None:
            raise KeyError(f"Subscription {subscription_id} not found")
        return sub

    async def create_subscription(
        self,
        org_id: UUID,
        url: str,
        event_types: list[str],
        secret: Optional[str] = None,
    ) -> Subscription:
        """Record a subscription creation."""
        sub_id = str(uuid4())
        now = datetime.now(timezone.utc)
        sub = Subscription(
            id=sub_id,
            url=url,
            event_types=event_types,
            disabled=False,
            created_at=now,
            updated_at=now,
            secret=secret,
        )
        self.subscriptions[sub_id] = sub
        return sub

    async def update_subscription(
        self,
        org_id: UUID,
        subscription_id: str,
        url: Optional[str] = None,
        event_types: Optional[list[str]] = None,
        disabled: Optional[bool] = None,
    ) -> Subscription:
        """Record a subscription update."""
        sub = await self.get_subscription(org_id, subscription_id)
        # Build updated subscription (dataclass is not frozen)
        if url is not None:
            sub.url = url
        if event_types is not None:
            sub.event_types = event_types
        if disabled is not None:
            sub.disabled = disabled
        sub.updated_at = datetime.now(timezone.utc)
        return sub

    async def delete_subscription(self, org_id: UUID, subscription_id: str) -> None:
        """Record a subscription deletion."""
        self.subscriptions.pop(subscription_id, None)

    async def get_subscription_secret(self, org_id: UUID, subscription_id: str) -> str:
        """Return the secret for a subscription."""
        sub = await self.get_subscription(org_id, subscription_id)
        return sub.secret or "whsec_fake_secret"

    async def recover_messages(
        self,
        org_id: UUID,
        subscription_id: str,
        since: datetime,
        until: Optional[datetime] = None,
    ) -> RecoveryTask:
        """Record a recovery request."""
        self.recovered.append((org_id, subscription_id, since))
        return RecoveryTask(id=str(uuid4()), status="completed")

    # -------------------------------------------------------------------------
    # Message history
    # -------------------------------------------------------------------------

    async def get_messages(
        self,
        org_id: UUID,
        event_types: Optional[list[str]] = None,
    ) -> list[EventMessage]:
        """Return recorded messages, optionally filtered by event type."""
        if event_types is None:
            return list(self.messages)
        return [m for m in self.messages if m.event_type in event_types]

    async def get_message(self, org_id: UUID, message_id: str) -> EventMessage:
        """Return a specific message by ID."""
        for msg in self.messages:
            if msg.id == message_id:
                return msg
        raise KeyError(f"Message {message_id} not found")

    async def get_message_attempts(
        self,
        org_id: UUID,
        message_id: str,
    ) -> list[DeliveryAttempt]:
        """Return delivery attempts for a message (always empty in fake)."""
        return []

    async def get_subscription_attempts(
        self,
        org_id: UUID,
        subscription_id: str,
        limit: int = 100,
    ) -> list[DeliveryAttempt]:
        """Return delivery attempts for a subscription (always empty in fake)."""
        return []

    # -------------------------------------------------------------------------
    # Test helpers
    # -------------------------------------------------------------------------

    def assert_subscription_created(self, url: str) -> Subscription:
        """Assert that a subscription was created for the given URL."""
        for sub in self.subscriptions.values():
            if sub.url == url:
                return sub
        raise AssertionError(
            f"No subscription created for URL '{url}'. "
            f"Created URLs: {[s.url for s in self.subscriptions.values()]}"
        )

    def assert_org_deleted(self, org_id: UUID) -> None:
        """Assert that an organization was deleted."""
        if org_id not in self.deleted_orgs:
            raise AssertionError(f"Organization {org_id} was not deleted")

    def clear(self) -> None:
        """Clear all recorded state."""
        self.subscriptions.clear()
        self.messages.clear()
        self.deleted_orgs.clear()
        self.recovered.clear()


class FakeEndpointVerifier:
    """Test implementation of EndpointVerifier.

    Records verification calls for assertions.
    Can be configured to simulate failures.

    Usage:
        fake = FakeEndpointVerifier()
        container = Container(..., endpoint_verifier=fake)

        # After calling code that verifies an endpoint:
        assert fake.verified_urls == ["https://example.com/hook"]

        # Simulate unreachable endpoint:
        fake.should_fail = True
    """

    def __init__(self) -> None:
        """Initialize with empty state."""
        self.verified_urls: list[str] = []
        self.should_fail: bool = False
        self.fail_message: str = "Simulated endpoint verification failure"

    async def verify(self, url: str, timeout: float = 5.0) -> None:
        """Record the verification call. Optionally fail."""
        if self.should_fail:
            from airweave.domains.webhooks.types import WebhooksError

            raise WebhooksError(self.fail_message, 400)
        self.verified_urls.append(url)

    def clear(self) -> None:
        """Clear all recorded state."""
        self.verified_urls.clear()
        self.should_fail = False


class FakeWebhookService:
    """Test implementation of WebhookService.

    Standalone fake with in-memory state for test assertions.
    Composes FakeWebhookAdmin + FakeEndpointVerifier internally.

    Usage:
        fake = FakeWebhookService()
        container = Container(..., webhook_service=fake)

        # After calling code that creates a subscription:
        fake.assert_subscription_created("https://example.com/hook")
    """

    def __init__(self) -> None:
        """Initialize with in-memory state."""
        self._admin = FakeWebhookAdmin()
        self._verifier = FakeEndpointVerifier()

    # -------------------------------------------------------------------------
    # Subscriptions (orchestrated)
    # -------------------------------------------------------------------------

    async def list_subscriptions_with_health(
        self,
        org_id: UUID,
    ) -> list[tuple[Subscription, HealthStatus, list[DeliveryAttempt]]]:
        """Return subscriptions with unknown health (no delivery data in fake)."""
        subs = await self._admin.list_subscriptions(org_id)
        return [(sub, HealthStatus.unknown, []) for sub in subs]

    async def get_subscription_detail(
        self,
        org_id: UUID,
        subscription_id: str,
        include_secret: bool = False,
    ) -> tuple[Subscription, list[DeliveryAttempt], Optional[str]]:
        """Return subscription with empty attempts."""
        sub = await self._admin.get_subscription(org_id, subscription_id)
        secret = None
        if include_secret:
            secret = await self._admin.get_subscription_secret(org_id, subscription_id)
        return sub, [], secret

    async def create_subscription(
        self,
        org_id: UUID,
        url: str,
        event_types: list[str],
        secret: Optional[str] = None,
    ) -> Subscription:
        """Record a subscription creation."""
        return await self._admin.create_subscription(org_id, url, event_types, secret)

    async def update_subscription(
        self,
        org_id: UUID,
        subscription_id: str,
        url: Optional[str] = None,
        event_types: Optional[list[str]] = None,
        disabled: Optional[bool] = None,
        recover_since: Optional[datetime] = None,
    ) -> Subscription:
        """Record a subscription update."""
        return await self._admin.update_subscription(
            org_id, subscription_id, url, event_types, disabled
        )

    async def delete_subscription(
        self,
        org_id: UUID,
        subscription_id: str,
    ) -> Subscription:
        """Record a subscription deletion, return the deleted subscription."""
        sub = await self._admin.get_subscription(org_id, subscription_id)
        await self._admin.delete_subscription(org_id, subscription_id)
        return sub

    # -------------------------------------------------------------------------
    # Messages (pass-through)
    # -------------------------------------------------------------------------

    async def get_messages(
        self,
        org_id: UUID,
        event_types: Optional[list[str]] = None,
    ) -> list[EventMessage]:
        """Return recorded messages."""
        return await self._admin.get_messages(org_id, event_types)

    async def get_message(
        self,
        org_id: UUID,
        message_id: str,
    ) -> EventMessage:
        """Return a specific message."""
        return await self._admin.get_message(org_id, message_id)

    async def get_message_attempts(
        self,
        org_id: UUID,
        message_id: str,
    ) -> list[DeliveryAttempt]:
        """Return delivery attempts for a message."""
        return await self._admin.get_message_attempts(org_id, message_id)

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
        """Record a recovery request."""
        return await self._admin.recover_messages(org_id, subscription_id, since, until)

    # -------------------------------------------------------------------------
    # Test helpers
    # -------------------------------------------------------------------------

    def assert_subscription_created(self, url: str) -> Subscription:
        """Assert that a subscription was created for the given URL."""
        return self._admin.assert_subscription_created(url)

    def clear(self) -> None:
        """Clear all recorded state."""
        self._admin.clear()
        self._verifier.clear()
