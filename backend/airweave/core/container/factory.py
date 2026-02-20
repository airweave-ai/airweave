"""Container Factory.

All construction logic lives here. The factory reads settings and builds
the container with environment-appropriate implementations.

Design principles:
- Single place for all wiring decisions
- Environment-aware: local vs dev vs prd
- Fail fast: broken wiring crashes at startup, not at 3am
- Testable: can unit test factory logic with mock settings
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from airweave.adapters.circuit_breaker import InMemoryCircuitBreaker
from airweave.adapters.event_bus.in_memory import InMemoryEventBus
from airweave.adapters.ocr.docling import DoclingOcrAdapter
from airweave.adapters.webhooks.endpoint_verifier import HttpEndpointVerifier
from airweave.adapters.webhooks.svix import SvixAdapter
from airweave.core.container.container import Container
from airweave.core.logging import logger
from airweave.core.protocols.event_bus import EventBus
from airweave.core.protocols.webhooks import WebhookPublisher
from airweave.domains.auth_provider.registry import AuthProviderRegistry
from airweave.domains.connections.repository import ConnectionRepository
from airweave.domains.credentials.repository import IntegrationCredentialRepository
from airweave.domains.entities.registry import EntityDefinitionRegistry
from airweave.domains.oauth.oauth2_service import OAuth2Service
from airweave.domains.source_connections.repository import SourceConnectionRepository
from airweave.domains.sources.lifecycle import SourceLifecycleService
from airweave.domains.sources.registry import SourceRegistry
from airweave.domains.sources.service import SourceService
from airweave.domains.webhooks.service import WebhookServiceImpl
from airweave.domains.webhooks.subscribers import WebhookEventSubscriber

if TYPE_CHECKING:
    from airweave.core.config import Settings
    from airweave.core.protocols import CircuitBreaker, OcrProvider
    from airweave.core.protocols.event_bus import EventBus
    from airweave.core.protocols.payment import PaymentGatewayProtocol


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
    # Webhook service (composes admin + verifier for API layer)
    # -----------------------------------------------------------------
    webhook_service = WebhookServiceImpl(
        webhook_admin=svix_adapter,
        endpoint_verifier=endpoint_verifier,
        verify_endpoints=settings.WEBHOOK_VERIFY_ENDPOINTS,
    )

    # -----------------------------------------------------------------
    # Event Bus
    # Fans out domain events to subscribers (webhooks, analytics, etc.)
    # -----------------------------------------------------------------
    event_bus = _create_event_bus(webhook_publisher=svix_adapter)

    # -----------------------------------------------------------------
    # Circuit Breaker + OCR
    # Shared circuit breaker tracks provider health across the process.
    # FallbackOcrProvider tries providers in order, skipping tripped ones.
    # -----------------------------------------------------------------
    circuit_breaker = _create_circuit_breaker()
    ocr_provider = _create_ocr_provider(circuit_breaker, settings)

    # Source Service + Source Lifecycle Service
    # Auth provider registry is built first, then passed to the source
    # registry so it can compute supported_auth_providers per source.
    # Both services share the same source_registry instance.
    # -----------------------------------------------------------------
    source_deps = _create_source_services(settings)

    # -----------------------------------------------------------------
    # Billing domain (payment gateway + service + webhook processor)
    # -----------------------------------------------------------------
    billing_deps = _create_billing_services(settings)

    # -----------------------------------------------------------------
    # Usage domain (factory creates per-org enforcement services)
    # -----------------------------------------------------------------
    usage_service_factory = _create_usage_service_factory(settings, billing_deps, source_deps)

    return Container(
        event_bus=event_bus,
        webhook_publisher=svix_adapter,
        webhook_admin=svix_adapter,
        circuit_breaker=circuit_breaker,
        ocr_provider=ocr_provider,
        source_service=source_deps["source_service"],
        source_registry=source_deps["source_registry"],
        auth_provider_registry=source_deps["auth_provider_registry"],
        sc_repo=source_deps["sc_repo"],
        conn_repo=source_deps["conn_repo"],
        cred_repo=source_deps["cred_repo"],
        oauth2_service=source_deps["oauth2_service"],
        source_lifecycle_service=source_deps["source_lifecycle_service"],
        endpoint_verifier=endpoint_verifier,
        webhook_service=webhook_service,
        billing_service=billing_deps["billing_service"],
        billing_webhook=billing_deps["billing_webhook"],
        usage_service_factory=usage_service_factory,
    )


# ---------------------------------------------------------------------------
# Private factory functions for each dependency
# ---------------------------------------------------------------------------


def _create_event_bus(webhook_publisher: WebhookPublisher) -> EventBus:
    """Create event bus with subscribers wired up.

    The event bus fans out domain events to:
    - WebhookEventSubscriber: External webhooks via Svix (all events)

    Future subscribers:
    - PubSubSubscriber: Redis PubSub for real-time UI updates
    - AnalyticsSubscriber: PostHog tracking
    """
    bus = InMemoryEventBus()

    # WebhookEventSubscriber subscribes to * — all domain events
    # Svix channel filtering handles per-endpoint event type matching
    webhook_subscriber = WebhookEventSubscriber(webhook_publisher)
    for pattern in webhook_subscriber.EVENT_PATTERNS:
        bus.subscribe(pattern, webhook_subscriber.handle)

    return bus


def _create_circuit_breaker() -> "CircuitBreaker":
    """Create the shared circuit breaker for provider failover.

    Uses a 120-second cooldown: after a provider fails, it is skipped
    for 2 minutes before being retried (half-open state).
    """
    return InMemoryCircuitBreaker(cooldown_seconds=120)


def _create_ocr_provider(circuit_breaker: "CircuitBreaker", settings: "Settings") -> "OcrProvider":
    """Create OCR provider with fallback chain.

    Chain order: Mistral (cloud) -> Docling (local service, if configured).
    Docling is only added when DOCLING_BASE_URL is set.

    raises: ValueError if no OCR providers are available
    returns: FallbackOcrProvider with the available OCR providers
    """
    from airweave.adapters.ocr.fallback import FallbackOcrProvider
    from airweave.adapters.ocr.mistral import MistralOcrAdapter

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
        raise ValueError("No OCR providers available")

    logger.info(f"Creating FallbackOcrProvider with {len(providers)} providers: {providers}")

    return FallbackOcrProvider(providers=providers, circuit_breaker=circuit_breaker)


def _create_source_services(settings: Settings) -> dict:
    """Create source services, registries, repository adapters, and lifecycle service.

    Build order matters:
    1. Auth provider registry (no dependencies)
    2. Entity definition registry (no dependencies)
    3. Source registry (depends on both)
    4. Repository adapters (thin wrappers around crud singletons)
    5. OAuth2 adapter (thin wrapper around oauth2_service singleton)
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
    conn_repo = ConnectionRepository()
    cred_repo = IntegrationCredentialRepository()
    oauth2_svc = OAuth2Service()

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
        "conn_repo": conn_repo,
        "cred_repo": cred_repo,
        "oauth2_service": oauth2_svc,
        "source_lifecycle_service": source_lifecycle_service,
    }


