"""Container Factory.

All construction logic lives here. The factory reads settings and builds
the container with environment-appropriate implementations.

Design principles:
- Single place for all wiring decisions
- Environment-aware: local vs dev vs prd
- Fail fast: broken wiring crashes at startup, not at 3am
- Testable: can unit test factory logic with mock settings
"""

from typing import Optional

from prometheus_client import CollectorRegistry

from airweave.adapters.analytics.posthog import PostHogTracker
from airweave.adapters.analytics.subscriber import AnalyticsEventSubscriber
from airweave.adapters.circuit_breaker import InMemoryCircuitBreaker
from airweave.adapters.encryption.fernet import FernetCredentialEncryptor
from airweave.adapters.event_bus.in_memory import InMemoryEventBus
from airweave.adapters.health import PostgresHealthProbe, RedisHealthProbe, TemporalHealthProbe
from airweave.adapters.metrics import (
    PrometheusAgenticSearchMetrics,
    PrometheusDbPoolMetrics,
    PrometheusHttpMetrics,
    PrometheusMetricsRenderer,
)
from airweave.adapters.ocr.docling import DoclingOcrAdapter
from airweave.adapters.ocr.fallback import FallbackOcrProvider
from airweave.adapters.ocr.mistral import MistralOcrAdapter
from airweave.adapters.pubsub.redis import RedisPubSub
from airweave.adapters.webhooks.endpoint_verifier import HttpEndpointVerifier
from airweave.adapters.webhooks.svix import SvixAdapter
from airweave.core.config import Settings
from airweave.core.container.container import Container
from airweave.core.health.service import HealthService
from airweave.core.logging import logger
from airweave.core.metrics_service import PrometheusMetricsService
from airweave.core.protocols import CircuitBreaker, OcrProvider, PubSub
from airweave.core.protocols.event_bus import EventBus
from airweave.core.protocols.payment import PaymentGatewayProtocol
from airweave.core.protocols.webhooks import WebhookPublisher
from airweave.core.redis_client import redis_client
from airweave.db.session import health_check_engine
from airweave.domains.auth_provider.registry import AuthProviderRegistry
from airweave.domains.collections.repository import CollectionRepository
from airweave.domains.collections.service import CollectionService
from airweave.domains.collections.vector_db_deployment_metadata_repository import (
    VectorDbDeploymentMetadataRepository,
)
from airweave.domains.connections.repository import ConnectionRepository
from airweave.domains.credentials.repository import IntegrationCredentialRepository
from airweave.domains.embedders.config import (
    DENSE_EMBEDDER,
    EMBEDDING_DIMENSIONS,
    SPARSE_EMBEDDER,
    validate_embedding_config_sync,
)
from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.domains.embedders.registry import DenseEmbedderRegistry, SparseEmbedderRegistry
from airweave.domains.embedders.sparse.fastembed import (
    FastEmbedSparseEmbedder as DomainFastEmbedSparseEmbedder,
)
from airweave.domains.entities.entity_count_repository import EntityCountRepository
from airweave.domains.entities.registry import EntityDefinitionRegistry
from airweave.domains.oauth.callback_service import OAuthCallbackService
from airweave.domains.oauth.flow_service import OAuthFlowService
from airweave.domains.oauth.oauth1_service import OAuth1Service
from airweave.domains.oauth.oauth2_service import OAuth2Service
from airweave.domains.oauth.repository import (
    OAuthConnectionRepository,
    OAuthCredentialRepository,
    OAuthInitSessionRepository,
    OAuthRedirectSessionRepository,
    OAuthSourceRepository,
)
from airweave.domains.organizations.protocols import UserOrganizationRepositoryProtocol
from airweave.domains.organizations.repository import OrganizationRepository as OrgRepo
from airweave.domains.organizations.repository import UserOrganizationRepository
from airweave.domains.source_connections.create import SourceConnectionCreationService
from airweave.domains.source_connections.delete import SourceConnectionDeletionService
from airweave.domains.source_connections.repository import SourceConnectionRepository
from airweave.domains.source_connections.response import ResponseBuilder
from airweave.domains.source_connections.service import SourceConnectionService
from airweave.domains.source_connections.update import SourceConnectionUpdateService
from airweave.domains.sources.lifecycle import SourceLifecycleService
from airweave.domains.sources.registry import SourceRegistry
from airweave.domains.sources.service import SourceService
from airweave.domains.sources.validation import SourceValidationService
from airweave.domains.syncs.sync_cursor_repository import SyncCursorRepository
from airweave.domains.syncs.sync_job_repository import SyncJobRepository
from airweave.domains.syncs.sync_job_service import SyncJobService
from airweave.domains.syncs.sync_lifecycle_service import SyncLifecycleService
from airweave.domains.syncs.sync_record_service import SyncRecordService
from airweave.domains.syncs.sync_repository import SyncRepository
from airweave.domains.temporal.schedule_service import TemporalScheduleService
from airweave.domains.temporal.service import TemporalWorkflowService
from airweave.domains.usage.ledger import UsageLedger
from airweave.domains.usage.limit_checker import UsageLimitChecker, UsageLimitCheckerProtocol
from airweave.domains.usage.protocols import UsageLedgerProtocol
from airweave.domains.usage.repository import UsageRepository
from airweave.domains.usage.subscribers.billing_listener import UsageBillingListener
from airweave.domains.webhooks.service import WebhookServiceImpl
from airweave.domains.webhooks.subscribers import WebhookEventSubscriber
from airweave.platform.auth.settings import integration_settings
from airweave.platform.sync.subscribers.progress_relay import SyncProgressRelay
from airweave.platform.temporal.client import TemporalClient


