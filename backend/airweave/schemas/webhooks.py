"""Webhook subscription and message schemas.

This module defines Pydantic schemas for the Webhooks API, which handles webhook
subscriptions and message management. Webhooks allow you to receive
real-time notifications when events occur in Airweave.

All response models use snake_case field names for consistency with the webhook
payloads that are delivered to your endpoints.
"""

from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator

from airweave.domains.webhooks.types import EventType, HealthStatus

# Import shared error response models
from airweave.schemas.errors import (
    NotFoundErrorResponse,
    RateLimitErrorResponse,
    ValidationErrorDetail,
    ValidationErrorResponse,
)

if TYPE_CHECKING:
    from airweave.domains.webhooks.types import (
        DeliveryAttempt as DomainDeliveryAttempt,
    )
    from airweave.domains.webhooks.types import (
        EventMessage as DomainEventMessage,
    )
    from airweave.domains.webhooks.types import (
        Subscription as DomainSubscription,
    )

# Re-export for backwards compatibility
__all__ = [
    "NotFoundErrorResponse",
    "RateLimitErrorResponse",
    "ValidationErrorDetail",
    "ValidationErrorResponse",
]

# =============================================================================
# Unified Response Models (snake_case)
# =============================================================================
# These models provide a consistent snake_case API that matches the webhook
# payloads delivered to user endpoints. They wrap domain types.


class WebhookMessage(BaseModel):
    """A webhook message that was sent (or attempted) to webhook subscribers.

    The payload contains the actual event data matching the webhook delivery format.
    """

    id: str = Field(
        ...,
        description="Unique identifier for this message (UUID format)",
        json_schema_extra={"example": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"},
    )
    event_type: str = Field(
        ...,
        description="The type of event (e.g., 'sync.completed', 'sync.failed')",
        json_schema_extra={"example": "sync.completed"},
    )
    payload: dict = Field(
        ...,
        description="The event payload data, matching what is delivered to webhooks. "
        "Structure varies by event_type.",
    )
    timestamp: datetime = Field(
        ...,
        description="When this message was created (ISO 8601 format, UTC)",
        json_schema_extra={"example": "2024-03-15T09:45:32Z"},
    )
    channels: Optional[List[str]] = Field(
        default=None,
        description="Channels this message was sent to (typically matches the event type)",
        json_schema_extra={"example": ["sync.completed"]},
    )
    tags: Optional[List[str]] = Field(
        default=None,
        description="Tags associated with this message for filtering",
        json_schema_extra={"example": None},
    )

    @classmethod
    def from_domain(cls, msg: "DomainEventMessage") -> "WebhookMessage":
        """Convert a domain EventMessage to API response."""
        return cls(
            id=msg.id,
            event_type=msg.event_type,
            payload=msg.payload,
            timestamp=msg.timestamp,
            channels=msg.channels,
            tags=None,
        )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                "event_type": "sync.completed",
                "payload": {
                    "event_type": "sync.completed",
                    "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "collection_readable_id": "customer-support-tickets-x7k9m",
                    "collection_name": "Customer Support Tickets",
                    "source_connection_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
                    "source_type": "zendesk",
                    "status": "completed",
                    "timestamp": "2024-03-15T09:45:32Z",
                    "error": None,
                },
                "timestamp": "2024-03-15T09:45:32Z",
                "channels": ["sync.completed"],
                "tags": None,
                "delivery_attempts": None,
            }
        },
    }


class WebhookMessageWithAttempts(WebhookMessage):
    """A webhook message with delivery attempts."""

    delivery_attempts: Optional[List["DeliveryAttempt"]] = Field(
        default=None,
        description="Delivery attempts for this message.",
    )

    @classmethod
    def from_domain(
        cls, msg: "DomainEventMessage", attempts: Optional[List["DeliveryAttempt"]] = None
    ) -> "WebhookMessageWithAttempts":
        """Convert a domain EventMessage to API response with attempts."""
        return cls(
            id=msg.id,
            event_type=msg.event_type,
            payload=msg.payload,
            timestamp=msg.timestamp,
            channels=msg.channels,
            tags=None,
            delivery_attempts=attempts,
        )


