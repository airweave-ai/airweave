from typing import Optional, List, Tuple, TypeVar, Callable
import uuid
from functools import wraps

from svix.api import SvixAsync, SvixOptions, ApplicationIn, EndpointIn, MessageIn, EndpointOut, EndpointPatch, MessageListOptions, MessageOut, MessageAttemptOut, MessageAttemptListByEndpointOptions, EndpointSecretOut
from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger

from airweave import schemas
from airweave.webhooks.constants.event_types import EventType, event_type_from_sync_job_status

from airweave.core.shared_models import SyncJobStatus

import jwt, time

T = TypeVar('T')


class WebhooksError:
    """Error class for webhook operations."""
    def __init__(self, message: str):
        self.message = message

# 10 years in seconds
TOKEN_DURATION_SECONDS = 24 * 365 * 10 * 60 * 60

def generate_org_token(signing_secret: str) -> str:
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
    """Decorator that auto-creates the Svix organization if a 'not_found' error occurs.
    
    The decorated method must have 'organisation' as its first argument after self.
    On 'not_found' error, creates the organization in Svix and retries the operation once.
    """
    @wraps(method)
    async def wrapper(self: 'WebhooksService', organisation: schemas.Organization, *args, **kwargs) -> T:
        try:
            return await method(self, organisation, *args, **kwargs)
        except Exception as e:
            if hasattr(e, 'code') and e.code == 'not_found':
                try:
                    await self.create_organization(organisation)
                except Exception as e_org_creation:
                    if hasattr(e_org_creation, 'code') and e_org_creation.code == 'conflict':
                        raise e
                return await method(self, organisation, *args, **kwargs)
            raise
    return wrapper


