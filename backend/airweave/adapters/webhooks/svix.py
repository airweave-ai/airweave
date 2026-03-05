"""Svix adapter for webhooks.

Implements WebhookPublisher and WebhookAdmin protocols.
All Svix SDK types are converted to domain types at the boundary.
WebhookAdmin methods raise WebhooksError on failure.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime
from functools import wraps
from typing import TYPE_CHECKING, Callable, Optional, TypeVar

import jwt
from svix.api import (
    ApplicationIn,
    EndpointIn,
    EndpointOut,
    EndpointPatch,
    MessageAttemptListByEndpointOptions,
    MessageAttemptOut,
    MessageIn,
    MessageListOptions,
    MessageOut,
    RecoverIn,
    SvixAsync,
    SvixOptions,
)
from svix.exceptions import HttpError as SvixHttpError
from svix.exceptions import HTTPValidationError as SvixValidationError

from airweave.core.config import settings
from airweave.core.protocols.webhooks import WebhookAdmin, WebhookPublisher
from airweave.domains.webhooks.types import (
    DeliveryAttempt,
    EventMessage,
    RecoveryTask,
    Subscription,
    WebhookPublishError,
    WebhooksError,
)

if TYPE_CHECKING:
    from airweave.core.protocols.event_bus import DomainEvent

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 10 years in seconds
TOKEN_DURATION_SECONDS = 24 * 365 * 10 * 60 * 60

# Default org identifier for self-hosted Svix JWT auth
SVIX_ORG_ID = "org_23rb8YdGqMT0qIzpgGwdXfHirMu"


def _generate_token(signing_secret: str) -> str:
    """Generate a JWT token for Svix API authentication."""
    now = int(time.time())
    return jwt.encode(
        {
            "iat": now,
            "exp": now + TOKEN_DURATION_SECONDS,
            "nbf": now,
            "iss": "svix-server",
            "sub": SVIX_ORG_ID,
        },
        signing_secret,
        algorithm="HS256",
    )


def _raise_from_exception(e: Exception, context: str = "") -> None:
    """Convert any exception to WebhooksError and raise it."""
    prefix = f"{context}: " if context else ""
    if isinstance(e, SvixHttpError):
        if e.code == "not_found":
            raise WebhooksError(f"{prefix}{e.detail}", 404) from e
        elif e.code in ("validation", "validation_error"):
            raise WebhooksError(f"{prefix}{e.detail}", 422) from e
        raise WebhooksError(f"{prefix}{e.detail}", e.status_code or 500) from e
    if isinstance(e, SvixValidationError):
        messages = [err.msg for err in e.detail] if e.detail else ["Validation error"]
        raise WebhooksError(f"{prefix}{'; '.join(messages)}", 422) from e
    raise WebhooksError(f"{prefix}{str(e)}", 500) from e


def _is_transient_error(exc: Exception) -> bool:
    """Check if an exception is a transient error worth retrying.

    Returns True for connection errors and Svix 5xx responses.
    Returns False for validation errors and other non-recoverable failures.
    """
    if isinstance(exc, (ConnectionError, OSError, TimeoutError)):
        return True
    if isinstance(exc, SvixHttpError):
        return exc.status_code is not None and exc.status_code >= 500
    return False


def _auto_create_org(method: Callable[..., T]) -> Callable[..., T]:
    """Decorator to auto-create Svix org if not found."""

    @wraps(method)
    async def wrapper(self: "SvixAdapter", org_id: uuid.UUID, *args, **kwargs) -> T:
        try:
            return await method(self, org_id, *args, **kwargs)
        except Exception as e:
            if hasattr(e, "code") and e.code == "not_found":
                try:
                    await self._create_org(org_id)
                except Exception as e2:
                    if not (hasattr(e2, "code") and e2.code == "conflict"):
                        raise e
                return await method(self, org_id, *args, **kwargs)
            raise

    return wrapper


# ---------------------------------------------------------------------------
# Type converters: Svix SDK → Domain types
# ---------------------------------------------------------------------------


def _to_subscription(endpoint: EndpointOut) -> Subscription:
    return Subscription(
        id=endpoint.id,
        url=endpoint.url,
        event_types=endpoint.channels or [],
        disabled=endpoint.disabled,
        created_at=endpoint.created_at,
        updated_at=endpoint.updated_at,
    )


def _to_message(msg: MessageOut) -> EventMessage:
    return EventMessage(
        id=msg.id,
        event_type=msg.event_type,
        payload=msg.payload,
        timestamp=msg.timestamp,
        channels=msg.channels or [],
    )


def _to_attempt(attempt: MessageAttemptOut) -> DeliveryAttempt:
    return DeliveryAttempt(
        id=attempt.id,
        message_id=attempt.msg_id,
        endpoint_id=attempt.endpoint_id,
        timestamp=attempt.timestamp,
        response_status_code=attempt.response_status_code,
        response=attempt.response,
        url=attempt.url,
    )


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class SvixAdapter(WebhookPublisher, WebhookAdmin):
    """Svix adapter implementing WebhookPublisher and WebhookAdmin."""

    def __init__(self) -> None:
        """Initialize Svix adapter with JWT token from settings."""
        token = _generate_token(settings.SVIX_JWT_SECRET)
        self._svix = SvixAsync(token, SvixOptions(server_url=settings.SVIX_URL))

    async def _create_org(self, org_id: uuid.UUID) -> None:
        await self._svix.application.create(ApplicationIn(name=str(org_id), uid=str(org_id)))

    # -------------------------------------------------------------------------
    # Organization lifecycle
    # -------------------------------------------------------------------------

    async def delete_organization(self, org_id: uuid.UUID) -> None:
        """Delete a Svix application (organization) and all its data.

        Best-effort: logs errors rather than raising.
        """
        try:
            await self._svix.application.delete(str(org_id))
        except Exception as e:
            logger.error(f"Failed to delete Svix application for org {org_id}: {e}")

    # -------------------------------------------------------------------------
    # WebhookPublisher
    # -------------------------------------------------------------------------

    async def publish_event(self, event: "DomainEvent") -> None:
        """Publish a domain event to webhook subscribers.

        Serializes the event to a flat JSON dict for Svix delivery.
        Retries up to 3 times on transient errors (connection failures,
        Svix 5xx) with exponential backoff (0s, 1s, 2s).
        Wraps infrastructure errors in WebhookPublishError so the event
        bus sees a domain exception, never raw Svix/HTTP internals.
        """
        event_type = event.event_type.value
        payload = event.model_dump(mode="json")

        max_retries = 3
        retry_delays = [0, 1, 2]

        for attempt in range(max_retries):
            try:
                await self._publish_internal(event.organization_id, event_type, payload)
                logger.info(
                    f"Published webhook event '{event_type}' for org {event.organization_id}"
                )
                return
            except Exception as exc:
                is_last_attempt = attempt == max_retries - 1
                if not _is_transient_error(exc) or is_last_attempt:
                    raise WebhookPublishError(event_type, exc) from exc
                delay = retry_delays[attempt]
                logger.warning(
                    f"Transient Svix error publishing '{event_type}' "
                    f"(attempt {attempt + 1}/{max_retries}), retrying in {delay}s: {exc}"
                )
                if delay > 0:
                    await asyncio.sleep(delay)

    @_auto_create_org
    async def _publish_internal(self, org_id: uuid.UUID, event_type: str, payload: dict) -> None:
        event_id = str(uuid.uuid4())
        print(
            f"[SVIX PRE-CREATE] event_type={event_type} org_id={org_id} "
            f"event_id={event_id} svix_url={settings.SVIX_URL}"
        )
        try:
            result = await self._svix.message.create(
                str(org_id),
                MessageIn(
                    event_type=event_type,
                    channels=[event_type],
                    event_id=event_id,
                    payload=payload,
                ),
            )
            print(
                f"[SVIX POST-CREATE] msg_id={result.id} event_type={event_type} "
                f"org_id={org_id} channels={result.channels}"
            )
        except Exception as exc:
            print(
                f"[SVIX CREATE FAILED] event_type={event_type} org_id={org_id} "
                f"event_id={event_id} error={exc!r}"
            )
            raise

        # Verify the message is queryable immediately
        try:
            msgs = await self._svix.message.list(
                str(org_id), MessageListOptions(event_types=[event_type])
            )
            found = any(m.id == result.id for m in msgs.data)
            print(
                f"[SVIX VERIFY] msg_id={result.id} found_in_list={found} "
                f"total_msgs={len(msgs.data)} event_type={event_type}"
            )
        except Exception as exc:
            print(f"[SVIX VERIFY FAILED] {exc!r}")

    # -------------------------------------------------------------------------
    # WebhookAdmin - Subscriptions
    # -------------------------------------------------------------------------

    async def list_subscriptions(self, org_id: uuid.UUID) -> list[Subscription]:
        """List all subscriptions for an organization."""
        try:
            endpoints = await self._list_endpoints_internal(org_id)
            return [_to_subscription(ep) for ep in endpoints]
        except WebhooksError:
            raise
        except Exception as e:
            _raise_from_exception(e, "Failed to list subscriptions")

    @_auto_create_org
    async def _list_endpoints_internal(self, org_id: uuid.UUID) -> list[EndpointOut]:
        return (await self._svix.endpoint.list(str(org_id))).data

    async def get_subscription(self, org_id: uuid.UUID, subscription_id: str) -> Subscription:
        """Get a specific subscription."""
        try:
            endpoint = await self._get_endpoint_internal(org_id, subscription_id)
            return _to_subscription(endpoint)
        except WebhooksError:
            raise
        except Exception as e:
            _raise_from_exception(e, "Failed to get subscription")

    @_auto_create_org
    async def _get_endpoint_internal(self, org_id: uuid.UUID, endpoint_id: str) -> EndpointOut:
        return await self._svix.endpoint.get(str(org_id), endpoint_id)

    async def create_subscription(
        self,
        org_id: uuid.UUID,
        url: str,
        event_types: list[str],
        secret: Optional[str] = None,
    ) -> Subscription:
        """Create a new subscription."""
        try:
            endpoint = await self._create_endpoint_internal(org_id, url, event_types, secret)
            return _to_subscription(endpoint)
        except WebhooksError:
            raise
        except Exception as e:
            _raise_from_exception(e, "Failed to create subscription")

    @_auto_create_org
    async def _create_endpoint_internal(
        self, org_id: uuid.UUID, url: str, event_types: list[str], secret: Optional[str]
    ) -> EndpointOut:
        return await self._svix.endpoint.create(
            str(org_id),
            EndpointIn(url=url, channels=event_types, secret=secret, uid=str(uuid.uuid4())),
        )

    async def update_subscription(
        self,
        org_id: uuid.UUID,
        subscription_id: str,
        url: Optional[str] = None,
        event_types: Optional[list[str]] = None,
        disabled: Optional[bool] = None,
    ) -> Subscription:
        """Update a subscription."""
        try:
            patch_data = {}
            if url is not None:
                patch_data["url"] = url
            if event_types is not None:
                patch_data["channels"] = event_types
            if disabled is not None:
                patch_data["disabled"] = disabled

            endpoint = await self._svix.endpoint.patch(
                str(org_id), subscription_id, EndpointPatch(**patch_data)
            )
            return _to_subscription(endpoint)
        except WebhooksError:
            raise
        except Exception as e:
            _raise_from_exception(e, "Failed to update subscription")

    async def delete_subscription(self, org_id: uuid.UUID, subscription_id: str) -> None:
        """Delete a subscription."""
        try:
            await self._svix.endpoint.delete(str(org_id), subscription_id)
        except WebhooksError:
            raise
        except Exception as e:
            _raise_from_exception(e, "Failed to delete subscription")

    async def get_subscription_secret(self, org_id: uuid.UUID, subscription_id: str) -> str:
        """Get the signing secret for a subscription."""
        try:
            secret = await self._get_secret_internal(org_id, subscription_id)
            return secret.key
        except WebhooksError:
            raise
        except Exception as e:
            _raise_from_exception(e, "Failed to get subscription secret")

    @_auto_create_org
    async def _get_secret_internal(self, org_id: uuid.UUID, endpoint_id: str):
        return await self._svix.endpoint.get_secret(str(org_id), endpoint_id)

    async def recover_messages(
        self,
        org_id: uuid.UUID,
        subscription_id: str,
        since: datetime,
        until: Optional[datetime] = None,
    ) -> RecoveryTask:
        """Recover failed messages for a subscription."""
        try:
            result = await self._svix.endpoint.recover(
                str(org_id), subscription_id, RecoverIn(since=since, until=until)
            )
            status_map = {0: "running", 1: "completed"}
            return RecoveryTask(id=result.id, status=status_map.get(result.status, "unknown"))
        except WebhooksError:
            raise
        except Exception as e:
            _raise_from_exception(e, "Failed to recover messages")

    # -------------------------------------------------------------------------
    # WebhookAdmin - Message History
    # -------------------------------------------------------------------------

    async def get_messages(
        self, org_id: uuid.UUID, event_types: Optional[list[str]] = None
    ) -> list[EventMessage]:
        """Get event messages for an organization."""
        try:
            messages = await self._get_messages_internal(org_id, event_types)
            return [_to_message(m) for m in messages]
        except WebhooksError:
            raise
        except Exception as e:
            _raise_from_exception(e, "Failed to get messages")

    @_auto_create_org
    async def _get_messages_internal(
        self, org_id: uuid.UUID, event_types: Optional[list[str]]
    ) -> list[MessageOut]:
        return (
            await self._svix.message.list(str(org_id), MessageListOptions(event_types=event_types))
        ).data

    async def get_message(self, org_id: uuid.UUID, message_id: str) -> EventMessage:
        """Get a specific message."""
        try:
            msg = await self._get_message_internal(org_id, message_id)
            return _to_message(msg)
        except WebhooksError:
            raise
        except Exception as e:
            _raise_from_exception(e, "Failed to get message")

    @_auto_create_org
    async def _get_message_internal(self, org_id: uuid.UUID, message_id: str) -> MessageOut:
        return await self._svix.message.get(str(org_id), message_id)

    async def get_message_attempts(
        self, org_id: uuid.UUID, message_id: str
    ) -> list[DeliveryAttempt]:
        """Get delivery attempts for a message."""
        try:
            attempts = (await self._svix.message_attempt.list_by_msg(str(org_id), message_id)).data
            return [_to_attempt(a) for a in attempts]
        except WebhooksError:
            raise
        except Exception as e:
            _raise_from_exception(e, "Failed to get message attempts")

    async def get_subscription_attempts(
        self, org_id: uuid.UUID, subscription_id: str, limit: int = 100
    ) -> list[DeliveryAttempt]:
        """Get delivery attempts for a subscription."""
        try:
            attempts = (
                await self._svix.message_attempt.list_by_endpoint(
                    str(org_id), subscription_id, MessageAttemptListByEndpointOptions(limit=limit)
                )
            ).data
            return [_to_attempt(a) for a in attempts]
        except WebhooksError:
            raise
        except Exception as e:
            _raise_from_exception(e, "Failed to get subscription attempts")