class WebhookSubscription(BaseModel):
    """A webhook subscription (endpoint) configuration.

    This is the lightweight representation returned by list, create, update,
    and delete endpoints.  For the full detail view (delivery attempts,
    signing secret) see ``WebhookSubscriptionDetail``.
    """

    id: str = Field(
        ...,
        description="Unique identifier for this subscription (UUID format)",
        json_schema_extra={"example": "c3d4e5f6-a7b8-9012-cdef-345678901234"},
    )
    url: str = Field(
        ...,
        description="The URL where webhook events are delivered",
        json_schema_extra={"example": "https://api.mycompany.com/webhooks/airweave"},
    )
    filter_types: Optional[List[str]] = Field(
        default=None,
        description=(
            "Event types this subscription is filtered to receive. "
            "See EventType enum for all available types."
        ),
        json_schema_extra={"example": ["sync.completed", "sync.failed"]},
    )
    disabled: bool = Field(
        default=False,
        description="Whether this subscription is currently disabled. "
        "Disabled subscriptions do not receive event deliveries.",
        json_schema_extra={"example": False},
    )
    description: Optional[str] = Field(
        default=None,
        description="Optional human-readable description of this subscription",
        json_schema_extra={"example": "Production notifications for data team"},
    )
    created_at: datetime = Field(
        ...,
        description="When this subscription was created (ISO 8601 format, UTC)",
        json_schema_extra={"example": "2024-03-01T08:00:00Z"},
    )
    updated_at: datetime = Field(
        ...,
        description="When this subscription was last updated (ISO 8601 format, UTC)",
        json_schema_extra={"example": "2024-03-15T14:30:00Z"},
    )
    health_status: HealthStatus = Field(
        default=HealthStatus.unknown,
        description="Health status of this subscription based on recent delivery attempts. "
        "Values: 'healthy' (all recent deliveries succeeded), "
        "'degraded' (mix of successes and failures), "
        "'failing' (consecutive failures beyond threshold), "
        "'unknown' (no delivery data yet).",
        json_schema_extra={"example": "healthy"},
    )

    @classmethod
    def from_domain(
        cls,
        sub: "DomainSubscription",
        health: HealthStatus = HealthStatus.unknown,
    ) -> "WebhookSubscription":
        """Convert a domain Subscription to API response."""
        return cls(
            id=sub.id,
            url=sub.url,
            filter_types=sub.event_types,
            disabled=sub.disabled,
            description=None,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
            health_status=health,
        )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "c3d4e5f6-a7b8-9012-cdef-345678901234",
                "url": "https://api.mycompany.com/webhooks/airweave",
                "filter_types": ["sync.completed", "sync.failed"],
                "disabled": False,
                "description": "Production notifications for data team",
                "created_at": "2024-03-01T08:00:00Z",
                "updated_at": "2024-03-15T14:30:00Z",
                "health_status": "healthy",
            }
        },
    }


class WebhookSubscriptionDetail(WebhookSubscription):
    """Full subscription detail, including delivery attempts and signing secret.

    Returned by ``GET /subscriptions/{id}`` only.
    """

    delivery_attempts: Optional[List["DeliveryAttempt"]] = Field(
        default=None,
        description="Recent delivery attempts for this subscription.",
    )
    secret: Optional[str] = Field(
        default=None,
        description="The signing secret for webhook signature verification. "
        "Only included when include_secret=true is passed to the API. "
        "Keep this secret secure.",
        json_schema_extra={"example": "whsec_C2FVsBQIhrscChlQIMV10R9X4jZ8"},
    )

    @classmethod
    def from_domain(
        cls,
        sub: "DomainSubscription",
        health: HealthStatus = HealthStatus.unknown,
        delivery_attempts: Optional[List["DeliveryAttempt"]] = None,
        secret: Optional[str] = None,
    ) -> "WebhookSubscriptionDetail":
        """Convert a domain Subscription to detailed API response."""
        return cls(
            id=sub.id,
            url=sub.url,
            filter_types=sub.event_types,
            disabled=sub.disabled,
            description=None,
            created_at=sub.created_at,
            updated_at=sub.updated_at,
            health_status=health,
            delivery_attempts=delivery_attempts,
            secret=secret,
        )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "c3d4e5f6-a7b8-9012-cdef-345678901234",
                "url": "https://api.mycompany.com/webhooks/airweave",
                "filter_types": ["sync.completed", "sync.failed"],
                "disabled": False,
                "description": "Production notifications for data team",
                "created_at": "2024-03-01T08:00:00Z",
                "updated_at": "2024-03-15T14:30:00Z",
                "health_status": "healthy",
                "delivery_attempts": None,
                "secret": None,
            }
        },
    }


