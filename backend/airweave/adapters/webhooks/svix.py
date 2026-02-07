"""Svix adapter for webhooks.

Implements WebhookPublisher and WebhookAdmin protocols.
All Svix SDK types are converted to domain types at the boundary.
WebhookAdmin methods raise WebhooksError on failure.
"""

import logging
import time
import uuid
from datetime import datetime
from functools import wraps
from typing import Callable, Optional, TypeVar

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
from airweave.core.datetime_utils import utc_now_naive
from airweave.domains.webhooks.types import (
    DeliveryAttempt,
    EventMessage,
    RecoveryTask,
    Subscription,
    SyncEventPayload,
    WebhooksError,
    event_type_from_status,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 10 years in seconds
TOKEN_DURATION_SECONDS = 24 * 365 * 10 * 60 * 60


def _generate_token(signing_secret: str) -> str:
    """Generate a JWT token for Svix API authentication."""
    now = int(time.time())
    return jwt.encode(
        {
            "iat": now,
            "exp": now + TOKEN_DURATION_SECONDS,
            "nbf": now,
            "iss": "svix-server",
            "sub": "org_23rb8YdGqMT0qIzpgGwdXfHirMu",
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


class SvixAdapter:
    """Svix adapter implementing WebhookPublisher and WebhookAdmin."""

    def __init__(self) -> None:
        """Initialize Svix adapter with JWT token from settings."""
        token = _generate_token(settings.SVIX_JWT_SECRET)
        self._svix = SvixAsync(token, SvixOptions(server_url=settings.SVIX_URL))

    async def _create_org(self, org_id: uuid.UUID) -> None:
        await self._svix.application.create(ApplicationIn(name=str(org_id), uid=str(org_id)))

    # -------------------------------------------------------------------------
    # WebhookPublisher
    # -------------------------------------------------------------------------

    async def publish_sync_event(
        self,
        org_id: uuid.UUID,
        source_connection_id: uuid.UUID,
        sync_job_id: uuid.UUID,
        sync_id: uuid.UUID,
        collection_id: uuid.UUID,
        collection_name: str,
        collection_readable_id: str,
        source_type: str,
        status: str,
        error: Optional[str] = None,
    ) -> None:
        """Publish a sync lifecycle event."""
        event_type = event_type_from_status(status)
        if event_type is None:
            return

        payload = SyncEventPayload(
            event_type=event_type,
            job_id=sync_job_id,
            collection_readable_id=collection_readable_id,
            collection_name=collection_name,
            source_connection_id=source_connection_id,
            source_type=source_type,
            status=status,
            timestamp=utc_now_naive(),
            error=error,
        )

        try:
            await self._publish_internal(org_id, event_type.value, payload)
        except Exception as e:
            logger.error(f"Failed to publish webhook event: {e}")

    @_auto_create_org
    async def _publish_internal(
        self, org_id: uuid.UUID, event_type: str, payload: SyncEventPayload
    ) -> None:
        await self._svix.message.create(
            str(org_id),
            MessageIn(
                event_type=event_type,
                channels=[event_type],
                event_id=str(uuid.uuid4()),
                payload=payload.to_dict(),
            ),
        )

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
