"""Webhook domain operations.

Business logic for managing webhook subscriptions and viewing message
history.  Orchestrates calls to the ``WebhookAdmin`` and
``EndpointVerifier`` protocols — keeps the API layer thin and the
adapter layer infrastructure-only.

All public functions receive their dependencies as keyword arguments
so that tests can inject fakes without monkey-patching.
"""

import asyncio
from datetime import datetime
from typing import Optional
from uuid import UUID

from airweave.core.protocols.webhooks import EndpointVerifier, WebhookAdmin
from airweave.domains.webhooks.types import (
    DeliveryAttempt,
    HealthStatus,
    Subscription,
    WebhooksError,
    compute_health_status,
)

# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


async def list_subscriptions_with_health(
    org_id: UUID,
    *,
    webhook_admin: WebhookAdmin,
) -> list[tuple[Subscription, HealthStatus, list[DeliveryAttempt]]]:
    """Fetch all subscriptions with computed health status.

    For each subscription the most recent delivery attempts are fetched in
    parallel so the caller can display health information.  If fetching
    attempts for a single subscription fails, it is returned with
    ``HealthStatus.unknown``.

    Returns:
        A list of ``(subscription, health_status, delivery_attempts)`` tuples.
    """
    subscriptions = await webhook_admin.list_subscriptions(org_id)

    # Fan out to get recent attempts in parallel
    attempts_results = await asyncio.gather(
        *[
            webhook_admin.get_subscription_attempts(org_id, sub.id, limit=10)
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
    org_id: UUID,
    subscription_id: str,
    *,
    webhook_admin: WebhookAdmin,
    include_secret: bool = False,
) -> tuple[Subscription, list[DeliveryAttempt], Optional[str]]:
    """Fetch a subscription with delivery attempts and optional signing secret.

    Returns:
        A ``(subscription, delivery_attempts, secret_or_none)`` tuple.
    """
    subscription = await webhook_admin.get_subscription(org_id, subscription_id)

    attempts = await webhook_admin.get_subscription_attempts(org_id, subscription_id)

    secret: Optional[str] = None
    if include_secret:
        secret = await webhook_admin.get_subscription_secret(org_id, subscription_id)

    return subscription, attempts, secret


async def create_subscription(
    org_id: UUID,
    url: str,
    event_types: list[str],
    secret: Optional[str],
    *,
    webhook_admin: WebhookAdmin,
    endpoint_verifier: EndpointVerifier,
    verify: bool = True,
) -> Subscription:
    """Create a new webhook subscription.

    If *verify* is ``True`` the endpoint URL is pinged first to ensure it
    is reachable and responds with a 2xx status code.

    Args:
        org_id: Organization that owns the subscription.
        url: HTTPS endpoint URL for delivery.
        event_types: Event type strings to subscribe to.
        secret: Optional custom signing secret.
        webhook_admin: Protocol for subscription CRUD.
        endpoint_verifier: Protocol to verify endpoint reachability.
        verify: Whether to verify the endpoint before creating.

    Returns:
        The newly created ``Subscription``.

    Raises:
        WebhooksError: If verification fails or Svix rejects the subscription.
    """
    if verify:
        await endpoint_verifier.verify(url)

    return await webhook_admin.create_subscription(org_id, url, event_types, secret)


async def update_subscription(
    org_id: UUID,
    subscription_id: str,
    *,
    webhook_admin: WebhookAdmin,
    url: Optional[str] = None,
    event_types: Optional[list[str]] = None,
    disabled: Optional[bool] = None,
    recover_since: Optional[datetime] = None,
) -> Subscription:
    """Update a webhook subscription.

    When re-enabling a subscription (``disabled=False``) with a
    ``recover_since`` timestamp, a best-effort message recovery is
    triggered for the period the subscription was disabled.

    Returns:
        The updated ``Subscription``.
    """
    subscription = await webhook_admin.update_subscription(
        org_id,
        subscription_id,
        url,
        event_types,
        disabled=disabled,
    )

    # If re-enabling with recovery, trigger best-effort recovery
    if disabled is False and recover_since is not None:
        try:
            await webhook_admin.recover_messages(
                org_id,
                subscription_id,
                since=recover_since,
            )
        except WebhooksError:
            # Recovery is best-effort — subscription update already succeeded
            pass

    return subscription