def create_container(settings: Settings) -> Container:
    """Build container with environment-appropriate implementations.

    This is the single source of truth for dependency wiring. It reads
    the settings and decides which adapter implementation to use for
    each protocol.

    Args:
        settings: Application settings (from core/config.py)

    Returns:
        Fully constructed Container ready for use

    Example:
        # In main.py or worker.py
        from airweave.core.config import settings
        from airweave.core.container import create_container

        container = create_container(settings)
    """
    # -----------------------------------------------------------------
    # Webhooks (Svix adapter)
    # SvixAdapter implements both WebhookPublisher and WebhookAdmin
    # -----------------------------------------------------------------
    svix_adapter = SvixAdapter()

    # -----------------------------------------------------------------
    # Endpoint verification (plain HTTP, not Svix)
    # -----------------------------------------------------------------
    endpoint_verifier = HttpEndpointVerifier()

    # -----------------------------------------------------------------
    # Billing services
    # -----------------------------------------------------------------
    billing_services = _create_billing_services(settings)

    # -----------------------------------------------------------------
    # Organization repositories
    # -----------------------------------------------------------------
    user_org_repo = UserOrganizationRepository()

    # Source Service + Source Lifecycle Service
    # Auth provider registry is built first, then passed to the source
    # registry so it can compute supported_auth_providers per source.
    # Both services share the same source_registry instance.
    # -----------------------------------------------------------------
    source_deps = _create_source_services(settings)

    # -----------------------------------------------------------------
    # Usage domain — checker (read) + ledger (write), both singletons
    # -----------------------------------------------------------------
    usage_checker = _create_usage_checker(settings, billing_services, source_deps, user_org_repo)
    usage_ledger = _create_usage_ledger(settings, billing_services)
    # -----------------------------------------------------------------
    # Webhook service (composes admin + verifier for API layer)
    # -----------------------------------------------------------------
    webhook_service = WebhookServiceImpl(
        webhook_admin=svix_adapter,
        endpoint_verifier=endpoint_verifier,
        verify_endpoints=settings.WEBHOOK_VERIFY_ENDPOINTS,
    )

    # -----------------------------------------------------------------
    # PubSub (realtime message transport — Redis adapter)
    # -----------------------------------------------------------------

    pubsub = RedisPubSub()

    # -----------------------------------------------------------------
    # Circuit Breaker + OCR
    # Shared circuit breaker tracks provider health across the process.
    # FallbackOcrProvider tries providers in order, skipping tripped ones.
    # -----------------------------------------------------------------
    circuit_breaker = _create_circuit_breaker()
    ocr_provider = _create_ocr_provider(circuit_breaker, settings)

    # -----------------------------------------------------------------
    # Health service
    # Owns shutdown flag and orchestrates readiness probes.
    # -----------------------------------------------------------------
    health = _create_health_service(settings)

    # -----------------------------------------------------------------
    # Metrics (Prometheus adapters, shared registry, wrapped in service)
    # -----------------------------------------------------------------
    metrics = _create_metrics_service(settings)

    event_bus = _create_event_bus(
        webhook_publisher=svix_adapter,
        settings=settings,
        pubsub=pubsub,
        usage_ledger=usage_ledger,
    )

    # -----------------------------------------------------------------
    # Sync domain services
    # Repos come from source_deps; services are built here.
    # -----------------------------------------------------------------

    sync_deps = _create_sync_services(
        event_bus=event_bus,
        sc_repo=source_deps["sc_repo"],
        collection_repo=source_deps["collection_repo"],
        conn_repo=source_deps["conn_repo"],
        cred_repo=source_deps["cred_repo"],
        source_registry=source_deps["source_registry"],
        sync_repo=source_deps["sync_repo"],
        sync_cursor_repo=source_deps["sync_cursor_repo"],
        sync_job_repo=source_deps["sync_job_repo"],
    )

    # SourceConnectionService is built here (not in _create_source_services)
    # because it needs sync_lifecycle which is built in _create_sync_services.
    deletion_service = SourceConnectionDeletionService(
        sc_repo=source_deps["sc_repo"],
        collection_repo=source_deps["collection_repo"],
        sync_job_repo=source_deps["sync_job_repo"],
        sync_lifecycle=sync_deps["sync_lifecycle"],
        response_builder=sync_deps["response_builder"],
        temporal_workflow_service=sync_deps["temporal_workflow_service"],
    )
    source_validation = SourceValidationService(
        source_registry=source_deps["source_registry"],
    )
    encryptor = FernetCredentialEncryptor(settings.ENCRYPTION_KEY)
    init_session_repo = OAuthInitSessionRepository()

    # OAuth flow service
    # -----------------------------------------------------------------
    oauth_flow_svc = OAuthFlowService(
        oauth2_service=source_deps["oauth2_service"],
        oauth1_service=source_deps["oauth1_service"],
        integration_settings=integration_settings,
        init_session_repo=init_session_repo,
        redirect_session_repo=source_deps["redirect_session_repo"],
        settings=settings,
    )

    update_service = SourceConnectionUpdateService(
        sc_repo=source_deps["sc_repo"],
        collection_repo=source_deps["collection_repo"],
        connection_repo=source_deps["conn_repo"],
        cred_repo=source_deps["cred_repo"],
        sync_repo=source_deps["sync_repo"],
        sync_record_service=sync_deps["sync_record_service"],
        source_service=source_deps["source_service"],
        source_validation=source_validation,
        credential_encryptor=encryptor,
        response_builder=sync_deps["response_builder"],
        temporal_schedule_service=sync_deps["temporal_schedule_service"],
    )
    create_service = SourceConnectionCreationService(
        sc_repo=source_deps["sc_repo"],
        collection_repo=source_deps["collection_repo"],
        connection_repo=source_deps["conn_repo"],
        credential_repo=source_deps["cred_repo"],
        source_registry=source_deps["source_registry"],
        source_validation=source_validation,
        source_lifecycle=source_deps["source_lifecycle_service"],
        sync_lifecycle=sync_deps["sync_lifecycle"],
        sync_record_service=sync_deps["sync_record_service"],
        response_builder=sync_deps["response_builder"],
        oauth_flow_service=oauth_flow_svc,
        credential_encryptor=encryptor,
        temporal_workflow_service=sync_deps["temporal_workflow_service"],
        event_bus=event_bus,
    )
    source_connection_service = SourceConnectionService(
        sc_repo=source_deps["sc_repo"],
        collection_repo=source_deps["collection_repo"],
        connection_repo=source_deps["conn_repo"],
        redirect_session_repo=source_deps["redirect_session_repo"],
        source_registry=source_deps["source_registry"],
        auth_provider_registry=source_deps["auth_provider_registry"],
        response_builder=sync_deps["response_builder"],
        sync_lifecycle=sync_deps["sync_lifecycle"],
        create_service=create_service,
        update_service=update_service,
        deletion_service=deletion_service,
    )

    # -----------------------------------------------------------------
    # Embedder registries + instances (deployment-wide singletons)
    # -----------------------------------------------------------------
    dense_embedder_registry = DenseEmbedderRegistry()
    dense_embedder_registry.build()
    sparse_embedder_registry = SparseEmbedderRegistry()
    sparse_embedder_registry.build()

    # Validate env vars, registry lookups, dimensions, and credentials
    # before attempting to construct embedder instances.
    # DB reconciliation happens later in main.py lifespan.
    validate_embedding_config_sync(
        dense_registry=dense_embedder_registry,
        sparse_registry=sparse_embedder_registry,
    )

    dense_embedder = _create_dense_embedder(settings, dense_embedder_registry)
    sparse_embedder = _create_sparse_embedder(sparse_embedder_registry)

    # -----------------------------------------------------------------
    # Collection service (needs collection_repo, sc_repo, sync_lifecycle, dense_registry)
    # -----------------------------------------------------------------
    collection_service = CollectionService(
        collection_repo=source_deps["collection_repo"],
        sc_repo=source_deps["sc_repo"],
        sync_lifecycle=sync_deps["sync_lifecycle"],
        event_bus=event_bus,
        settings=settings,
        deployment_metadata_repo=VectorDbDeploymentMetadataRepository(),
        dense_registry=dense_embedder_registry,
    )

    # OAuth callback service
    # -----------------------------------------------------------------

    oauth_callback_svc = OAuthCallbackService(
        oauth_flow_service=oauth_flow_svc,
        init_session_repo=init_session_repo,
        response_builder=sync_deps["response_builder"],
        source_registry=source_deps["source_registry"],
        sync_lifecycle=sync_deps["sync_lifecycle"],
        sync_record_service=sync_deps["sync_record_service"],
        temporal_workflow_service=sync_deps["temporal_workflow_service"],
        event_bus=event_bus,
        organization_repo=OrgRepo(),
        source_repo=source_deps["source_repo"],
        sc_repo=source_deps["sc_repo"],
        credential_repo=source_deps["cred_repo"],
        connection_repo=source_deps["conn_repo"],
        collection_repo=source_deps["collection_repo"],
        sync_repo=source_deps["sync_repo"],
        sync_job_repo=source_deps["sync_job_repo"],
        credential_encryptor=encryptor,
    )

    # -----------------------------------------------------------------
    # Usage billing listener
    # -----------------------------------------------------------------

    return Container(
        billing_service=billing_services["billing_service"],
        billing_webhook=billing_services["billing_webhook"],
        collection_service=collection_service,
        health=health,
        event_bus=event_bus,
        pubsub=pubsub,
        webhook_publisher=svix_adapter,
        webhook_admin=svix_adapter,
        circuit_breaker=circuit_breaker,
        dense_embedder_registry=dense_embedder_registry,
        sparse_embedder_registry=sparse_embedder_registry,
        dense_embedder=dense_embedder,
        sparse_embedder=sparse_embedder,
        ocr_provider=ocr_provider,
        metrics=metrics,
        source_service=source_deps["source_service"],
        source_registry=source_deps["source_registry"],
        auth_provider_registry=source_deps["auth_provider_registry"],
        sc_repo=source_deps["sc_repo"],
        collection_repo=source_deps["collection_repo"],
        conn_repo=source_deps["conn_repo"],
        cred_repo=source_deps["cred_repo"],
        user_org_repo=user_org_repo,
        oauth1_service=source_deps["oauth1_service"],
        oauth2_service=source_deps["oauth2_service"],
        redirect_session_repo=source_deps["redirect_session_repo"],
        source_connection_service=source_connection_service,
        oauth_flow_service=oauth_flow_svc,
        oauth_callback_service=oauth_callback_svc,
        init_session_repo=init_session_repo,
        source_lifecycle_service=source_deps["source_lifecycle_service"],
        endpoint_verifier=endpoint_verifier,
        webhook_service=webhook_service,
        response_builder=sync_deps["response_builder"],
        sync_repo=source_deps["sync_repo"],
        sync_cursor_repo=source_deps["sync_cursor_repo"],
        sync_job_repo=source_deps["sync_job_repo"],
        payment_gateway=billing_services["payment_gateway"],
        sync_record_service=sync_deps["sync_record_service"],
        sync_job_service=sync_deps["sync_job_service"],
        sync_lifecycle=sync_deps["sync_lifecycle"],
        temporal_workflow_service=sync_deps["temporal_workflow_service"],
        temporal_schedule_service=sync_deps["temporal_schedule_service"],
        usage_checker=usage_checker,
        usage_ledger=usage_ledger,
    )


