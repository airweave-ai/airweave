"""Webhook service implementation.

Implements the ``WebhookService`` protocol by composing ``WebhookAdmin``
(Svix CRUD) and ``EndpointVerifier`` (HTTP ping) behind a single class.
The API layer injects this service — it never touches the lower-level
adapter protocols directly.

Construction happens in the container factory which passes the
``verify_endpoints`` flag from settings, so the service owns the
"should I verify?" decision.
"""

import asyncio
from datetime import datetime
from typing import Optional
from uuid import UUID

from airweave.core.protocols.webhooks import EndpointVerifier, WebhookAdmin
from airweave.domains.webhooks.types import (
    DeliveryAttempt,
    EventMessage,
    HealthStatus,
    RecoveryTask,
    Subscription,
    WebhooksError,
    compute_health_status,
)


class WebhookServiceImpl:
    """Webhook service composing WebhookAdmin + EndpointVerifier.

    Args:
        webhook_admin: Infrastructure adapter for subscription/message CRUD.
        endpoint_verifier: HTTP verifier for endpoint reachability checks.
        verify_endpoints: Whether to verify endpoints before creating
            subscriptions.  Set from ``settings.WEBHOOK_VERIFY_ENDPOINTS``
            at container construction time.
    """

    def __init__(
        self,
        webhook_admin: WebhookAdmin,
        endpoint_verifier: EndpointVerifier,
        verify_endpoints: bool = True,
    ) -> None:
        """Initialize with admin adapter, verifier, and verification flag."""
        self._admin = webhook_admin
        self._verifier = endpoint_verifier
        self._verify_endpoints = verify_endpoints

    # -------------------------------------------------------------------------
    # Subscriptions (orchestrated)
    # -------------------------------------------------------------------------

    async def list_subscriptions_with_health(
        self,
        org_id: UUID,
    ) -> list[tuple[Subscription, HealthStatus, list[DeliveryAttempt]]]:
        """List subscriptions with computed health status.

        For each subscription the most recent delivery attempts are fetched
        in parallel.  If fetching attempts for a single subscription fails,
        it is returned with ``HealthStatus.unknown``.
        """
        subscriptions = await self._admin.list_subscriptions(org_id)

        attempts_results = await asyncio.gather(
            *[
                self._admin.get_subscription_attempts(org_id, sub.id, limit=10)
                for sub in subscriptions
            ],
            return_exceptions=True,
        )

        result: list[tuple[Subscription, HealthStatus, list[DeliveryAttempt]]] = []
        for sub, attempts_or_exc in zip(subscriptions, attempts_results, strict=False):
            if isinstance(attempts_or_exc, Exception):
                result.append((sub, HealthStatus.unknown, []))
            else:
                health = compute_health_status(attempts_or_exc)
                result.append((sub, health, attempts_or_exc))
        return result

    async def get_subscription_detail(
        self,
        org_id: UUID,
        subscription_id: str,
        include_secret: bool = False,
    ) -> tuple[Subscription, list[DeliveryAttempt], Optional[str]]:
        """Get subscription with delivery attempts and optional signing secret."""
        subscription = await self._admin.get_subscription(org_id, subscription_id)
        attempts = await self._admin.get_subscription_attempts(org_id, subscription_id)

        secret: Optional[str] = None
        if include_secret:
            secret = await self._admin.get_subscription_secret(org_id, subscription_id)

        return subscription, attempts, secret

    async def create_subscription(
        self,
        org_id: UUID,
        url: str,
        event_types: list[str],
        secret: Optional[str] = None,
    ) -> Subscription:
        """Create a subscription, verifying the endpoint if configured.

        Endpoint verification is controlled by the ``verify_endpoints``
        flag passed at construction time.
        """
        if self._verify_endpoints:
            await self._verifier.verify(url)

        return await self._admin.create_subscription(org_id, url, event_types, secret)

    async def update_subscription(
        self,
        org_id: UUID,
        subscription_id: str,
        url: Optional[str] = None,
        event_types: Optional[list[str]] = None,
        disabled: Optional[bool] = None,
        recover_since: Optional[datetime] = None,
    ) -> Subscription:
        """Update a subscription with optional recovery on re-enable.

        When re-enabling (``disabled=False``) with a ``recover_since``
        timestamp, a best-effort message recovery is triggered.
        """
        subscription = await self._admin.update_subscription(
            org_id,
            subscription_id,
            url,
            event_types,
            disabled=disabled,
        )

        if disabled is False and recover_since is not None:
            try:
                await self._admin.recover_messages(org_id, subscription_id, since=recover_since)
            except WebhooksError:
                pass

        return subscription

    async def delete_subscription(
        self,
        org_id: UUID,
        subscription_id: str,
    ) -> Subscription:
        """Delete a subscription. Returns the subscription before deletion."""
        subscription = await self._admin.get_subscription(org_id, subscription_id)
        await self._admin.delete_subscription(org_id, subscription_id)
        return subscription

    # -------------------------------------------------------------------------
    # Messages (pass-through)
    # -------------------------------------------------------------------------

    async def get_messages(
        self,
        org_id: UUID,
        event_types: Optional[list[str]] = None,
    ) -> list[EventMessage]:
        """Get event messages for an organization."""
        return await self._admin.get_messages(org_id, event_types=event_types)

    async def get_message(
        self,
        org_id: UUID,
        message_id: str,
    ) -> EventMessage:
        """Get a specific message."""
        return await self._admin.get_message(org_id, message_id)

    async def get_message_attempts(
        self,
        org_id: UUID,
        message_id: str,
    ) -> list[DeliveryAttempt]:
        """Get delivery attempts for a message."""
        return await self._admin.get_message_attempts(org_id, message_id)

    # -------------------------------------------------------------------------
    # Recovery
    # -------------------------------------------------------------------------

    async def recover_messages(
        self,
        org_id: UUID,
        subscription_id: str,
        since: datetime,
        until: Optional[datetime] = None,
    ) -> RecoveryTask:
        """Recover failed messages for a subscription."""
        return await self._admin.recover_messages(org_id, subscription_id, since=since, until=until)
