"""Fake WebhookPublisher for testing.

Records published events for assertions without touching Svix.
"""

from typing import TYPE_CHECKING

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