# ---------------------------------------------------------------------------
# Private factory functions for each dependency
# ---------------------------------------------------------------------------


def _create_health_service(settings: Settings) -> HealthService:
    """Create the health service with infrastructure probes.

    All known probes (postgres, redis, temporal) are always registered.
    The critical-vs-informational split comes from
    ``settings.health_critical_probes``.
    """
    critical_names = settings.health_critical_probes

    probes = {
        "postgres": PostgresHealthProbe(health_check_engine),
        "redis": RedisHealthProbe(redis_client.client),
        "temporal": TemporalHealthProbe(lambda: TemporalClient._client),
    }

    unknown = critical_names - probes.keys()
    if unknown:
        logger.warning(
            "HEALTH_CRITICAL_PROBES references unknown probes: %s",
            ", ".join(sorted(unknown)),
        )

    critical = [p for name, p in probes.items() if name in critical_names]
    informational = [p for name, p in probes.items() if name not in critical_names]

    return HealthService(
        critical=critical,
        informational=informational,
        timeout=settings.HEALTH_CHECK_TIMEOUT,
    )


def _create_metrics_service(settings: Settings) -> PrometheusMetricsService:
    """Build the PrometheusMetricsService with Prometheus adapters and a shared registry."""
    registry = CollectorRegistry()
    return PrometheusMetricsService(
        http=PrometheusHttpMetrics(registry=registry),
        agentic_search=PrometheusAgenticSearchMetrics(registry=registry),
        db_pool=PrometheusDbPoolMetrics(
            registry=registry,
            max_overflow=settings.db_pool_max_overflow,
        ),
        renderer=PrometheusMetricsRenderer(registry=registry),
        host=settings.METRICS_HOST,
        port=settings.METRICS_PORT,
    )