def _create_payment_gateway(settings: "Settings") -> "PaymentGatewayProtocol":
    """Create payment gateway: Stripe if enabled, otherwise a null implementation."""
    if settings.STRIPE_ENABLED:
        from airweave.adapters.payment.stripe import StripePaymentGateway

        return StripePaymentGateway()

    from airweave.adapters.payment.null import NullPaymentGateway

    return NullPaymentGateway()


def _create_billing_services(settings: "Settings") -> dict:
    """Create billing service and webhook processor with shared dependencies."""
    from airweave.domains.billing.operations import BillingOperations
    from airweave.domains.billing.repository import (
        BillingPeriodRepository,
        OrganizationBillingRepository,
    )
    from airweave.domains.billing.service import BillingService
    from airweave.domains.billing.webhook_processor import BillingWebhookProcessor
    from airweave.domains.organizations.repository import OrganizationRepository

    payment_gateway = _create_payment_gateway(settings)
    billing_repo = OrganizationBillingRepository()
    period_repo = BillingPeriodRepository()
    org_repo = OrganizationRepository()
    billing_ops = BillingOperations(billing_repo=billing_repo, payment_gateway=payment_gateway)

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
        "billing_repo": billing_repo,
        "period_repo": period_repo,
    }


def _create_usage_service_factory(settings: "Settings", billing_deps: dict, source_deps: dict):
    """Create usage service factory: real if billing is enabled, null for local dev."""
    if settings.LOCAL_DEVELOPMENT:
        from airweave.domains.usage.factory import NullUsageServiceFactory

        return NullUsageServiceFactory()

    from airweave.domains.organizations.repository import UserOrganizationRepository
    from airweave.domains.usage.factory import UsageServiceFactory
    from airweave.domains.usage.repository import UsageRepository

    return UsageServiceFactory(
        usage_repo=UsageRepository(),
        billing_repo=billing_deps["billing_repo"],
        period_repo=billing_deps["period_repo"],
        sc_repo=source_deps["sc_repo"],
        user_org_repo=UserOrganizationRepository(),
    )
