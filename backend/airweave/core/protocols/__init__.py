"""Core protocols for dependency injection.

Domain-specific protocols (repositories, OAuth2, source lifecycle) have moved
to their respective domains/ directories. This module keeps cross-cutting
infrastructure protocols only.
"""

from airweave.core.health.protocols import HealthProbe, HealthServiceProtocol
from airweave.core.protocols.cache import ContextCache
from airweave.core.protocols.circuit_breaker import CircuitBreaker
from airweave.core.protocols.email import EmailService
from airweave.core.protocols.encryption import CredentialEncryptor
from airweave.core.protocols.event_bus import DomainEvent, EventBus, EventHandler, EventSubscriber
from airweave.core.protocols.identity import IdentityProvider
from airweave.core.protocols.llm import LLMProtocol
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
from airweave.core.protocols.payment import PaymentGatewayProtocol
from airweave.core.protocols.pubsub import PubSub, PubSubSubscription
from airweave.core.protocols.rate_limiter import RateLimiter
from airweave.core.protocols.reranker import RerankerProtocol
from airweave.core.protocols.tokenizer import TokenizerProtocol
from airweave.core.protocols.webhooks import (
    EndpointVerifier,
    WebhookAdmin,
    WebhookPublisher,
    WebhookServiceProtocol,
)
from airweave.core.protocols.worker_metrics_registry import WorkerMetricsRegistryProtocol

__all__ = [
    "AgenticSearchMetrics",
    "ContextCache",
    "CircuitBreaker",
    "CredentialEncryptor",
    "DbPool",
    "DbPoolMetrics",
    "DomainEvent",
    "EmailService",
    "EndpointVerifier",
    "EventBus",
    "EventHandler",
    "EventSubscriber",
    "HealthProbe",
    "HealthServiceProtocol",
    "HttpMetrics",
    "LLMProtocol",
    "IdentityProvider",
    "MetricsRenderer",
    "MetricsService",
    "OcrProvider",
    "PaymentGatewayProtocol",
    "PubSub",
    "PubSubSubscription",
    "RateLimiter",
    "RerankerProtocol",
    "WebhookAdmin",
    "WebhookPublisher",
    "TokenizerProtocol",
    "WebhookServiceProtocol",
    "WorkerMetrics",
    "WorkerMetricsRegistryProtocol",
]