def _create_event_bus(
    webhook_publisher: WebhookPublisher,
    settings: Settings,
    pubsub: PubSub,
    usage_ledger: UsageLedgerProtocol,
) -> EventBus:
    """Create event bus with subscribers wired up.

    The event bus fans out domain events to:
    - WebhookEventSubscriber: External webhooks via Svix (all events)
    - AnalyticsEventSubscriber: PostHog analytics tracking
    - SyncProgressRelay: Relays entity batch events to Redis PubSub (entity.*)
    - UsageBillingListener: Accumulates usage from entity/query/sync/
      source_connection events

    Returns:
        EventBus
    """
    bus = InMemoryEventBus()

    # WebhookEventSubscriber subscribes to * — all domain events
    # Svix channel filtering handles per-endpoint event type matching
    webhook_subscriber = WebhookEventSubscriber(webhook_publisher)
    for pattern in webhook_subscriber.EVENT_PATTERNS:
        bus.subscribe(pattern, webhook_subscriber.handle)

    # AnalyticsEventSubscriber — forwards domain events to PostHog
    tracker = PostHogTracker(settings)
    analytics_subscriber = AnalyticsEventSubscriber(tracker)
    for pattern in analytics_subscriber.EVENT_PATTERNS:
        bus.subscribe(pattern, analytics_subscriber.handle)

    # Sync progress relay (self-initializing from sync.running events)
    progress_relay = SyncProgressRelay(pubsub=pubsub)
    for pattern in progress_relay.EVENT_PATTERNS:
        bus.subscribe(pattern, progress_relay.handle)

    # UsageBillingListener — accumulates usage from entity/query/sync/
    # source_connection events
    usage_billing_listener = UsageBillingListener(ledger=usage_ledger)
    for pattern in usage_billing_listener.EVENT_PATTERNS:
        bus.subscribe(pattern, usage_billing_listener.handle)

    return bus


