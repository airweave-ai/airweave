"""Core protocols for dependency injection.

Domain-specific protocols (repositories, OAuth2, source lifecycle) have moved
to their respective domains/ directories. This module keeps cross-cutting
infrastructure protocols only.
"""

from airweave.core.health.protocols import HealthProbe, HealthServiceProtocol
from airweave.core.protocols.circuit_breaker import CircuitBreaker
from airweave.core.protocols.encryption import CredentialEncryptor
from airweave.core.protocols.event_bus import DomainEvent, EventBus, EventHandler, EventSubscriber
from airweave.core.protocols.metrics import (
    AgenticSearchMetrics,
    DbPool,
    DbPoolMetrics,
    HttpMetrics,
    MetricsRenderer,
    MetricsService,
    WorkerMetrics,
)
from airweave.core.protocols.ocr import OcrProvider
from airweave.core.protocols.pubsub import PubSub
from airweave.core.protocols.payment import PaymentGatewayProtocol
from airweave.core.protocols.webhooks import (
    EndpointVerifier,
    WebhookAdmin,
    WebhookPublisher,
    WebhookServiceProtocol,
)
from airweave.core.protocols.worker_metrics_registry import WorkerMetricsRegistryProtocol

__all__ = [
    "AgenticSearchMetrics",
    "CircuitBreaker",
    "CredentialEncryptor",
    "DbPool",
    "DbPoolMetrics",
    "DomainEvent",
    "EndpointVerifier",
    "EventBus",
    "EventHandler",
    "HealthProbe",
    "HealthServiceProtocol",
    "HttpMetrics",
    "MetricsRenderer",
    "MetricsService",
    "OcrProvider",
    "PaymentGatewayProtocol",
    "PubSub",
    "WebhookAdmin",
    "WebhookPublisher",
    "WebhookServiceProtocol",
    "WorkerMetrics",
    "WorkerMetricsRegistryProtocol",
]
