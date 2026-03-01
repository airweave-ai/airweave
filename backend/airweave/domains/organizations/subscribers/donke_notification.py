"""Donke notification subscriber — notifies the Donke agent about new signups.

Best-effort HTTP call; failures are logged and swallowed.
"""

import logging

import httpx

from airweave.core.config import settings
from airweave.core.events.organization import OrganizationLifecycleEvent

logger = logging.getLogger(__name__)


class DonkeNotificationSubscriber:
    """Sends a signup notification to the Donke agent on organization.created."""

    EVENT_PATTERNS = ["organization.created"]

    async def handle(self, event: OrganizationLifecycleEvent) -> None:
        """Notify Donke agent about new organization signup (best-effort)."""
        if not settings.DONKE_URL or not settings.DONKE_API_KEY:
            return

        if event.event_type.value != "organization.created":
            return

        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{settings.DONKE_URL}/api/notify-signup?code={settings.DONKE_API_KEY}",
                    headers={"Content-Type": "application/json"},
                    json={
                        "organization_name": event.organization_name,
                        "user_email": event.owner_email,
                        "plan": event.plan or "developer",
                        "organization_id": str(event.organization_id),
                    },
                    timeout=5.0,
                )
                logger.info(f"Notified Donke about signup for org {event.organization_id}")
        except Exception as e:
            logger.warning(f"Failed to notify Donke about signup: {e}")