def _create_circuit_breaker() -> CircuitBreaker:
    """Create the shared circuit breaker for provider failover.

    Uses a 120-second cooldown: after a provider fails, it is skipped
    for 2 minutes before being retried (half-open state).
    """
    return InMemoryCircuitBreaker(cooldown_seconds=120)


def _create_ocr_provider(
    circuit_breaker: CircuitBreaker, settings: Settings
) -> Optional[OcrProvider]:
    """Create OCR provider with fallback chain.

    Chain order: Mistral (cloud) -> Docling (local service, if configured).
    Docling is only added when DOCLING_BASE_URL is set.

    Returns None with a warning when no providers are available.
    """
    try:
        mistral_ocr = MistralOcrAdapter()
    except Exception as e:
        logger.error(f"Error creating Mistral OCR adapter: {e}")
        mistral_ocr = None

    providers = []
    if mistral_ocr:
        providers.append(("mistral-ocr", mistral_ocr))

    if settings.DOCLING_BASE_URL:
        try:
            docling_ocr = DoclingOcrAdapter(base_url=settings.DOCLING_BASE_URL)
            providers.append(("docling", docling_ocr))
        except Exception as e:
            logger.error(f"Error creating Docling OCR adapter: {e}")
            docling_ocr = None

    if not providers:
        logger.warning(
            "No OCR providers available — document processing will be disabled. "
            "Set MISTRAL_API_KEY or DOCLING_BASE_URL to enable OCR."
        )
        return None

    logger.info(f"Creating FallbackOcrProvider with {len(providers)} providers: {providers}")

    return FallbackOcrProvider(providers=providers, circuit_breaker=circuit_breaker)


