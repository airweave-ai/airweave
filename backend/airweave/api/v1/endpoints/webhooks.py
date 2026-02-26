"""Webhooks API endpoints for webhook subscriptions and messages.

This module provides endpoints for managing webhook subscriptions and
retrieving event messages sent to those webhooks. Uses protocol-based
dependency injection via Inject().

All business logic lives in the ``WebhookService`` — endpoints are thin
HTTP routing that delegates to the service and converts results to API
schemas.
"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from airweave.analytics import business_events
from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.core.protocols import WebhookServiceProtocol
from airweave.domains.webhooks import WebhooksError
from airweave.domains.webhooks.types import compute_health_status
from airweave.schemas.webhooks import (
    CreateSubscriptionRequest,
    DeliveryAttempt,
    NotFoundErrorResponse,
    PatchSubscriptionRequest,
    RateLimitErrorResponse,
    RecoverMessagesRequest,
    RecoveryTask,
    ValidationErrorResponse,
    WebhookMessage,
    WebhookMessageWithAttempts,
    WebhookSubscription,
    WebhookSubscriptionDetail,
)

router = APIRouter()


@router.get(
    "/messages",
    response_model=List[WebhookMessage],
    summary="List Messages",
    description="""Retrieve all webhook messages for your organization.

Webhook messages represent payloads that were sent (or attempted to be sent)
to your subscribed endpoints. Each message contains the event type, payload data,
and delivery status information.

Use the `event_types` query parameter to filter messages by specific event types,
such as `sync.completed` or `sync.failed`.""",
    responses={
        200: {"model": List[WebhookMessage], "description": "List of webhook messages"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def get_messages(
    ctx: ApiContext = Depends(deps.get_context),
    webhook_service: WebhookServiceProtocol = Inject(WebhookServiceProtocol),
    event_types: List[str] | None = Query(
        default=None,
        description="Filter messages by event type(s). "
        "Accepts multiple values, e.g., `?event_types=sync.completed&event_types=sync.failed`.",
        json_schema_extra={"example": ["sync.completed", "sync.failed"]},
    ),
) -> List[WebhookMessage]:
    """Retrieve event messages for the current organization."""
    try:
        messages = await webhook_service.get_messages(ctx.organization.id, event_types=event_types)
    except WebhooksError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    return [WebhookMessage.from_domain(msg) for msg in messages]


@router.get(
    "/messages/{message_id}",
    response_model=WebhookMessageWithAttempts,
    summary="Get Message",
    description="""Retrieve a specific webhook message by its ID.

Returns the full message details including the event type, payload data,
timestamp, and delivery channel information. Use this to inspect the
exact payload that was sent to your webhook endpoints.

Use `include_attempts=true` to also retrieve delivery attempts for this message,
which include HTTP response codes, response bodies, and timestamps for debugging
delivery failures.""",
    responses={
        200: {"model": WebhookMessageWithAttempts, "description": "Webhook message details"},
        404: {"model": NotFoundErrorResponse, "description": "Message Not Found"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def get_message(
    message_id: str = Path(
        ...,
        description="The unique identifier of the message to retrieve (UUID).",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    ),
    include_attempts: bool = Query(
        default=False,
        description="Include delivery attempts for this message. Each attempt includes "
        "the HTTP response code, response body, and timestamp.",
    ),
    ctx: ApiContext = Depends(deps.get_context),
    webhook_service: WebhookServiceProtocol = Inject(WebhookServiceProtocol),
) -> WebhookMessageWithAttempts:
    """Retrieve a specific event message by ID."""
    try:
        message = await webhook_service.get_message(ctx.organization.id, message_id)

        attempts = None
        if include_attempts:
            attempts_list = await webhook_service.get_message_attempts(
                ctx.organization.id, message_id
            )
            attempts = [DeliveryAttempt.from_domain(a) for a in attempts_list]
    except WebhooksError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    return WebhookMessageWithAttempts.from_domain(message, attempts=attempts)


@router.get(
    "/subscriptions",
    response_model=List[WebhookSubscription],
    summary="List Subscriptions",
    description="""List all webhook subscriptions for your organization.

