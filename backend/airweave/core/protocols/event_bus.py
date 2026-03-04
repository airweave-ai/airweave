"""EventBus protocol for domain event fan-out.

The event bus decouples domain code from event consumers. Instead of
calling each consumer explicitly (webhooks, analytics, realtime),
domain code publishes events to the bus and subscribers handle them.

Usage:
    # Domain code publishes
    await event_bus.publish(SyncCompletedEvent(...))

    # Subscribers react (registered at startup)
    event_bus.subscribe("sync.*", webhook_subscriber.handle)
    event_bus.subscribe("sync.*", analytics_subscriber.handle)
"""

from typing import Awaitable, Callable, List, Protocol, runtime_checkable

from airweave.core.events.base import DomainEvent

# Type alias for the bare callable signature accepted by EventBus.subscribe().
EventHandler = Callable[[DomainEvent], Awaitable[None]]


@runtime_checkable
class EventSubscriber(Protocol):
    """Protocol for classes that subscribe to domain events.

    Subscriber classes implement this protocol and are wired to the
    EventBus at startup. The bus calls ``handle()`` for matching events.

    Usage:
        class MySubscriber(EventSubscriber):
            EVENT_PATTERNS = ["sync.*"]

            async def handle(self, event: DomainEvent) -> None:
                ...
    """

    EVENT_PATTERNS: List[str]

    async def handle(self, event: DomainEvent) -> None:
        """Process a domain event.

        Args:
            event: The domain event to handle.
        """
        ...


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
