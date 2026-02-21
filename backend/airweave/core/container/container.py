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
from typing import Any, Optional

from airweave.core.protocols import (
    CircuitBreaker,
    EndpointVerifier,
    EventBus,
    HealthServiceProtocol,
    MetricsService,
    OcrProvider,
    WebhookAdmin,
    WebhookPublisher,
    WebhookServiceProtocol,
)
from airweave.core.protocols.payment import PaymentGatewayProtocol
from airweave.domains.auth_provider.protocols import AuthProviderRegistryProtocol
from airweave.domains.billing.protocols import BillingServiceProtocol, BillingWebhookProtocol
from airweave.domains.collections.protocols import (
    CollectionRepositoryProtocol,
    CollectionServiceProtocol,
)
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.credentials.protocols import IntegrationCredentialRepositoryProtocol
from airweave.domains.oauth.protocols import OAuth1ServiceProtocol, OAuth2ServiceProtocol
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionRepositoryProtocol,
    SourceConnectionServiceProtocol,
)
from airweave.domains.sources.protocols import (
    SourceLifecycleServiceProtocol,
    SourceRegistryProtocol,
    SourceServiceProtocol,
)
from airweave.domains.syncs.protocols import (
    SyncCursorRepositoryProtocol,
    SyncJobRepositoryProtocol,
    SyncJobServiceProtocol,
    SyncLifecycleServiceProtocol,
    SyncRecordServiceProtocol,
    SyncRepositoryProtocol,
)
from airweave.domains.temporal.protocols import (
    TemporalScheduleServiceProtocol,
    TemporalWorkflowServiceProtocol,
)


@dataclass(frozen=True)
class Container:
    """Immutable container holding all protocol implementations.

    Usage:
        # Production: use the global container built by factory
        from airweave.core.container import container
        await container.event_bus.publish(SyncLifecycleEvent(...))

        # Testing: construct directly with fakes (see backend/conftest.py
        # for the full test_container fixture and Fake* definitions)
        test_container = Container(event_bus=FakeEventBus(), ...)

        # FastAPI endpoints: use Inject() to pull individual protocols
        from airweave.api.deps import Inject
        async def my_endpoint(event_bus: EventBus = Inject(EventBus)):
            await event_bus.publish(...)
    """

    # Health service — readiness check facade
    health: HealthServiceProtocol

    # Event bus for domain event fan-out
    event_bus: EventBus

    # Webhook protocols
    webhook_publisher: WebhookPublisher
    webhook_admin: WebhookAdmin
    endpoint_verifier: EndpointVerifier
    webhook_service: WebhookServiceProtocol

    # Circuit breaker for provider failover
    circuit_breaker: CircuitBreaker

    # Metrics (HTTP, agentic search, DB pool — via MetricsService facade)
    metrics: MetricsService

    # Source service — API-facing source operations
    source_service: SourceServiceProtocol

    # Source registries (shared across services)
    source_registry: SourceRegistryProtocol
    auth_provider_registry: AuthProviderRegistryProtocol

    # Collection service — domain service for collection lifecycle
    collection_service: CollectionServiceProtocol

    # Repository protocols (thin wrappers around crud singletons)
    sc_repo: SourceConnectionRepositoryProtocol
    collection_repo: CollectionRepositoryProtocol
    conn_repo: ConnectionRepositoryProtocol
    cred_repo: IntegrationCredentialRepositoryProtocol

    # OAuth services
    oauth1_service: OAuth1ServiceProtocol
    oauth2_service: OAuth2ServiceProtocol

    # Source connection service — domain service for source connections
    source_connection_service: SourceConnectionServiceProtocol

    # Source lifecycle — creates/validates configured source instances
    source_lifecycle_service: SourceLifecycleServiceProtocol

    # Response builder — constructs API responses for source connections
    response_builder: ResponseBuilderProtocol

    # Sync domain
    sync_repo: SyncRepositoryProtocol
    sync_cursor_repo: SyncCursorRepositoryProtocol
    sync_job_repo: SyncJobRepositoryProtocol
    sync_record_service: SyncRecordServiceProtocol
    sync_job_service: SyncJobServiceProtocol
    sync_lifecycle: SyncLifecycleServiceProtocol

    # Temporal domain
    temporal_workflow_service: TemporalWorkflowServiceProtocol
    temporal_schedule_service: TemporalScheduleServiceProtocol

    # Billing domain
    billing_service: BillingServiceProtocol
    billing_webhook: BillingWebhookProtocol

    payment_gateway: PaymentGatewayProtocol

    # OCR provider (with fallback chain + circuit breaking)
    # Optional: None when no OCR backend (Mistral/Docling) is configured
    ocr_provider: Optional[OcrProvider] = None

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
