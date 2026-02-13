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
from airweave.core.container.container import Container
from airweave.core.logging import logger

if TYPE_CHECKING:
    from airweave.core.config import Settings
    from airweave.core.protocols import CircuitBreaker, OcrProvider


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

    return Container(
        event_bus=event_bus,
        webhook_publisher=svix_adapter,
        webhook_admin=svix_adapter,
        circuit_breaker=circuit_breaker,
        ocr_provider=ocr_provider,
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
