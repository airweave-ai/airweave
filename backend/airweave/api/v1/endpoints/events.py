from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from pydantic import BaseModel, HttpUrl

from airweave.webhooks.service import service
from airweave.webhooks.constants.event_types import EventType

from svix.api import MessageOut, EndpointOut, MessageAttemptOut, EndpointSecretOut

from airweave.api import deps
from airweave.api.context import ApiContext

router = APIRouter()


class SubscriptionWithAttemptsOut(BaseModel):
    """Response model for a subscription with its message attempts."""
    endpoint: EndpointOut
    message_attempts: List[MessageAttemptOut]

    class Config:
        arbitrary_types_allowed = True


class CreateSubscriptionRequest(BaseModel):
    url: HttpUrl
    event_types: List[EventType]
    secret: str | None = None

class PatchSubscriptionRequest(BaseModel):
    url: HttpUrl | None = None
    event_types: List[EventType] | None = None


@router.get("/messages", response_model=List[MessageOut])
async def get_messages(
    ctx: ApiContext = Depends(deps.get_context),
    event_types: List[str] | None = Query(default=None),
) -> List[MessageOut]:
    messages, error = await service.get_messages(ctx.organization, event_types=event_types)
    if error:
        raise HTTPException(status_code=500, detail=error.message)
    return messages

@router.get("/subscriptions", response_model=List[EndpointOut])
async def get_subscriptions(
    ctx: ApiContext = Depends(deps.get_context),
) -> List[EndpointOut]:
    endpoints, error = await service.get_endpoints(ctx.organization)
    if error:
        raise HTTPException(status_code=500, detail=error.message)
    return endpoints

@router.get("/subscriptions/{subscription_id}", response_model=SubscriptionWithAttemptsOut)
async def get_subscription(
    subscription_id: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> SubscriptionWithAttemptsOut:
    endpoint, error = await service.get_endpoint(ctx.organization, subscription_id)
    if error:
        raise HTTPException(status_code=500, detail=error.message)
    
    message_attempts, attempts_error = await service.get_message_attempts_by_endpoint(
        ctx.organization, subscription_id
    )
    if attempts_error:
        raise HTTPException(status_code=500, detail=attempts_error.message)
    
    return SubscriptionWithAttemptsOut(
        endpoint=endpoint,
        message_attempts=message_attempts or []
    )

@router.post("/subscriptions", response_model=EndpointOut)
async def create_subscription(
    request: CreateSubscriptionRequest,
    ctx: ApiContext = Depends(deps.get_context),
) -> EndpointOut:
    endpoint, error = await service.create_endpoint(ctx.organization, str(request.url), request.event_types, request.secret)
    if error:
        raise HTTPException(status_code=500, detail=error.message)
    return endpoint

@router.delete("/subscriptions/{subscription_id}")
async def delete_subscription(
    subscription_id: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> None:
    error = await service.delete_endpoint(ctx.organization, subscription_id)
    if error:
        raise HTTPException(status_code=500, detail=error.message)

@router.patch("/subscriptions/{subscription_id}", response_model=EndpointOut)
async def patch_subscription(
    subscription_id: str,
    request: PatchSubscriptionRequest,
    ctx: ApiContext = Depends(deps.get_context),
) -> EndpointOut:
    url = str(request.url) if request.url else None
    endpoint, error = await service.patch_endpoint(ctx.organization, subscription_id, url, request.event_types)
    if error:
        raise HTTPException(status_code=500, detail=error.message)
    return endpoint

@router.get("/subscriptions/{subscription_id}/secret", response_model=EndpointSecretOut)
async def get_subscription_secret(
    subscription_id: str,
    ctx: ApiContext = Depends(deps.get_context),
) -> EndpointSecretOut:
    secret, error = await service.get_endpoint_secret(ctx.organization, subscription_id)
    if error:
        raise HTTPException(status_code=500, detail=error.message)
    return secret