Returns all configured webhook endpoints, including their URLs, subscribed
event types, and current status (enabled/disabled). Use this to audit
your webhook configuration or find a specific subscription.""",
    responses={
        200: {"model": List[WebhookSubscription], "description": "List of webhook subscriptions"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def get_subscriptions(
    ctx: ApiContext = Depends(deps.get_context),
    webhook_service: WebhookServiceProtocol = Inject(WebhookServiceProtocol),
) -> List[WebhookSubscription]:
    """List all webhook subscriptions for the organization."""
    try:
        results = await webhook_service.list_subscriptions_with_health(ctx.organization.id)
    except WebhooksError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    return [
        WebhookSubscription.from_domain(sub, health=health) for sub, health, _attempts in results
    ]


@router.get(
    "/subscriptions/{subscription_id}",
    response_model=WebhookSubscriptionDetail,
    summary="Get Subscription",
    description="""Retrieve a specific webhook subscription with its recent delivery attempts.

Returns the subscription configuration along with a history of message delivery
attempts. This is useful for debugging delivery issues or verifying that your
endpoint is correctly receiving events.

Use `include_secret=true` to also retrieve the signing secret for webhook
signature verification. Keep this secret secure.""",
    responses={
        200: {
            "model": WebhookSubscriptionDetail,
            "description": "Subscription with delivery attempts",
        },
        404: {"model": NotFoundErrorResponse, "description": "Subscription Not Found"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def get_subscription(
    subscription_id: str = Path(
        ...,
        description="The unique identifier of the subscription to retrieve (UUID).",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    ),
    include_secret: bool = Query(
        default=False,
        description="Include the signing secret for webhook signature verification. "
        "Keep this secret secure and use it to verify the 'svix-signature' header.",
    ),
    ctx: ApiContext = Depends(deps.get_context),
    webhook_service: WebhookServiceProtocol = Inject(WebhookServiceProtocol),
) -> WebhookSubscriptionDetail:
    """Retrieve a specific webhook subscription with delivery attempts."""
    try:
        subscription, domain_attempts, secret = await webhook_service.get_subscription_detail(
            ctx.organization.id,
            subscription_id,
            include_secret=include_secret,
        )
    except WebhooksError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    delivery_attempts = [DeliveryAttempt.from_domain(a) for a in domain_attempts]
    health = compute_health_status(domain_attempts)
    return WebhookSubscriptionDetail.from_domain(
        subscription, health=health, delivery_attempts=delivery_attempts, secret=secret
    )


@router.post(
    "/subscriptions",
    response_model=WebhookSubscription,
    summary="Create Subscription",
    description="""Create a new webhook subscription.

Webhook subscriptions allow you to receive real-time notifications when events
occur in Airweave. When you create a subscription, you specify:

- **URL**: The HTTPS endpoint where events will be delivered
- **Event Types**: Which events you want to receive (e.g., `sync.completed`, `sync.failed`)
- **Secret** (optional): A custom signing secret for verifying webhook signatures

After creation, Airweave will send HTTP POST requests to your URL whenever
matching events occur. Each request includes a signature header for verification.""",
    responses={
        200: {"model": WebhookSubscription, "description": "Created subscription"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def create_subscription(
    request: CreateSubscriptionRequest,
    ctx: ApiContext = Depends(deps.get_context),
    webhook_service: WebhookServiceProtocol = Inject(WebhookServiceProtocol),
) -> WebhookSubscription:
    """Create a new webhook subscription."""
    event_type_strs = [e.value for e in request.event_types]

    try:
        subscription = await webhook_service.create_subscription(
            ctx.organization.id,
            str(request.url),
            event_type_strs,
            request.secret,
        )
    except WebhooksError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    # Track webhook subscription creation
    business_events.track_webhook_subscription_created(
        ctx=ctx,
        endpoint_id=subscription.id,
        url=str(request.url),
        event_types=event_type_strs,
    )

    return WebhookSubscription.from_domain(subscription)


@router.delete(
    "/subscriptions/{subscription_id}",
    response_model=WebhookSubscription,
    summary="Delete Subscription",
    description="""Permanently delete a webhook subscription.

Once deleted, Airweave will stop sending events to this endpoint immediately.
This action cannot be undone. Any pending message deliveries will be cancelled.

