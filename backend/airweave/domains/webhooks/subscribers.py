"""Event subscribers for the webhooks domain."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from airweave.core.protocols import WebhookPublisher
    from airweave.core.protocols.event_bus import DomainEvent

logger = logging.getLogger(__name__)


class WebhookEventSubscriber:
    """Forwards domain events to external webhook endpoints.

    Subscribes to all events (``*``) and delegates payload construction
    to each event's ``to_webhook_payload()`` method.  The ``event_type``
    string (e.g. ``sync.completed``, ``source_connection.created``)
    determines the Svix channel, so endpoint-level filtering is handled
    by the infrastructure, not by this subscriber.
    """

    EVENT_PATTERNS = ["*"]

    def __init__(self, publisher: "WebhookPublisher") -> None:
        """Initialize with a webhook publisher.

        Args:
            publisher: Protocol for publishing events to external endpoints.
        """
        self._publisher = publisher

    async def handle(self, event: "DomainEvent") -> None:
        """Handle any domain event by forwarding to webhooks.

        Args:
            event: Any domain event that satisfies the DomainEvent protocol.
        """
        event_type = str(event.event_type)

        # All domain events must implement to_webhook_payload()
        if not hasattr(event, "to_webhook_payload"):
            logger.warning(
                f"WebhookEventSubscriber: event '{event_type}' has no "
                f"to_webhook_payload() method, skipping"
            )
            return

        payload = event.to_webhook_payload()

        logger.debug(f"WebhookEventSubscriber: forwarding '{event_type}' to webhook publisher")

        await self._publisher.publish_event(
            org_id=event.organization_id,
            event_type=event_type,
            payload=payload,
        )
