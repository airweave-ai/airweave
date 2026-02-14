"""Core protocols for dependency injection."""

from airweave.core.protocols.circuit_breaker import CircuitBreaker
from airweave.core.protocols.credential import CredentialServiceProtocol
from airweave.core.protocols.event_bus import DomainEvent, EventBus, EventHandler
from airweave.core.protocols.integration_credential_repository import (
    IntegrationCredentialRepositoryProtocol,
)
from airweave.core.protocols.ocr import OcrProvider
from airweave.core.protocols.webhooks import WebhookAdmin, WebhookPublisher

__all__ = [
    "CircuitBreaker",
    "CredentialServiceProtocol",
    "DomainEvent",
    "EventBus",
    "EventHandler",
    "IntegrationCredentialRepositoryProtocol",
    "OcrProvider",
    "WebhookAdmin",
    "WebhookPublisher",
]
