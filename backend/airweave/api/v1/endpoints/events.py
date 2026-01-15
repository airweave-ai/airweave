"""Events API endpoints for webhook subscriptions and event messages.

This module provides endpoints for managing webhook subscriptions and
retrieving event messages sent to those webhooks.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from svix.api import EndpointOut, EndpointSecretOut, MessageAttemptOut, MessageOut

from airweave.analytics import business_events
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.webhooks.constants.event_types import EventType
from airweave.webhooks.service import service

router = APIRouter()


class SubscriptionWithAttemptsOut(BaseModel):
    """Response model for a subscription with its message attempts."""

    endpoint: EndpointOut
    message_attempts: List[MessageAttemptOut]

    class Config:
        """Pydantic config for arbitrary types."""

        arbitrary_types_allowed = True


class CreateSubscriptionRequest(BaseModel):
    """Request model for creating a new webhook subscription."""

    url: HttpUrl
    event_types: List[EventType]
    secret: str | None = None


class PatchSubscriptionRequest(BaseModel):
    """Request model for updating an existing webhook subscription."""

    url: HttpUrl | None = None
    event_types: List[EventType] | None = None


@router.get("/messages", response_model=List[MessageOut])
async def get_messages(
    ctx: ApiContext = Depends(deps.get_context),
    event_types: List[str] | None = Query(default=None),
) -> List[MessageOut]:
    """Get event messages for the current organization.

    Args:
        ctx: The API context containing organization info.
        event_types: Optional list of event types to filter by.

    Returns:
        List of event messages.
    """
    messages, error = await service.get_messages(ctx.organization, event_types=event_types)
    if error:
        raise HTTPException(status_code=500, detail=error.message)
    return messages


@router.get("/messages/{message_id}", response_model=MessageOut)
async def get_message(
    message_id: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> MessageOut:
    """Get a specific event message by ID.

    Args:
        message_id: The ID of the message to retrieve.
        ctx: The API context containing organization info.

    Returns:
        The event message with its payload.
    """
    message, error = await service.get_message(ctx.organization, message_id)
    if error:
        raise HTTPException(status_code=500, detail=error.message)
    return message


@router.get("/messages/{message_id}/attempts", response_model=List[MessageAttemptOut])
async def get_message_attempts(
    message_id: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> List[MessageAttemptOut]:
    """Get delivery attempts for a specific message.

    Args:
        message_id: The ID of the message.
        ctx: The API context containing organization info.

    Returns:
        List of delivery attempts for this message.
    """
    attempts, error = await service.get_message_attempts_by_message(ctx.organization, message_id)
    if error:
        raise HTTPException(status_code=500, detail=error.message)
    return attempts or []


@router.get("/subscriptions", response_model=List[EndpointOut])
async def get_subscriptions(
    ctx: ApiContext = Depends(deps.get_context),
) -> List[EndpointOut]:
    """Get all webhook subscriptions for the current organization.

    Args:
        ctx: The API context containing organization info.

    Returns:
        List of webhook subscriptions.
    """
    endpoints, error = await service.get_endpoints(ctx.organization)
    if error:
        raise HTTPException(status_code=500, detail=error.message)
    return endpoints


@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionWithAttemptsOut)
async def get_subscription(
    subscription_id: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> SubscriptionWithAttemptsOut:
    """Get a specific webhook subscription with its delivery attempts.

    Args:
        subscription_id: The ID of the subscription to retrieve.
        ctx: The API context containing organization info.

    Returns:
        The subscription details with message delivery attempts.
    """
    endpoint, error = await service.get_endpoint(ctx.organization, subscription_id)
    if error:
        raise HTTPException(status_code=500, detail=error.message)

    message_attempts, attempts_error = await service.get_message_attempts_by_endpoint(
        ctx.organization, subscription_id
    )
    if attempts_error:
        raise HTTPException(status_code=500, detail=attempts_error.message)

    return SubscriptionWithAttemptsOut(endpoint=endpoint, message_attempts=message_attempts or [])


@router.post("/subscriptions", response_model=EndpointOut)
async def create_subscription(
    request: CreateSubscriptionRequest,
    ctx: ApiContext = Depends(deps.get_context),
) -> EndpointOut:
    """Create a new webhook subscription.

    Args:
        request: The subscription creation request.
        ctx: The API context containing organization info.

    Returns:
        The created subscription.
    """
    endpoint, error = await service.create_endpoint(
        ctx.organization, str(request.url), request.event_types, request.secret
    )
    if error:
        raise HTTPException(status_code=500, detail=error.message)

    # Track webhook subscription creation
    business_events.track_webhook_subscription_created(
        ctx=ctx,
        endpoint_id=endpoint.id,
        url=str(request.url),
        event_types=[e.value for e in request.event_types],
    )

    return endpoint


@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> None:
    """Delete a webhook subscription.

    Args:
        subscription_id: The ID of the subscription to delete.
        ctx: The API context containing organization info.
    """
    error = await service.delete_endpoint(ctx.organization, subscription_id)
    if error:
        raise HTTPException(status_code=500, detail=error.message)

    # Track webhook subscription deletion
    business_events.track_webhook_subscription_deleted(ctx=ctx, endpoint_id=subscription_id)


@router.patch("/subscriptions/{subscription_id}", response_model=EndpointOut)
async def patch_subscription(
    subscription_id: str,
    request: PatchSubscriptionRequest,
    ctx: ApiContext = Depends(deps.get_context),
) -> EndpointOut:
    """Update a webhook subscription.

    Args:
        subscription_id: The ID of the subscription to update.
        request: The subscription update request.
        ctx: The API context containing organization info.

    Returns:
        The updated subscription.
    """
    url = str(request.url) if request.url else None
    endpoint, error = await service.patch_endpoint(
        ctx.organization, subscription_id, url, request.event_types
    )
    if error:
        raise HTTPException(status_code=500, detail=error.message)

    # Track webhook subscription update
    business_events.track_webhook_subscription_updated(
        ctx=ctx,
        endpoint_id=subscription_id,
        url_changed=request.url is not None,
        event_types_changed=request.event_types is not None,
        new_event_types=[e.value for e in request.event_types] if request.event_types else None,
    )

    return endpoint


@router.get("/subscriptions/{subscription_id}/secret", response_model=EndpointSecretOut)
async def get_subscription_secret(
    subscription_id: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> EndpointSecretOut:
    """Get the signing secret for a webhook subscription.

    Args:
        subscription_id: The ID of the subscription.
        ctx: The API context containing organization info.

    Returns:
        The subscription's signing secret.
    """
    secret, error = await service.get_endpoint_secret(ctx.organization, subscription_id)
    if error:
        raise HTTPException(status_code=500, detail=error.message)

    # Track webhook secret viewing (security audit trail)
    business_events.track_webhook_secret_viewed(ctx=ctx, endpoint_id=subscription_id)

    return secret
