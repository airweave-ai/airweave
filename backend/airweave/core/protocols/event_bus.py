"""EventBus protocol for domain event fan-out.

The event bus decouples domain code from event consumers. Instead of
calling each consumer explicitly (webhooks, analytics, realtime),
domain code publishes events to the bus and subscribers handle them.

Usage:
    # Domain code publishes
    await event_bus.publish(SyncCompletedEvent(...))

    # Subscribers react (registered at startup)
    event_bus.subscribe("sync.*", webhook_handler)
    event_bus.subscribe("sync.*", analytics_handler)
"""

from datetime import datetime
from typing import Awaitable, Callable, Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class DomainEvent(Protocol):
    """Base protocol for all domain events.

    Concrete events are frozen dataclasses that carry domain-specific data.
    The bus only cares about these three fields for routing and metadata.
    Subscribers type-narrow to the concrete event class they expect.
    """

    @property
    def event_type(self) -> str:
        """Dot-separated event identifier (e.g., 'sync.completed').

        Convention: {domain}.{action} — used for pattern matching.
        """
        ...

    @property
    def timestamp(self) -> datetime:
        """When the event occurred (UTC)."""
        ...

    @property
    def organization_id(self) -> UUID:
        """Organization this event belongs to."""
        ...


# Type alias for event handlers (async callables that receive a DomainEvent)
EventHandler = Callable[[DomainEvent], Awaitable[None]]


@runtime_checkable
class EventBus(Protocol):
    """Protocol for publishing domain events to multiple subscribers.

    The bus matches events to subscribers by glob pattern on event_type.
    Failures in one subscriber don't affect others.
    """

    async def publish(self, event: DomainEvent) -> None:
        """Publish an event to all matching subscribers.

        Args:
            event: The domain event to publish.
        """
        ...

    def subscribe(self, event_pattern: str, handler: EventHandler) -> None:
        """Register a handler for events matching the pattern.

        Args:
            event_pattern: Glob pattern to match (e.g., 'sync.*', 'sync.completed').
            handler: Async callable invoked when a matching event is published.
        """
        ...
