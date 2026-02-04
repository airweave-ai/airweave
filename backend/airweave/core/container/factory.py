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
    --------
        # In main.py or worker.py
        from airweave.core.config import settings
        from airweave.core.container import create_container

        container = create_container(settings)
    """
    # -----------------------------------------------------------------
    # Webhooks (Svix-based)
    # The WebhooksService implements both EventMessageStore and WebhookSender
    # -----------------------------------------------------------------
    webhooks_service = _create_webhooks_service(settings)

    return Container(
        event_message_store=webhooks_service,
        webhook_sender=webhooks_service,
    )


# ---------------------------------------------------------------------------
# Private factory functions for each dependency
# ---------------------------------------------------------------------------


def _create_webhooks_service(settings: Settings):
    """Create webhooks service for event storage and sending.

    The WebhooksService wraps Svix and implements both:
    - EventMessageStore: reading messages, attempts, subscriptions
    - WebhookSender: publishing sync events

    All environments use Svix (runs locally in docker-compose too).
    """
    # Import here to avoid circular imports at module load time
    from airweave.webhooks.service import WebhooksService

    # WebhooksService reads settings internally (SVIX_URL, SVIX_JWT_SECRET)
    # so we just instantiate it without passing settings
    return WebhooksService()
