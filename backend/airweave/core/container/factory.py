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

from airweave.adapters.webhooks.svix import SvixAdapter
from airweave.core.container.container import Container

if TYPE_CHECKING:
    from airweave.core.config import Settings


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

    return Container(
        event_bus=event_bus,
        webhook_publisher=svix_adapter,
        webhook_admin=svix_adapter,
    )


# ---------------------------------------------------------------------------
# Private factory functions for each dependency
# ---------------------------------------------------------------------------


def _create_event_bus(webhook_publisher):
    """Create event bus with subscribers wired up.

    The event bus fans out domain events to:
    - SyncEventSubscriber: External webhooks (domains/webhooks)

    Future subscribers:
    - AnalyticsSubscriber: PostHog tracking
    - RealtimeSubscriber: Redis PubSub for UI updates
    """
    from airweave.adapters.event_bus import InMemoryEventBus
    from airweave.domains.webhooks import SyncEventSubscriber

    bus = InMemoryEventBus()

    # Wire up domain subscribers (they declare their own EVENT_PATTERNS)
    sync_subscriber = SyncEventSubscriber(webhook_publisher)
    for pattern in sync_subscriber.EVENT_PATTERNS:
        bus.subscribe(pattern, sync_subscriber.handle)

    return bus
