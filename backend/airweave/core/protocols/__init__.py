"""Core protocols for dependency injection."""

from airweave.core.protocols.event_bus import DomainEvent, EventBus, EventHandler
from airweave.core.protocols.webhooks import WebhookAdmin, WebhookPublisher

__all__ = [
    "DomainEvent",
    "EventBus",
    "EventHandler",
    "WebhookAdmin",
    "WebhookPublisher",
]