def _create_dense_embedder(
    settings: Settings, registry: DenseEmbedderRegistry
) -> DenseEmbedderProtocol:
    """Create the deployment-wide dense embedder singleton.

    Uses the domain config constants (DENSE_EMBEDDER, EMBEDDING_DIMENSIONS)
    and the registry to look up the spec and construct the correct embedder.
    """
    from airweave.domains.embedders.dense.local import LocalDenseEmbedder
    from airweave.domains.embedders.dense.mistral import MistralDenseEmbedder
    from airweave.domains.embedders.dense.openai import OpenAIDenseEmbedder

    spec = registry.get(DENSE_EMBEDDER)

    if spec.embedder_class_ref is OpenAIDenseEmbedder:
        return OpenAIDenseEmbedder(
            api_key=settings.OPENAI_API_KEY,
            model=spec.api_model_name,
            dimensions=EMBEDDING_DIMENSIONS,
        )

    if spec.embedder_class_ref is MistralDenseEmbedder:
        return MistralDenseEmbedder(
            api_key=settings.MISTRAL_API_KEY,
            model=spec.api_model_name,
            dimensions=EMBEDDING_DIMENSIONS,
        )

    if spec.embedder_class_ref is LocalDenseEmbedder:
        return LocalDenseEmbedder(
            inference_url=settings.TEXT2VEC_INFERENCE_URL,
            dimensions=EMBEDDING_DIMENSIONS,
        )

    raise ValueError(f"Unknown dense embedder class: {spec.embedder_class_ref}")


def _create_sparse_embedder(registry: SparseEmbedderRegistry) -> SparseEmbedderProtocol:
    """Create the deployment-wide sparse embedder singleton.

    Uses the domain config constant (SPARSE_EMBEDDER) and the registry
    to look up the spec and construct the correct embedder.
    """
    spec = registry.get(SPARSE_EMBEDDER)

    return DomainFastEmbedSparseEmbedder(model=spec.api_model_name)


