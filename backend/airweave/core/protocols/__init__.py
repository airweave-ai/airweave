"""Core protocols for dependency injection."""

from airweave.core.protocols.circuit_breaker import CircuitBreaker
from airweave.core.protocols.event_bus import DomainEvent, EventBus, EventHandler
from airweave.core.protocols.ocr import OcrProvider
from airweave.core.protocols.webhooks import (
    EndpointVerifier,
    WebhookAdmin,
    WebhookPublisher,
    WebhookServiceProtocol,
)

__all__ = [
    "CircuitBreaker",
    "DomainEvent",
    "EndpointVerifier",
    "EventBus",
    "EventHandler",
    "OcrProvider",
    "WebhookAdmin",
    "WebhookPublisher",
    "WebhookServiceProtocol",
]
