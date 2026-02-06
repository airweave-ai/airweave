"""Dependency Injection Container.

The container is a simple immutable dataclass that holds protocol implementations.
It has no construction logic — that belongs in the factory.

Design principles:
- Container serves, factory builds
- Fail fast: all construction at startup
- Type safety: fields are protocol types
- Testing: construct directly with fakes
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from airweave.core.protocols import (
        EventBus,
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
        test_container = Container(
            event_bus=FakeEventBus(),
            webhook_publisher=FakeWebhookPublisher(),
            webhook_admin=FakeWebhookAdmin(),
        )
    """

    # Event bus for domain event fan-out
    event_bus: "EventBus"

    # Webhook protocols (Svix-backed)
    webhook_publisher: "WebhookPublisher"  # Internal: publish sync events
    webhook_admin: "WebhookAdmin"  # External API: subscriptions + history

    # -----------------------------------------------------------------
    # Convenience methods
    # -----------------------------------------------------------------

    def replace(self, **changes: Any) -> Container:
        """Create a new container with some dependencies replaced.

        Useful for partial overrides in tests:

            modified = container.replace(webhook_publisher=FakeWebhookPublisher())

        Args:
            **changes: Dependency name -> new implementation

        Returns:
            New Container with specified dependencies replaced
        """
        return replace(self, **changes)