def _create_source_services(settings: Settings) -> dict:
    """Create source services, registries, repository adapters, and lifecycle service.

    Build order matters:
    1. Auth provider registry (no dependencies)
    2. Entity definition registry (no dependencies)
    3. Source registry (depends on both)
    4. Repository adapters (thin wrappers around crud singletons)
    5. OAuth2 service (with injected repos, encryptor, settings)
    6. SourceLifecycleService (depends on all of the above)
    """
    auth_provider_registry = AuthProviderRegistry()
    auth_provider_registry.build()

    entity_definition_registry = EntityDefinitionRegistry()
    entity_definition_registry.build()

    source_registry = SourceRegistry(auth_provider_registry, entity_definition_registry)
    source_registry.build()

    # Repository adapters
    sc_repo = SourceConnectionRepository()
    collection_repo = CollectionRepository()
    conn_repo = ConnectionRepository()
    cred_repo = IntegrationCredentialRepository()
    sync_repo = SyncRepository()
    sync_cursor_repo = SyncCursorRepository()
    sync_job_repo = SyncJobRepository()
    redirect_session_repo = OAuthRedirectSessionRepository()
    source_repo = OAuthSourceRepository()
    oauth1_svc = OAuth1Service()
    oauth2_svc = OAuth2Service(
        settings=settings,
        conn_repo=OAuthConnectionRepository(),
        cred_repo=OAuthCredentialRepository(),
        encryptor=FernetCredentialEncryptor(settings.ENCRYPTION_KEY),
        source_repo=source_repo,
    )

    source_service = SourceService(
        source_registry=source_registry,
        settings=settings,
    )
    source_lifecycle_service = SourceLifecycleService(
        source_registry=source_registry,
        auth_provider_registry=auth_provider_registry,
        sc_repo=sc_repo,
        conn_repo=conn_repo,
        cred_repo=cred_repo,
        oauth2_service=oauth2_svc,
    )

    return {
        "source_service": source_service,
        "source_registry": source_registry,
        "auth_provider_registry": auth_provider_registry,
        "sc_repo": sc_repo,
        "collection_repo": collection_repo,
        "conn_repo": conn_repo,
        "cred_repo": cred_repo,
        "oauth1_service": oauth1_svc,
        "oauth2_service": oauth2_svc,
        "source_repo": source_repo,
        "redirect_session_repo": redirect_session_repo,
        "source_lifecycle_service": source_lifecycle_service,
        "sync_repo": sync_repo,
        "sync_cursor_repo": sync_cursor_repo,
        "sync_job_repo": sync_job_repo,
    }


def _create_payment_gateway(settings: Settings) -> PaymentGatewayProtocol:
    """Create payment gateway: Stripe if enabled, otherwise a null implementation."""
    if settings.STRIPE_ENABLED:
        from airweave.adapters.payment.stripe import StripePaymentGateway

        return StripePaymentGateway()

    from airweave.adapters.payment.null import NullPaymentGateway

    return NullPaymentGateway()


def _create_billing_services(settings: Settings) -> dict:
    """Create billing service and webhook processor with shared dependencies."""
    from airweave.domains.billing.operations import BillingOperations
    from airweave.domains.billing.repository import (
        BillingPeriodRepository,
        OrganizationBillingRepository,
    )
    from airweave.domains.billing.service import BillingService
    from airweave.domains.billing.webhook_processor import BillingWebhookProcessor
    from airweave.domains.organizations.repository import OrganizationRepository
    from airweave.domains.usage.repository import UsageRepository

    payment_gateway = _create_payment_gateway(settings)
    billing_repo = OrganizationBillingRepository()
    period_repo = BillingPeriodRepository()
    org_repo = OrganizationRepository()
    usage_repo = UsageRepository()
    billing_ops = BillingOperations(
        billing_repo=billing_repo,
        period_repo=period_repo,
        usage_repo=usage_repo,
        payment_gateway=payment_gateway,
    )

    billing_service = BillingService(
        payment_gateway=payment_gateway,
        billing_repo=billing_repo,
        period_repo=period_repo,
        billing_ops=billing_ops,
        org_repo=org_repo,
    )
    billing_webhook = BillingWebhookProcessor(
        payment_gateway=payment_gateway,
        billing_repo=billing_repo,
        period_repo=period_repo,
        billing_ops=billing_ops,
        org_repo=org_repo,
    )

    return {
        "billing_service": billing_service,
        "billing_webhook": billing_webhook,
        "payment_gateway": payment_gateway,
        "billing_repo": billing_repo,
        "period_repo": period_repo,
    }


