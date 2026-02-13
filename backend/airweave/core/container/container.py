"""Dependency Injection Container.

The container is a simple immutable dataclass that holds protocol implementations.
It has no construction logic — that belongs in the factory.

Design principles:
- Container serves, factory builds
- Fail fast: all construction at startup
- Type safety: fields are protocol types
- Testing: construct directly with fakes
"""

from dataclasses import dataclass, replace
from typing import Any

from airweave.core.protocols import (
    CircuitBreaker,
    EventBus,
    OcrProvider,
    WebhookAdmin,
    WebhookPublisher,
)


@dataclass(frozen=True)
class Container:
    """Immutable container holding all protocol implementations.

    Usage:
        # Production: use the global container built by factory
        from airweave.core.container import container
        await container.event_bus.publish(SyncLifecycleEvent(...))

        # Testing: construct directly with fakes
        from airweave.adapters.event_bus import FakeEventBus
        from airweave.adapters.circuit_breaker import FakeCircuitBreaker
        from airweave.adapters.ocr import FakeOcrProvider
        test_container = Container(
            event_bus=FakeEventBus(),
            webhook_publisher=FakeWebhookPublisher(),
            webhook_admin=FakeWebhookAdmin(),
            circuit_breaker=FakeCircuitBreaker(),
            ocr_provider=FakeOcrProvider(),
        )

        # FastAPI endpoints: use Inject() to pull individual protocols
        from airweave.api.deps import Inject
        async def my_endpoint(event_bus: EventBus = Inject(EventBus)):
            await event_bus.publish(...)
    """

    # Event bus for domain event fan-out
    event_bus: EventBus

    # Webhook protocols (Svix-backed)
    webhook_publisher: WebhookPublisher  # Internal: publish sync events
    webhook_admin: WebhookAdmin  # External API: subscriptions + history

    # Circuit breaker for provider failover
    circuit_breaker: CircuitBreaker

    # OCR provider (with fallback chain + circuit breaking)
    ocr_provider: OcrProvider

    # -----------------------------------------------------------------
    # Convenience methods
    # -----------------------------------------------------------------

    def replace(self, **changes: Any) -> "Container":
        """Create a new container with some dependencies replaced.

        Useful for partial overrides in tests:

            modified = container.replace(webhook_publisher=FakeWebhookPublisher())

        Args:
            **changes: Dependency name -> new implementation

        Returns:
            New Container with specified dependencies replaced
        """
        return replace(self, **changes)