class DeliveryAttempt(BaseModel):
    """A delivery attempt for a webhook message.

    Each time Airweave attempts to deliver a message to your webhook endpoint,
    a delivery attempt is recorded. Failed attempts are automatically retried
    with exponential backoff.
    """

    id: str = Field(
        ...,
        description="Unique identifier for this delivery attempt",
        json_schema_extra={"example": "atmpt_2bVxUn3RFnLYHa8z6ZKHMT9PqPX"},
    )
    message_id: str = Field(
        ...,
        description="The event message that was being delivered",
        json_schema_extra={"example": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"},
    )
    endpoint_id: str = Field(
        ...,
        description="The subscription endpoint this was delivered to",
        json_schema_extra={"example": "c3d4e5f6-a7b8-9012-cdef-345678901234"},
    )
    response: Optional[str] = Field(
        default=None,
        description="The response body returned by your webhook endpoint (truncated to 1KB)",
        json_schema_extra={"example": '{"status": "processed", "id": "evt_123"}'},
    )
    response_status_code: int = Field(
        ...,
        description="HTTP status code returned by your webhook endpoint. "
        "2xx codes indicate success; other codes trigger retries.",
        json_schema_extra={"example": 200},
    )
    status: str = Field(
        ...,
        description="Delivery status: `success` (2xx response), `pending` (awaiting delivery), "
        "or `failed` (non-2xx response or timeout)",
        json_schema_extra={"example": "success"},
    )
    timestamp: datetime = Field(
        ...,
        description="When this delivery attempt occurred (ISO 8601 format, UTC)",
        json_schema_extra={"example": "2024-03-15T09:45:33Z"},
    )
    url: Optional[str] = Field(
        default=None,
        description="The URL that was called",
    )

    @classmethod
    def from_domain(cls, attempt: "DomainDeliveryAttempt") -> "DeliveryAttempt":
        """Convert a domain DeliveryAttempt to API response."""
        # Derive status from response code
        if attempt.response_status_code >= 200 and attempt.response_status_code < 300:
            status = "success"
        elif attempt.response_status_code == 0:
            status = "pending"
        else:
            status = "failed"

        return cls(
            id=attempt.id,
            message_id=attempt.message_id,
            endpoint_id=attempt.endpoint_id,
            response=attempt.response,
            response_status_code=attempt.response_status_code,
            status=status,
            timestamp=attempt.timestamp,
            url=attempt.url,
        )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Successful Delivery",
                    "value": {
                        "id": "atmpt_2bVxUn3RFnLYHa8z6ZKHMT9PqPX",
                        "message_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                        "endpoint_id": "c3d4e5f6-a7b8-9012-cdef-345678901234",
                        "response": '{"status": "processed", "id": "evt_123"}',
                        "response_status_code": 200,
                        "status": "success",
                        "timestamp": "2024-03-15T09:45:33Z",
                    },
                },
                {
                    "summary": "Failed Delivery",
                    "value": {
                        "id": "atmpt_3cWyVo4SGmMZb9a7ALINT0QrQYQ",
                        "message_id": "b2c3d4e5-f6a7-8901-bcde-f23456789012",
                        "endpoint_id": "c3d4e5f6-a7b8-9012-cdef-345678901234",
                        "response": "Internal Server Error",
                        "response_status_code": 500,
                        "status": "failed",
                        "timestamp": "2024-03-15T10:12:05Z",
                    },
                },
            ],
        },
    }


class RecoveryTask(BaseModel):
    """Information about a message recovery task.

    When you trigger a recovery of failed messages, this object is returned
    to track the recovery progress. The status indicates whether the recovery
    is still in progress or has completed.
    """

    id: str = Field(
        ...,
        description="Unique identifier for this recovery task (Svix internal ID)",
        json_schema_extra={"example": "rcvr_2bVxUn3RFnLYHa8z6ZKHMT9PqPX"},
    )
    status: str = Field(
        ...,
        description="Recovery task status: 'running' or 'completed'",
        json_schema_extra={"example": "running"},
    )

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "rcvr_2bVxUn3RFnLYHa8z6ZKHMT9PqPX",
                "status": "running",
            }
        },
    }


# =============================================================================
# Request Models
# =============================================================================


