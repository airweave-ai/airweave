"""Core protocols for dependency injection.

Domain-specific protocols (repositories, OAuth2, source lifecycle) have moved
to their respective domains/ directories. This module keeps cross-cutting
infrastructure protocols only.
"""

from airweave.core.health.protocols import HealthProbe, HealthServiceProtocol
from airweave.core.protocols.circuit_breaker import CircuitBreaker
from airweave.core.protocols.encryption import CredentialEncryptor
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
    "CredentialEncryptor",
    "DomainEvent",
    "EndpointVerifier",
    "EventBus",
    "EventHandler",
    "HealthProbe",
    "HealthServiceProtocol",
    "OcrProvider",
    "WebhookAdmin",
    "WebhookPublisher",
    "WebhookServiceProtocol",
]