def _create_sync_services(
    event_bus: EventBus,
    sc_repo: SourceConnectionRepository,
    collection_repo: CollectionRepository,
    conn_repo: ConnectionRepository,
    cred_repo: IntegrationCredentialRepository,
    source_registry: SourceRegistry,
    sync_repo: SyncRepository,
    sync_cursor_repo: SyncCursorRepository,
    sync_job_repo: SyncJobRepository,
) -> dict:
    """Create sync-domain services and orchestrator.

    Repos are passed in from _create_source_services (single source of truth).

    Build order:
    1. Leaf services (SyncJobService, TemporalWorkflowService)
    2. Composite services (SyncRecordService, ResponseBuilder)
    3. TemporalScheduleService (needs repos)
    4. SyncLifecycleService (needs everything above)
    """
    entity_count_repo = EntityCountRepository()

    sync_job_service = SyncJobService(sync_job_repo=sync_job_repo)
    temporal_workflow_service = TemporalWorkflowService()

    sync_record_service = SyncRecordService(
        sync_repo=sync_repo,
        sync_job_repo=sync_job_repo,
        connection_repo=conn_repo,
    )

    response_builder = ResponseBuilder(
        sc_repo=sc_repo,
        connection_repo=conn_repo,
        credential_repo=cred_repo,
        source_registry=source_registry,
        entity_count_repo=entity_count_repo,
        sync_job_repo=sync_job_repo,
    )

    temporal_schedule_service = TemporalScheduleService(
        sync_repo=sync_repo,
        sc_repo=sc_repo,
        collection_repo=collection_repo,
        connection_repo=conn_repo,
    )

    sync_lifecycle = SyncLifecycleService(
        sc_repo=sc_repo,
        collection_repo=collection_repo,
        connection_repo=conn_repo,
        sync_cursor_repo=sync_cursor_repo,
        sync_service=sync_record_service,
        sync_job_service=sync_job_service,
        sync_job_repo=sync_job_repo,
        temporal_workflow_service=temporal_workflow_service,
        temporal_schedule_service=temporal_schedule_service,
        response_builder=response_builder,
        event_bus=event_bus,
    )

    return {
        "sync_record_service": sync_record_service,
        "sync_job_service": sync_job_service,
        "sync_lifecycle": sync_lifecycle,
        "temporal_workflow_service": temporal_workflow_service,
        "temporal_schedule_service": temporal_schedule_service,
        "response_builder": response_builder,
    }


def _create_usage_checker(
    settings: Settings,
    billing_deps: dict,
    source_deps: dict,
    user_org_repo: UserOrganizationRepositoryProtocol,
) -> UsageLimitCheckerProtocol:
    """Create the singleton UsageLimitChecker."""
    from airweave.domains.usage.limit_checker import AlwaysAllowLimitChecker

    if settings.LOCAL_DEVELOPMENT:
        return AlwaysAllowLimitChecker()

    return UsageLimitChecker(
        usage_repo=UsageRepository(),
        billing_repo=billing_deps["billing_repo"],
        period_repo=billing_deps["period_repo"],
        sc_repo=source_deps["sc_repo"],
        user_org_repo=user_org_repo,
    )


def _create_usage_ledger(settings: Settings, billing_deps: dict) -> UsageLedgerProtocol:
    """Create the singleton UsageLedger."""
    from airweave.domains.usage.ledger import NullUsageLedger
    from airweave.domains.usage.repository import UsageRepository

    if settings.LOCAL_DEVELOPMENT:
        return NullUsageLedger()

    return UsageLedger(
        usage_repo=UsageRepository(),
        billing_repo=billing_deps["billing_repo"],
        period_repo=billing_deps["period_repo"],
    )