If you want to temporarily stop receiving events, consider disabling the
subscription instead using the PATCH endpoint.""",
    responses={
        200: {"model": WebhookSubscription, "description": "Deleted subscription"},
        404: {"model": NotFoundErrorResponse, "description": "Subscription Not Found"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def delete_subscription(
    subscription_id: str = Path(
        ...,
        description="The unique identifier of the subscription to delete (UUID).",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    ),
    ctx: ApiContext = Depends(deps.get_context),
    webhook_service: WebhookServiceProtocol = Inject(WebhookServiceProtocol),
) -> WebhookSubscription:
    """Delete a webhook subscription permanently."""
    try:
        subscription = await webhook_service.delete_subscription(
            ctx.organization.id, subscription_id
        )
    except WebhooksError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    # Track webhook subscription deletion
    business_events.track_webhook_subscription_deleted(ctx=ctx, endpoint_id=subscription_id)

    return WebhookSubscription.from_domain(subscription)


@router.patch(
    "/subscriptions/{subscription_id}",
    response_model=WebhookSubscription,
    summary="Update Subscription",
    description="""Update an existing webhook subscription.

Use this endpoint to modify a subscription's configuration. You can:

- **Change the URL**: Update where events are delivered
- **Update event types**: Modify which events trigger notifications
- **Enable/disable**: Temporarily pause delivery without deleting the subscription
- **Recover messages**: When re-enabling, optionally recover missed messages

Only include the fields you want to change. Omitted fields will retain their
current values.

When re-enabling a subscription (`disabled: false`), you can optionally provide
`recover_since` to automatically retry all messages that were generated while
the subscription was disabled.""",
    responses={
        200: {"model": WebhookSubscription, "description": "Updated subscription"},
        404: {"model": NotFoundErrorResponse, "description": "Subscription Not Found"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def patch_subscription(
    subscription_id: str = Path(
        ...,
        description="The unique identifier of the subscription to update (UUID).",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    ),
    request: PatchSubscriptionRequest = ...,
    ctx: ApiContext = Depends(deps.get_context),
    webhook_service: WebhookServiceProtocol = Inject(WebhookServiceProtocol),
) -> WebhookSubscription:
    """Update an existing webhook subscription."""
    url = str(request.url) if request.url else None
    event_type_strs = [e.value for e in request.event_types] if request.event_types else None

    try:
        subscription = await webhook_service.update_subscription(
            ctx.organization.id,
            subscription_id,
            url=url,
            event_types=event_type_strs,
            disabled=request.disabled,
            recover_since=request.recover_since,
        )
    except WebhooksError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    # Track webhook subscription update
    business_events.track_webhook_subscription_updated(
        ctx=ctx,
        endpoint_id=subscription_id,
        url_changed=request.url is not None,
        event_types_changed=request.event_types is not None,
        new_event_types=event_type_strs,
    )

    return WebhookSubscription.from_domain(subscription)


@router.post(
    "/subscriptions/{subscription_id}/recover",
    response_model=RecoveryTask,
    summary="Recover Failed Messages",
    description="""Retry failed message deliveries for a webhook subscription.

Triggers a recovery process that replays all failed messages within the
specified time window. This is useful when:

- Your endpoint was temporarily down and you want to catch up
- You've fixed a bug in your webhook handler
- You want to reprocess events after re-enabling a disabled subscription

Messages are retried in chronological order. Successfully delivered messages
are skipped; only failed or pending messages are retried.""",
    responses={
        200: {"model": RecoveryTask, "description": "Recovery task information"},
        404: {"model": NotFoundErrorResponse, "description": "Subscription Not Found"},
        422: {"model": ValidationErrorResponse, "description": "Validation Error"},
        429: {"model": RateLimitErrorResponse, "description": "Rate Limit Exceeded"},
    },
)
async def recover_failed_messages(
    subscription_id: str = Path(
        ...,
        description="The unique identifier of the subscription to recover messages for (UUID).",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    ),
    request: RecoverMessagesRequest = ...,
    ctx: ApiContext = Depends(deps.get_context),
    webhook_service: WebhookServiceProtocol = Inject(WebhookServiceProtocol),
) -> RecoveryTask:
    """Retry failed message deliveries for a subscription."""
    try:
        result = await webhook_service.recover_messages(
            ctx.organization.id,
            subscription_id,
            since=request.since,
            until=request.until,
        )
    except WebhooksError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message) from e

    return RecoveryTask(id=result.id, status=result.status)
