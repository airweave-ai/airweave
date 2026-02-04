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
    # Protocol imports will go here once core/protocols/ is created
    # from airweave.core.protocols.messaging import EventMessageStore, WebhookSender
    pass


@dataclass(frozen=True)
class Container:
    """Immutable container holding all protocol implementations.

    This is just a typed bag of dependencies. Construction logic lives
    in the factory module.

    Usage:
    ------
        # Production: use the global container built by factory
        from airweave.core.container import container
        store = container.event_message_store

        # Testing: construct directly with fakes
        test_container = Container(
            event_message_store=FakeEventMessageStore(),
            webhook_sender=FakeWebhookSender(),
        )

    Attributes:
    -----------
        event_message_store: Read event messages and delivery attempts (Svix)
        webhook_sender: Publish sync events to webhook subscribers (Svix)
    """

    # -----------------------------------------------------------------
    # Protocol implementations
    # Type hints will be Protocol types once core/protocols/ exists
    # -----------------------------------------------------------------

    event_message_store: Any  # -> EventMessageStore
    webhook_sender: Any  # -> WebhookSender

    # -----------------------------------------------------------------
    # Convenience methods
    # -----------------------------------------------------------------

    def replace(self, **changes: Any) -> Container:
        """Create a new container with some dependencies replaced.

        Useful for partial overrides in tests:

            modified = container.replace(webhook_sender=FakeWebhookSender())

        Args:
            **changes: Dependency name -> new implementation

        Returns:
            New Container with specified dependencies replaced
        """
        return replace(self, **changes)
