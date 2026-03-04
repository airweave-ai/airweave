"""Fake analytics tracker for testing."""

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class TrackedEvent:
    """Single recorded analytics call."""

    event_name: str
    distinct_id: str
    properties: Dict[str, Any]
    groups: Optional[Dict[str, str]]


class FakeAnalyticsTracker:
    """In-memory test double for AnalyticsTrackerProtocol.

    Records all tracked events for assertions.

    Usage:
        tracker = FakeAnalyticsTracker()
        subscriber = AnalyticsEventSubscriber(tracker)
        await subscriber.handle(some_event)
        assert tracker.has("source_connection_created")
    """

    def __init__(self) -> None:
        """Initialize with empty event list."""
        self.events: list[TrackedEvent] = []

    def track(
        self,
        event_name: str,
        distinct_id: str,
        properties: Optional[Dict[str, Any]] = None,
        groups: Optional[Dict[str, str]] = None,
    ) -> None:
        """Record the event for later assertions."""
        self.events.append(
            TrackedEvent(
                event_name=event_name,
                distinct_id=distinct_id,
                properties=properties or {},
                groups=groups,
            )
        )

    def has(self, event_name: str) -> bool:
        """Return True if an event with the given name was tracked."""
        return any(e.event_name == event_name for e in self.events)

    def get(self, event_name: str) -> TrackedEvent:
        """Return the first tracked event matching name, or raise AssertionError."""
        for e in self.events:
            if e.event_name == event_name:
                return e
        raise AssertionError(
            f"No analytics event '{event_name}' tracked. "
            f"Tracked: {[e.event_name for e in self.events]}"
        )

    def get_all(self, event_name: str) -> list[TrackedEvent]:
        """Return all tracked events matching name."""
        return [e for e in self.events if e.event_name == event_name]

    def clear(self) -> None:
        """Reset tracked events."""
        self.events.clear()