class CreateSubscriptionRequest(BaseModel):
    """Create a new webhook subscription.

    Webhook subscriptions define where Airweave should send event notifications.
    You can subscribe to specific event types to receive only the events you care about.
    """

    url: HttpUrl = Field(
        ...,
        description="The HTTPS URL where webhook events will be delivered. "
        "Must be a publicly accessible endpoint that returns a 2xx status code.",
        json_schema_extra={"example": "https://api.mycompany.com/webhooks/airweave"},
    )
    event_types: List[EventType] = Field(
        ...,
        description="List of event types to subscribe to. Events not in this list "
        "will not be delivered to this subscription. Available types: "
        "`sync.pending`, `sync.running`, `sync.completed`, `sync.failed`, "
        "`sync.cancelled`, `source_connection.created`, "
        "`source_connection.auth_completed`, `source_connection.deleted`, "
        "`collection.created`, `collection.updated`, `collection.deleted`.",
        json_schema_extra={"example": ["sync.completed", "sync.failed"]},
    )
    secret: str | None = Field(
        default=None,
        min_length=24,
        description="Optional custom signing secret for webhook signature verification. "
        "If not provided, a secure secret will be auto-generated. "
        "Must be at least 24 characters if specified.",
        json_schema_extra={"example": "whsec_C2FVsBQIhrscChlQIMV10R9X4jZ8"},
    )

    @field_validator("event_types")
    @classmethod
    def event_types_not_empty(cls, v: List[EventType]) -> List[EventType]:
        """Validate that event_types is not empty."""
        if not v:
            raise ValueError("event_types cannot be empty")
        return v

    @field_validator("secret")
    @classmethod
    def secret_min_length(cls, v: str | None) -> str | None:
        """Validate secret minimum length if provided."""
        if v is not None and len(v) < 24:
            raise ValueError("secret must be at least 24 characters")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://api.mycompany.com/webhooks/airweave",
                "event_types": ["sync.completed", "sync.failed"],
            }
        }
    }


class PatchSubscriptionRequest(BaseModel):
    """Update an existing webhook subscription.

    All fields are optional. Only provided fields will be updated;
    omitted fields retain their current values.

    When re-enabling a subscription (setting `disabled: false`), you can optionally
    provide `recover_since` to replay messages that were missed while disabled.
    """

    url: HttpUrl | None = Field(
        default=None,
        description="New URL for webhook delivery. Must be a publicly accessible HTTPS endpoint.",
        json_schema_extra={"example": "https://api.mycompany.com/webhooks/airweave-v2"},
    )
    event_types: List[EventType] | None = Field(
        default=None,
        description="New list of event types to subscribe to. "
        "This replaces the existing list entirely.",
        json_schema_extra={"example": ["sync.completed", "sync.failed", "sync.running"]},
    )
    disabled: bool | None = Field(
        default=None,
        description="Set to `true` to pause delivery to this subscription, "
        "or `false` to resume. Disabled subscriptions will not receive events.",
        json_schema_extra={"example": False},
    )
    recover_since: datetime | None = Field(
        default=None,
        description="When re-enabling a subscription (`disabled: false`), optionally "
        "recover failed messages from this timestamp. Only applies when enabling.",
        json_schema_extra={"example": "2024-03-14T00:00:00Z"},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Update event types",
                    "value": {
                        "event_types": ["sync.completed", "sync.failed", "sync.running"],
                    },
                },
                {
                    "summary": "Disable subscription",
                    "value": {
                        "disabled": True,
                    },
                },
                {
                    "summary": "Enable subscription",
                    "value": {
                        "disabled": False,
                    },
                },
                {
                    "summary": "Enable with message recovery",
                    "value": {
                        "disabled": False,
                        "recover_since": "2024-03-14T00:00:00Z",
                    },
                },
                {
                    "summary": "Change URL",
                    "value": {
                        "url": "https://api.mycompany.com/webhooks/airweave-v2",
                    },
                },
            ],
        }
    }


class RecoverMessagesRequest(BaseModel):
    """Request to retry failed message deliveries.

    Use this to replay events that failed to deliver during a specific time window,
    for example after fixing an issue with your webhook endpoint.
    """

    since: datetime = Field(
        ...,
        description="Start of the recovery time window (inclusive). "
        "All failed messages from this time onward will be retried.",
        json_schema_extra={"example": "2024-03-14T00:00:00Z"},
    )
    until: datetime | None = Field(
        default=None,
        description="End of the recovery time window (exclusive). "
        "If not specified, recovers all failed messages up to now.",
        json_schema_extra={"example": "2024-03-15T00:00:00Z"},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Recover last 24 hours",
                    "value": {
                        "since": "2024-03-14T00:00:00Z",
                        "until": "2024-03-15T00:00:00Z",
                    },
                },
                {
                    "summary": "Recover from timestamp to now",
                    "value": {
                        "since": "2024-03-14T12:00:00Z",
                    },
                },
            ],
        }
    }
