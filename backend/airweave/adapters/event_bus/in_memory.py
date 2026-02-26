"""In-memory event bus implementation.

Simple event bus that fans out events to subscribers in-process.
Can be replaced with a distributed bus (Redis Streams, Kafka, etc.) later.
"""

import asyncio
import fnmatch
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airweave.core.protocols.event_bus import DomainEvent, EventHandler

# Use standard logging to avoid circular import with airweave.core.logging
logger = logging.getLogger(__name__)


class InMemoryEventBus:
    """In-memory event bus with pattern-based subscriptions.

    Implements the EventBus protocol. Events are delivered to all
    matching subscribers asynchronously.

    Usage:
        bus = InMemoryEventBus()
        bus.subscribe("sync.*", webhook_handler)
        bus.subscribe("sync.completed", analytics_handler)
        await bus.publish(SyncLifecycleEvent(...))
    """

    def __init__(self) -> None:
        """Initialize the event bus."""
        self._subscribers: list[tuple[str, "EventHandler"]] = []

    def subscribe(self, event_pattern: str, handler: "EventHandler") -> None:
        """Register a handler for events matching the pattern.

        Args:
            event_pattern: Glob pattern (e.g., 'sync.*', 'sync.completed').
            handler: Async function to call when matching events are published.
        """
        self._subscribers.append((event_pattern, handler))
        logger.debug(f"EventBus: subscribed handler to '{event_pattern}'")

    async def publish(self, event: "DomainEvent") -> None:
        """Publish an event to all matching subscribers.

        Subscribers are called concurrently. Failures in one subscriber
        don't affect others.

        Args:
            event: The domain event to publish.
        """
        event_type = event.event_type
        matching_handlers = [
            handler
            for pattern, handler in self._subscribers
            if fnmatch.fnmatch(event_type, pattern)
        ]

        if not matching_handlers:
            logger.warning(f"EventBus: no subscribers for '{event_type}'")
            return

        logger.debug(f"EventBus: publishing '{event_type}' to {len(matching_handlers)} subscribers")

        # Fan out to all matching handlers concurrently
        results = await asyncio.gather(
            *[handler(event) for handler in matching_handlers],
            return_exceptions=True,
        )

        # Log any failures (but don't raise - other subscribers succeeded)
        for result in results:
            if isinstance(result, Exception):
                logger.error(
                    f"EventBus: subscriber failed for '{event_type}': {result}",
                    exc_info=result,
                )
