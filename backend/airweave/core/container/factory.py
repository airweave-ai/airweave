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

from airweave.adapters.ocr.docling import DoclingOcrAdapter
from airweave.adapters.webhooks.svix import SvixAdapter
from airweave.core.auth_provider_service import auth_provider_service
from airweave.core.container.container import Container
from airweave.core.logging import logger

# The legacy helpers singleton -- wrapped via protocol for testability
from airweave.core.source_connection_service_helpers import source_connection_helpers
from airweave.core.sync_job_service import sync_job_service
from airweave.core.sync_service import sync_service
from airweave.core.temporal_service import temporal_service
from airweave.domains.auth_provider.registry import AuthProviderRegistry
from airweave.domains.collections.repository import CollectionRepository
from airweave.domains.connections.repository import ConnectionRepository
from airweave.domains.credentials.repository import IntegrationCredentialRepository
from airweave.domains.credentials.service import CredentialService
from airweave.domains.entities.registry import EntityDefinitionRegistry
from airweave.domains.entity_counts.repository import EntityCountRepository
from airweave.domains.source_connections.repository import SourceConnectionRepository
from airweave.domains.source_connections.response import ResponseBuilder
from airweave.domains.source_connections.service import SourceConnectionService
from airweave.domains.sources.registry import SourceRegistry
from airweave.domains.sources.service import SourceService
from airweave.domains.sync_cursors.repository import SyncCursorRepository
from airweave.domains.sync_jobs.repository import SyncJobRepository
from airweave.domains.syncs.repository import SyncRepository
from airweave.platform.temporal.schedule_service import temporal_schedule_service

if TYPE_CHECKING:
    from airweave.core.config import Settings
    from airweave.core.protocols import (
        CircuitBreaker,
        CredentialServiceProtocol,
        OAuthFlowServiceProtocol,
        OcrProvider,
    )


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

    # -----------------------------------------------------------------
    # Source Registry
    # -----------------------------------------------------------------
    source_registry = _create_source_registry()

    # Source Service
    # Auth provider registry is built first, then passed to the source
    # registry so it can compute supported_auth_providers per source.
    # -----------------------------------------------------------------
    source_service = _create_source_service(source_registry, settings)

    # Credential Service
    # Cross-cutting: uses SourceRegistry for schema lookups
    # -----------------------------------------------------------------
    credential_service = _create_credential_service(source_registry)

    # OAuth Flow Service
    # Cross-cutting: OAuth initiation and completion
    # -----------------------------------------------------------------
    oauth_flow_service = _create_oauth_flow_service()

    # Source Connection Service
    # Domain service orchestrating all source connection operations
    # -----------------------------------------------------------------
    source_connection_service = _create_source_connection_service(
        source_registry, credential_service, oauth_flow_service, event_bus
    )

    return Container(
        event_bus=event_bus,
        webhook_publisher=svix_adapter,
        webhook_admin=svix_adapter,
        circuit_breaker=circuit_breaker,
        ocr_provider=ocr_provider,
        source_service=source_service,
        credential_service=credential_service,
        oauth_flow_service=oauth_flow_service,
        source_connection_service=source_connection_service,
    )


# ---------------------------------------------------------------------------
# Private factory functions for each dependency
# ---------------------------------------------------------------------------


def _create_event_bus(webhook_publisher):
    """Create event bus with subscribers wired up.

    The event bus fans out domain events to:
    - WebhookEventSubscriber: External webhooks via Svix (all events)

    Future subscribers:
    - PubSubSubscriber: Redis PubSub for real-time UI updates
    - AnalyticsSubscriber: PostHog tracking
    """
    from airweave.adapters.event_bus import InMemoryEventBus
    from airweave.domains.webhooks import WebhookEventSubscriber

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
    from airweave.adapters.circuit_breaker import InMemoryCircuitBreaker

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


def _create_source_registry() -> SourceRegistry:
    """Create source registry with its dependencies."""
    auth_provider_registry = AuthProviderRegistry()
    auth_provider_registry.build()

    entity_definition_registry = EntityDefinitionRegistry()
    entity_definition_registry.build()

    source_registry = SourceRegistry(auth_provider_registry, entity_definition_registry)
    source_registry.build()
    return source_registry


def _create_source_service(source_registry: SourceRegistry, settings: Settings) -> SourceService:
    source_service = SourceService(
        source_registry=source_registry,
        settings=settings,
    )
    return source_service


def _create_credential_service(source_registry) -> "CredentialServiceProtocol":
    """Create credential service using the shared source registry."""
    credential_repo = IntegrationCredentialRepository()
    return CredentialService(
        source_registry=source_registry,
        credential_repo=credential_repo,
    )


def _create_oauth_flow_service() -> "OAuthFlowServiceProtocol":
    """Create OAuth flow service with real OAuth adapters."""
    from airweave.domains.oauth.service import OAuthFlowService
    from airweave.platform.auth.oauth1_service import oauth1_service
    from airweave.platform.auth.oauth2_service import oauth2_service
    from airweave.platform.auth.settings import integration_settings

    return OAuthFlowService(
        oauth2_service=oauth2_service,
        oauth1_service=oauth1_service,
        integration_settings=integration_settings,
    )


def _create_source_connection_service(
    source_registry, credential_service, oauth_flow_service, event_bus
):
    """Create source connection service with all dependencies."""
    from airweave.domains.credentials.repository import IntegrationCredentialRepository

    sc_repo = SourceConnectionRepository()
    collection_repo = CollectionRepository()
    connection_repo = ConnectionRepository()
    credential_repo = IntegrationCredentialRepository()
    entity_count_repo = EntityCountRepository()
    sync_job_repo = SyncJobRepository()
    sync_repo = SyncRepository()
    sync_cursor_repo = SyncCursorRepository()

    response_builder = ResponseBuilder(
        sc_repo=sc_repo,
        connection_repo=connection_repo,
        credential_repo=credential_repo,
        source_registry=source_registry,
        entity_count_repo=entity_count_repo,
        sync_service=sync_service,
    )

    return SourceConnectionService(
        sc_repo=sc_repo,
        response_builder=response_builder,
        source_registry=source_registry,
        credential_service=credential_service,
        oauth_flow_service=oauth_flow_service,
        collection_repo=collection_repo,
        connection_repo=connection_repo,
        sync_job_repo=sync_job_repo,
        sync_cursor_repo=sync_cursor_repo,
        sync_repo=sync_repo,
        sync_service=sync_service,
        temporal_service=temporal_service,
        sync_job_service=sync_job_service,
        temporal_schedule_service=temporal_schedule_service,
        helpers=source_connection_helpers,
        auth_provider_service=auth_provider_service,
        event_bus=event_bus,
    )
