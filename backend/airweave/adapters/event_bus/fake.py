"""Fake event bus for testing.

Records published events for assertions without calling real subscribers.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airweave.core.protocols.event_bus import DomainEvent, EventHandler


class FakeEventBus:
    """Test implementation of EventBus.

    Records all published events for assertions. Optionally calls
    subscribers if registered (useful for integration tests).

    Usage:
        fake = FakeEventBus()
        await some_operation(event_bus=fake)

        # Assert events were published
        assert fake.has_event("sync.completed")
        event = fake.get_event("sync.completed")
        assert event.sync_id == expected_sync_id
    """

    def __init__(self, call_subscribers: bool = False) -> None:
        """Initialize the fake event bus.

        Args:
            call_subscribers: If True, actually call registered subscribers.
                             Defaults to False (just record events).
        """
        self.events: list["DomainEvent"] = []
        self._subscribers: list[tuple[str, "EventHandler"]] = []
        self._call_subscribers = call_subscribers

    def subscribe(self, event_pattern: str, handler: "EventHandler") -> None:
        """Register a handler (only called if call_subscribers=True)."""
        self._subscribers.append((event_pattern, handler))

    async def publish(self, event: "DomainEvent") -> None:
        """Record the event (and optionally call subscribers)."""
        self.events.append(event)

        if self._call_subscribers:
            import fnmatch

            for pattern, handler in self._subscribers:
                if fnmatch.fnmatch(event.event_type, pattern):
                    await handler(event)

    # Test helpers

    def has_event(self, event_type: str) -> bool:
        """Check if an event of the given type was published."""
        return any(e.event_type == event_type for e in self.events)

    def get_event(self, event_type: str) -> "DomainEvent":
        """Get the first event of the given type.

        Raises:
            AssertionError: If no event of that type was published.
        """
        for event in self.events:
            if event.event_type == event_type:
                return event
        raise AssertionError(f"No event of type '{event_type}' was published")

    def get_events(self, event_type: str) -> list["DomainEvent"]:
        """Get all events of the given type."""
        return [e for e in self.events if e.event_type == event_type]

    def clear(self) -> None:
        """Clear all recorded events."""
        self.events.clear()

    def assert_published(self, event_type: str) -> "DomainEvent":
        """Assert that an event was published and return it."""
        if not self.has_event(event_type):
            published = [e.event_type for e in self.events]
            raise AssertionError(
                f"Expected event '{event_type}' was not published. Published events: {published}"
            )
        return self.get_event(event_type)

    def assert_not_published(self, event_type: str) -> None:
        """Assert that an event was NOT published."""
        if self.has_event(event_type):
            raise AssertionError(f"Event '{event_type}' was published but should not have been")
