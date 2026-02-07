"""Webhooks service for managing Svix-based webhook subscriptions.

This module provides a service class for interacting with the Svix webhook
platform, including creating subscriptions, publishing events, and managing
message delivery.
"""

import time
import uuid
from datetime import datetime
from functools import wraps
from typing import Callable, List, Optional, Tuple, TypeVar

import jwt
from svix.api import (
    ApplicationIn,
    EndpointIn,
    EndpointOut,
    EndpointPatch,
    EndpointSecretOut,
    MessageAttemptListByEndpointOptions,
    MessageAttemptOut,
    MessageIn,
    MessageListOptions,
    MessageOut,
    MessageStatus,
    RecoverIn,
    RecoverOut,
    SvixAsync,
    SvixOptions,
)
from svix.exceptions import HttpError as SvixHttpError
from svix.exceptions import HTTPValidationError as SvixValidationError

from airweave import schemas
from airweave.core.config import settings
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.webhooks.constants.event_types import EventType, event_type_from_sync_job_status
from airweave.webhooks.schemas import SyncEventPayload

T = TypeVar("T")


class WebhooksError:
    """Error class for webhook operations with HTTP status code mapping."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        """Initialize the error with a message and HTTP status code.

        Args:
            message: The error message.
            status_code: The HTTP status code (404, 422, 500, etc.).
        """
        self.message = message
        self.status_code = status_code

    @classmethod
    def from_svix_error(cls, e: SvixHttpError, context: str = "") -> "WebhooksError":
        """Create a WebhooksError from a Svix HttpError.

        Maps Svix error codes to appropriate HTTP status codes:
        - not_found -> 404
        - validation/validation_error -> 422
        - other -> 500

        Args:
            e: The Svix HttpError.
            context: Optional context string for the error message.

        Returns:
            WebhooksError with appropriate status code.
        """
        prefix = f"{context}: " if context else ""
        message = f"{prefix}{e.detail}"

        # Map Svix error codes to HTTP status codes
        if e.code == "not_found":
            return cls(message, 404)
        elif e.code in ("validation", "validation_error"):
            return cls(message, 422)
        else:
            # Use Svix's status_code if available, otherwise 500
            return cls(message, e.status_code if e.status_code else 500)

    @classmethod
    def from_validation_error(cls, e: SvixValidationError, context: str = "") -> "WebhooksError":
        """Create a WebhooksError from a Svix HTTPValidationError.

        Args:
            e: The Svix HTTPValidationError.
            context: Optional context string for the error message.

        Returns:
            WebhooksError with 422 status code.
        """
        prefix = f"{context}: " if context else ""
        # Extract message from validation error details
        messages = [err.msg for err in e.detail] if e.detail else ["Validation error"]
        return cls(f"{prefix}{'; '.join(messages)}", 422)

    @classmethod
    def from_exception(cls, e: Exception, context: str = "") -> "WebhooksError":
        """Create a WebhooksError from any exception.

        Args:
            e: The exception.
            context: Optional context string for the error message.

        Returns:
            WebhooksError with appropriate status code.
        """
        if isinstance(e, SvixHttpError):
            return cls.from_svix_error(e, context)
        if isinstance(e, SvixValidationError):
            return cls.from_validation_error(e, context)
        prefix = f"{context}: " if context else ""
        return cls(f"{prefix}{str(e)}", 500)


# 10 years in seconds
TOKEN_DURATION_SECONDS = 24 * 365 * 10 * 60 * 60


def generate_org_token(signing_secret: str) -> str:
    """Generate a JWT token for Svix API authentication.

    Args:
        signing_secret: The secret used to sign the JWT.

    Returns:
        A signed JWT token string.
    """
    now = int(time.time())
    exp = now + TOKEN_DURATION_SECONDS

    payload = {
        "iat": now,
        "exp": exp,
        "nbf": now,
        "iss": "svix-server",
        "sub": "org_23rb8YdGqMT0qIzpgGwdXfHirMu",
    }

    token = jwt.encode(payload, signing_secret, algorithm="HS256")
    return token


def auto_create_org_on_not_found(method: Callable[..., T]) -> Callable[..., T]:
    """Decorate methods to auto-create Svix organization if not found.

    The decorated method must have 'organisation' as its first argument after self.
    On 'not_found' error, creates the organization in Svix and retries the operation once.

    Args:
        method: The method to decorate.

    Returns:
        The decorated method.
    """

    @wraps(method)
    async def wrapper(
        self: "WebhooksService", organisation: schemas.Organization, *args, **kwargs
    ) -> T:
        try:
            return await method(self, organisation, *args, **kwargs)
        except Exception as e:
            if hasattr(e, "code") and e.code == "not_found":
                try:
                    await self.create_organization(organisation)
                except Exception as e_org_creation:
                    if hasattr(e_org_creation, "code") and e_org_creation.code == "conflict":
                        raise e
                return await method(self, organisation, *args, **kwargs)
            raise

    return wrapper


class WebhooksService:
    """Service for managing webhooks via Svix."""

    def __init__(self, logger: Optional[ContextualLogger] = None) -> None:
        """Initialize the webhooks service.

        Args:
            logger: Optional contextual logger for structured logging.
        """
        token = generate_org_token(settings.SVIX_JWT_SECRET)
        self.logger = logger or default_logger.with_context(component="webhooks")
        self.svix = SvixAsync(token, SvixOptions(server_url=settings.SVIX_URL))

    async def create_organization(self, organisation: schemas.Organization) -> None:
        """Create an organization in Svix.

        Args:
            organisation: The organization to create.
        """
        await self.svix.application.create(
            ApplicationIn(name=organisation.name, uid=str(organisation.id))
        )

    async def delete_organization(self, organisation: schemas.Organization) -> None:
        """Delete an organization from Svix.

        Args:
            organisation: The organization to delete.
        """
        try:
            await self.svix.application.delete(organisation.id)
        except Exception as e:
            self.logger.error(
                f"Failed to delete organization {organisation.name}: {getattr(e, 'detail', e)}"
            )

    async def create_endpoint(
        self,
        organisation: schemas.Organization,
        url: str,
        event_types: List[EventType] | None = None,
        secret: str | None = None,
    ) -> Tuple[EndpointOut | None, WebhooksError | None]:
        """Create a webhook endpoint (subscription).

        Args:
            organisation: The organization to create the endpoint for.
            url: The webhook URL to receive events.
            event_types: Optional list of event types to subscribe to.
            secret: Optional signing secret for the webhook.

        Returns:
            Tuple of (endpoint, error).
        """
        try:
            endpoint = await self._create_endpoint_internal(organisation, url, event_types, secret)
            return endpoint, None
        except Exception as e:
            self.logger.error(f"Failed to create endpoint: {getattr(e, 'detail', e)}")
            return None, WebhooksError.from_exception(e, "Failed to create endpoint")

    @auto_create_org_on_not_found
    async def _create_endpoint_internal(
        self,
        organisation: schemas.Organization,
        url: str,
        event_types: List[EventType] | None = None,
        secret: str | None = None,
    ) -> EndpointOut:
        return await self.svix.endpoint.create(
            organisation.id,
            EndpointIn(
                url=url,
                channels=event_types,
                secret=secret,
                uid=str(uuid.uuid4()),  # Our UUID for bidirectional mapping
            ),
        )

    async def delete_endpoint(
        self, organisation: schemas.Organization, endpoint_id: str
    ) -> WebhooksError | None:
        """Delete a webhook endpoint.

        Args:
            organisation: The organization owning the endpoint.
            endpoint_id: The ID of the endpoint to delete.

        Returns:
            Error if the operation failed, None otherwise.
        """
        try:
            await self.svix.endpoint.delete(organisation.id, endpoint_id)
            return None
        except Exception as e:
            self.logger.error(f"Failed to delete endpoint {endpoint_id}: {getattr(e, 'detail', e)}")
            return WebhooksError.from_exception(e, "Failed to delete endpoint")

    async def patch_endpoint(
        self,
        organisation: schemas.Organization,
        endpoint_id: str,
        url: str | None = None,
        event_types: List[EventType] | None = None,
        disabled: bool | None = None,
    ) -> Tuple[EndpointOut | None, WebhooksError | None]:
        """Update a webhook endpoint.

        Args:
            organisation: The organization owning the endpoint.
            endpoint_id: The ID of the endpoint to update.
            url: Optional new URL for the webhook.
            event_types: Optional new list of event types.
            disabled: Optional flag to enable/disable the endpoint.

        Returns:
            Tuple of (endpoint, error).
        """
        try:
            # Only include fields that are explicitly set (not None)
            # to avoid Svix validation errors for null values
            patch_data = {}
            if url is not None:
                patch_data["url"] = url
            if event_types is not None:
                patch_data["channels"] = event_types
            if disabled is not None:
                patch_data["disabled"] = disabled

            endpoint = await self.svix.endpoint.patch(
                organisation.id,
                endpoint_id,
                EndpointPatch(**patch_data),
            )
            return endpoint, None
        except Exception as e:
            self.logger.error(f"Failed to patch endpoint {endpoint_id}: {getattr(e, 'detail', e)}")
            return None, WebhooksError.from_exception(e, "Failed to patch endpoint")

    async def get_endpoints(
        self, organisation: schemas.Organization
    ) -> Tuple[List[EndpointOut] | None, WebhooksError | None]:
        """Get all webhook endpoints for an organization.

        Args:
            organisation: The organization to get endpoints for.

        Returns:
            Tuple of (endpoints, error).
        """
        try:
            endpoints = await self._get_endpoints_internal(organisation)
            return endpoints, None
        except Exception as e:
            self.logger.error(f"Failed to get endpoints: {getattr(e, 'detail', e)}")
            return None, WebhooksError.from_exception(e, "Failed to get endpoints")

    @auto_create_org_on_not_found
    async def _get_endpoints_internal(
        self, organisation: schemas.Organization
    ) -> List[EndpointOut]:
        return (await self.svix.endpoint.list(organisation.id)).data

    async def get_endpoint(
        self, organisation: schemas.Organization, endpoint_id: str
    ) -> Tuple[EndpointOut | None, WebhooksError | None]:
        """Get a specific webhook endpoint.

        Args:
            organisation: The organization owning the endpoint.
            endpoint_id: The ID of the endpoint to get.

        Returns:
            Tuple of (endpoint, error).
        """
        try:
            endpoint = await self._get_endpoint_internal(organisation, endpoint_id)
            return endpoint, None
        except Exception as e:
            self.logger.error(f"Failed to get endpoint {endpoint_id}: {getattr(e, 'detail', e)}")
            return None, WebhooksError.from_exception(e, "Failed to get endpoint")

    @auto_create_org_on_not_found
    async def _get_endpoint_internal(
        self, organisation: schemas.Organization, endpoint_id: str
    ) -> EndpointOut:
        return await self.svix.endpoint.get(organisation.id, endpoint_id)

    async def get_endpoint_secret(
        self, organisation: schemas.Organization, endpoint_id: str
    ) -> Tuple[EndpointSecretOut | None, WebhooksError | None]:
        """Get the signing secret for a webhook endpoint.

        Args:
            organisation: The organization owning the endpoint.
            endpoint_id: The ID of the endpoint.

        Returns:
            Tuple of (secret, error).
        """
        try:
            secret = await self._get_endpoint_secret_internal(organisation, endpoint_id)
            return secret, None
        except Exception as e:
            self.logger.error(
                f"Failed to get endpoint secret {endpoint_id}: {getattr(e, 'detail', e)}"
            )
            return None, WebhooksError.from_exception(e, "Failed to get endpoint secret")

    @auto_create_org_on_not_found
    async def _get_endpoint_secret_internal(
        self, organisation: schemas.Organization, endpoint_id: str
    ) -> EndpointSecretOut:
        return await self.svix.endpoint.get_secret(str(organisation.id), endpoint_id)

    async def recover_failed_messages(
        self,
        organisation: schemas.Organization,
        endpoint_id: str,
        since: datetime,
        until: datetime | None = None,
    ) -> Tuple[RecoverOut | None, WebhooksError | None]:
        """Recover (retry) all failed messages for an endpoint since a given time.

        This is useful after re-enabling a disabled endpoint to retry all the
        messages that failed while it was disabled.

        Args:
            organisation: The organization owning the endpoint.
            endpoint_id: The ID of the endpoint.
            since: Recover messages that failed after this time.
            until: Optional upper bound for message recovery.

        Returns:
            Tuple of (recovery task info, error).
        """
        try:
            result = await self.svix.endpoint.recover(
                str(organisation.id),
                endpoint_id,
                RecoverIn(
                    since=since,
                    until=until,
                ),
            )
            return result, None
        except Exception as e:
            self.logger.error(
                f"Failed to recover messages for endpoint {endpoint_id}: {getattr(e, 'detail', e)}"
            )
            return None, WebhooksError.from_exception(e, "Failed to recover failed messages")

    async def publish_event_sync(
        self,
        source_connection_id: uuid.UUID,
        organisation: schemas.Organization,
        sync_job: schemas.SyncJob,
        collection: schemas.Collection,
        source_type: str,
        error: Optional[str] = None,
    ) -> None:
        """Publish a sync event to all subscribed webhooks.

        Args:
            source_connection_id: The source connection ID.
            organisation: The organization to publish the event for.
            sync_job: The sync job (contains status, id, metrics).
            collection: The collection being synced to.
            source_type: Short name of the source (e.g., 'slack', 'notion').
            error: Optional error message for failed syncs.
        """
        event_type = event_type_from_sync_job_status(sync_job.status)
        if event_type is None:
            # No webhook for this status (e.g., CREATED, CANCELLING)
            return

        # Build the event payload
        payload = SyncEventPayload(
            event_type=event_type,
            job_id=sync_job.id,
            collection_readable_id=collection.readable_id,
            collection_name=collection.name,
            source_connection_id=source_connection_id,
            source_type=source_type,
            status=sync_job.status,
            timestamp=utc_now_naive(),
            error=error or sync_job.error,
        )

        try:
            await self._publish_event_sync_internal(organisation, event_type, payload)
        except Exception as e:
            self.logger.error(f"Failed to publish event: {getattr(e, 'detail', e)}")

    @auto_create_org_on_not_found
    async def _publish_event_sync_internal(
        self,
        organisation: schemas.Organization,
        event_type: str,
        payload: SyncEventPayload,
    ) -> None:
        await self.svix.message.create(
            organisation.id,
            MessageIn(
                event_type=event_type,
                channels=[event_type],
                event_id=str(uuid.uuid4()),
                payload=payload.model_dump(mode="json"),
            ),
        )

    async def get_messages(
        self, organisation: schemas.Organization, event_types: List[str] | None = None
    ) -> Tuple[List[MessageOut] | None, WebhooksError | None]:
        """Get event messages for an organization.

        Args:
            organisation: The organization to get messages for.
            event_types: Optional list of event types to filter by.

        Returns:
            Tuple of (messages, error).
        """
        try:
            messages = await self._get_messages_internal(organisation, event_types)
            return messages, None
        except Exception as e:
            self.logger.error(f"Failed to get messages: {getattr(e, 'detail', e)}")
            return None, WebhooksError.from_exception(e, "Failed to get messages")

    async def get_message(
        self, organisation: schemas.Organization, message_id: str
    ) -> Tuple[MessageOut | None, WebhooksError | None]:
        """Get a specific message by ID.

        Args:
            organisation: The organization owning the message.
            message_id: The ID of the message to retrieve.

        Returns:
            Tuple of (message, error).
        """
        try:
            message = await self._get_message_internal(organisation, message_id)
            return message, None
        except Exception as e:
            self.logger.error(f"Failed to get message {message_id}: {getattr(e, 'detail', e)}")
            return None, WebhooksError.from_exception(e, "Failed to get message")

    @auto_create_org_on_not_found
    async def _get_message_internal(
        self, organisation: schemas.Organization, message_id: str
    ) -> MessageOut:
        return await self.svix.message.get(str(organisation.id), message_id)

    @auto_create_org_on_not_found
    async def _get_messages_internal(
        self, organisation: schemas.Organization, event_types: List[str] | None = None
    ) -> List[MessageOut]:
        return (
            await self.svix.message.list(
                organisation.id,
                MessageListOptions(
                    event_types=event_types,
                ),
            )
        ).data

    async def get_message_attempts_by_message(
        self, organisation: schemas.Organization, message_id: str
    ) -> Tuple[List[MessageAttemptOut] | None, WebhooksError | None]:
        """Get delivery attempts for a specific message.

        Args:
            organisation: The organization owning the message.
            message_id: The ID of the message.

        Returns:
            Tuple of (attempts, error).
        """
        try:
            attempts = (
                await self.svix.message_attempt.list_by_msg(str(organisation.id), message_id)
            ).data
            return attempts, None
        except Exception as e:
            self.logger.error(
                f"Failed to get message attempts for {message_id}: {getattr(e, 'detail', e)}"
            )
            return None, WebhooksError.from_exception(e, "Failed to get message attempts")

    async def get_message_attempts_by_endpoint(
        self,
        organisation: schemas.Organization,
        endpoint_id: str,
        limit: int = 100,
        status: MessageStatus | None = None,
    ) -> Tuple[List[MessageAttemptOut] | None, WebhooksError | None]:
        """Get message delivery attempts for a webhook endpoint.

        Args:
            organisation: The organization owning the endpoint.
            endpoint_id: The ID of the endpoint.
            limit: Maximum number of attempts to return.
            status: Optional status filter (MessageStatus.Success, MessageStatus.Fail, etc.).

        Returns:
            Tuple of (attempts, error).
        """
        try:
            message_attempts = (
                await self.svix.message_attempt.list_by_endpoint(
                    organisation.id,
                    endpoint_id,
                    MessageAttemptListByEndpointOptions(
                        limit=limit,
                        status=status,
                    ),
                )
            ).data
            return message_attempts, None
        except Exception as e:
            self.logger.error(
                f"Failed to get message attempts for {endpoint_id}: {getattr(e, 'detail', e)}"
            )
            return None, WebhooksError.from_exception(
                e, "Failed to get message attempts by endpoint"
            )

    async def get_all_message_attempts(
        self,
        organisation: schemas.Organization,
        status: str | None = None,
        limit: int = 100,
    ) -> Tuple[List[MessageAttemptOut] | None, WebhooksError | None]:
        """Get all message delivery attempts across all endpoints for an organization.

        Args:
            organisation: The organization to get attempts for.
            status: Optional status filter ("succeeded" or "failed").
            limit: Maximum number of attempts to return per endpoint.

        Returns:
            Tuple of (attempts, error).
        """
        try:
            # First get all endpoints
            endpoints, error = await self.get_endpoints(organisation)
            if error:
                return None, error

            if not endpoints:
                return [], None

            # Convert string status to Svix MessageStatus enum for API-level filtering
            svix_status: MessageStatus | None = None
            if status == "succeeded":
                svix_status = MessageStatus.SUCCESS
            elif status == "failed":
                svix_status = MessageStatus.FAIL

            # Aggregate attempts from all endpoints (filtered at Svix API level)
            all_attempts: List[MessageAttemptOut] = []
            for endpoint in endpoints:
                attempts, err = await self.get_message_attempts_by_endpoint(
                    organisation, endpoint.id, limit=limit, status=svix_status
                )
                if attempts:
                    all_attempts.extend(attempts)

            # Sort by timestamp descending
            all_attempts.sort(key=lambda a: a.timestamp, reverse=True)

            return all_attempts, None
        except Exception as e:
            self.logger.error(f"Failed to get all message attempts: {getattr(e, 'detail', e)}")
            return None, WebhooksError.from_exception(e, "Failed to get all message attempts")


service = WebhooksService()