class WebhooksService:
    """Webhooks service."""

    def __init__(self, logger: Optional[ContextualLogger] = None):
        """Initialize the webhooks service.

        Args:
            logger: Optional contextual logger for structured logging
        """
        token = generate_org_token(settings.SVIX_JWT_SECRET)
        self.logger = logger or default_logger.with_context(component="context_cache")
        self.svix = SvixAsync(token, SvixOptions(server_url=settings.SVIX_URL))

    async def create_organization(self, organisation: schemas.Organization) -> None:
        await self.svix.application.create(ApplicationIn(
            name=organisation.name,
            uid=str(organisation.id)
        ))
    
    async def delete_organization(self, organisation: schemas.Organization) -> None:
        try:
            await self.svix.application.delete(organisation.id)
        except Exception as e:
            self.logger.error(f"Failed to delete organization {organisation.name}: {getattr(e, 'detail', e)}")


    async def create_endpoint(self, organisation: schemas.Organization, url: str, event_types: List[EventType] | None = None, secret: str | None = None) -> Tuple[EndpointOut | None, WebhooksError | None]:
        try:
            endpoint = await self._create_endpoint_internal(organisation, url, event_types, secret)
            return endpoint, None
        except Exception as e:
            self.logger.error(f"Failed to create endpoint: {getattr(e, 'detail', e)}")
            return None, WebhooksError(f"Failed to create endpoint: {getattr(e, 'detail', e)}")

    @auto_create_org_on_not_found
    async def _create_endpoint_internal(self, organisation: schemas.Organization, url: str, event_types: List[EventType] | None = None, secret: str | None = None) -> EndpointOut:
        return await self.svix.endpoint.create(
            organisation.id,
            EndpointIn(
                url=url,
                channels=event_types,
                secret=secret,
            )
        )
    
    async def delete_endpoint(self, organisation: schemas.Organization, endpoint_id: str) -> WebhooksError | None:
        try:
            await self.svix.endpoint.delete(organisation.id, endpoint_id)
            return None
        except Exception as e:
            self.logger.error(f"Failed to delete endpoint {endpoint_id}: {getattr(e, 'detail', e)}")
            return WebhooksError(f"Failed to delete endpoint: {getattr(e, 'detail', e)}")
    
    async def patch_endpoint(self, organisation: schemas.Organization, endpoint_id: str, url: str | None = None, event_types: List[EventType] | None = None) -> Tuple[EndpointOut | None, WebhooksError | None]:
        try:
            endpoint = await self.svix.endpoint.patch(organisation.id, endpoint_id, EndpointPatch(
                url=url,
                channels=event_types,
            ))
            return endpoint, None
        except Exception as e:
            self.logger.error(f"Failed to patch endpoint {endpoint_id}: {getattr(e, 'detail', e)}")
            return None, WebhooksError(f"Failed to patch endpoint: {getattr(e, 'detail', e)}")
    
    async def get_endpoints(self, organisation: schemas.Organization) -> Tuple[List[EndpointOut] | None, WebhooksError | None]:
        try:
            endpoints = await self._get_endpoints_internal(organisation)
            return endpoints, None
        except Exception as e:
            self.logger.error(f"Failed to get endpoints: {getattr(e, 'detail', e)}")
            return None, WebhooksError(f"Failed to get endpoints: {getattr(e, 'detail', e)}")

    @auto_create_org_on_not_found
    async def _get_endpoints_internal(self, organisation: schemas.Organization) -> List[EndpointOut]:
        return (await self.svix.endpoint.list(organisation.id)).data
    
    async def get_endpoint(self, organisation: schemas.Organization, endpoint_id: str) -> Tuple[EndpointOut | None, WebhooksError | None]:
        try:
            endpoint = await self._get_endpoint_internal(organisation, endpoint_id)
            return endpoint, None
        except Exception as e:
            self.logger.error(f"Failed to get endpoint {endpoint_id}: {getattr(e, 'detail', e)}")
            return None, WebhooksError(f"Failed to get endpoint: {getattr(e, 'detail', e)}")

    @auto_create_org_on_not_found
    async def _get_endpoint_internal(self, organisation: schemas.Organization, endpoint_id: str) -> EndpointOut:
        return await self.svix.endpoint.get(organisation.id, endpoint_id)
    
    async def get_endpoint_secret(self, organisation: schemas.Organization, endpoint_id: str) -> Tuple[EndpointSecretOut | None, WebhooksError | None]:
        try:
            secret = await self._get_endpoint_secret_internal(organisation, endpoint_id)
            return secret, None
        except Exception as e:
            self.logger.error(f"Failed to get endpoint secret {endpoint_id}: {getattr(e, 'detail', e)}")
            return None, WebhooksError(f"Failed to get endpoint secret: {getattr(e, 'detail', e)}")

    @auto_create_org_on_not_found
    async def _get_endpoint_secret_internal(self, organisation: schemas.Organization, endpoint_id: str) -> EndpointSecretOut:
        return await self.svix.endpoint.get_secret(str(organisation.id), endpoint_id)

    async def publish_event_sync(self, organisation: schemas.Organization, connection: schemas.Connection, sync_job_status: SyncJobStatus) -> None:
        event_type = event_type_from_sync_job_status(sync_job_status)
        try:
            await self._publish_event_sync_internal(organisation, connection, event_type)
        except Exception as e:
            self.logger.error(f"Failed to publish event: {getattr(e, 'detail', e)}")

    @auto_create_org_on_not_found
    async def _publish_event_sync_internal(self, organisation: schemas.Organization, connection: schemas.Connection, event_type: str) -> None:
        await self.svix.message.create(
            organisation.id,
            MessageIn(
                event_type=event_type,
                channels=[event_type],
                event_id=str(uuid.uuid4()),
                payload={
                    "type": event_type,
                    "collection": connection.id,
                }
            )
        )
    
    async def get_messages(self, organisation: schemas.Organization, event_types: List[str] | None = None) -> Tuple[List[MessageOut] | None, WebhooksError | None]:
        try:
            messages = await self._get_messages_internal(organisation, event_types)
            return messages, None
        except Exception as e:
            self.logger.error(f"Failed to get messages: {getattr(e, 'detail', e)}")
            return None, WebhooksError(f"Failed to get messages: {getattr(e, 'detail', e)}")

    @auto_create_org_on_not_found
    async def _get_messages_internal(self, organisation: schemas.Organization, event_types: List[str] | None = None) -> List[MessageOut]:
        return (await self.svix.message.list(organisation.id, MessageListOptions(
            event_types=event_types,
        ))).data

    async def get_message_attempts_by_endpoint(self, organisation: schemas.Organization, endpoint_id: str, limit: int = 100) -> Tuple[List[MessageAttemptOut] | None, WebhooksError | None]:
        try:
            message_attempts = (await self.svix.message_attempt.list_by_endpoint(organisation.id, endpoint_id, MessageAttemptListByEndpointOptions(
                limit=limit,
            ))).data
            return message_attempts, None
        except Exception as e:
            self.logger.error(f"Failed to get message attempts by endpoint {endpoint_id}: {getattr(e, 'detail', e)}")
            return None, WebhooksError(f"Failed to get message attempts by endpoint: {getattr(e, 'detail', e)}")

service = WebhooksService()