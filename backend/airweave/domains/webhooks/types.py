"""Webhook domain types.

Pure domain types with no infrastructure dependencies.
EventType is derived from the core event bus enums (single source of truth).
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from airweave.core.events.enums import ALL_EVENT_TYPE_ENUMS

# ---------------------------------------------------------------------------
# Health status (pure domain logic)
# ---------------------------------------------------------------------------


class HealthStatus(str, Enum):
    """Health status of a webhook subscription based on recent delivery attempts."""

    healthy = "healthy"
    """Last N deliveries all succeeded (2xx responses)."""

    degraded = "degraded"
    """Mix of successes and failures in recent deliveries."""

    failing = "failing"
    """Multiple consecutive failures beyond threshold."""

    unknown = "unknown"
    """No delivery attempts yet."""


def compute_health_status(
    attempts: list["DeliveryAttempt"],
    consecutive_failure_threshold: int = 3,
) -> HealthStatus:
    """Compute health status from recent delivery attempts.

    Args:
        attempts: Recent delivery attempts, most recent first.
        consecutive_failure_threshold: How many consecutive failures
            mark the subscription as ``failing``.

    Returns:
        The computed ``HealthStatus``.
    """
    if not attempts:
        return HealthStatus.unknown

    # Count consecutive leading failures (most recent first)
    consecutive_failures = 0
    for attempt in attempts:
        if attempt.response_status_code < 200 or attempt.response_status_code >= 300:
            consecutive_failures += 1
        else:
            break

    if consecutive_failures >= consecutive_failure_threshold:
        return HealthStatus.failing

    # Check if all succeeded
    all_success = all(200 <= a.response_status_code < 300 for a in attempts)
    if all_success:
        return HealthStatus.healthy

    return HealthStatus.degraded


# Derive the webhook EventType enum from the single source of truth in
# core/events/enums.py so there is only one place to add new event types.
# Member names are derived from values: "sync.pending" → SYNC_PENDING.
_members: dict[str, str] = {}
for _enum_cls in ALL_EVENT_TYPE_ENUMS:
    for _member in _enum_cls:
        _members[_member.value.upper().replace(".", "_")] = _member.value

EventType = Enum("EventType", _members, type=str)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Domain types for webhook subscriptions and messages
# ---------------------------------------------------------------------------


@dataclass
class Subscription:
    """A webhook subscription (endpoint)."""

    id: str
    url: str
    event_types: list[str]
    disabled: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Optional fields populated on detail views
    secret: Optional[str] = None
    delivery_attempts: list["DeliveryAttempt"] = field(default_factory=list)


@dataclass
class EventMessage:
    """A webhook event message."""

    id: str
    event_type: str
    payload: dict
    timestamp: datetime
    channels: list[str] = field(default_factory=list)


@dataclass
class DeliveryAttempt:
    """A delivery attempt for a webhook message."""

    id: str
    message_id: str
    endpoint_id: str
    timestamp: datetime
    response_status_code: int
    response: Optional[str] = None
    url: Optional[str] = None


@dataclass
class RecoveryTask:
    """A message recovery task."""

    id: str
    status: str  # "running", "completed", "unknown"


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class WebhooksError(Exception):
    """Error from webhook operations."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        """Initialize with message and optional HTTP status code."""
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class WebhookPublishError(Exception):
    """Failed to publish a domain event to webhook subscribers.

    Raised by WebhookPublisher implementations when event delivery fails.
    Caught by the event bus — never reaches domain or sync code.
    """

    def __init__(self, event_type: str, cause: Exception) -> None:
        """Initialize with the event type that failed and the underlying cause."""
        self.event_type = event_type
        self.cause = cause
        super().__init__(f"Failed to publish webhook event '{event_type}': {cause}")
