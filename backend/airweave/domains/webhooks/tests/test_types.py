"""Unit tests for webhook domain types.

Tests compute_health_status (core business logic), EventType enum derivation,
and error types.
"""

from datetime import datetime, timezone

from airweave.core.events.enums import (
    ALL_EVENT_TYPE_ENUMS,
    CollectionEventType,
    SourceConnectionEventType,
    SyncEventType,
)
from airweave.domains.webhooks.types import (
    DeliveryAttempt,
    EventType,
    HealthStatus,
    Subscription,
    WebhookPublishError,
    WebhooksError,
    compute_health_status,
)

NOW = datetime.now(timezone.utc)


def _attempt(status_code: int, offset_seconds: int = 0) -> DeliveryAttempt:
    """Create a DeliveryAttempt with the given status code."""
    return DeliveryAttempt(
        id=f"atmpt_{offset_seconds}",
        message_id="msg_1",
        endpoint_id="ep_1",
        timestamp=NOW,
        response_status_code=status_code,
    )


# ---------------------------------------------------------------------------
# compute_health_status
# ---------------------------------------------------------------------------


class TestComputeHealthStatus:
    """Tests for the compute_health_status function."""

    def test_empty_attempts_returns_unknown(self):
        assert compute_health_status([]) is HealthStatus.unknown

    def test_all_2xx_returns_healthy(self):
        attempts = [_attempt(200), _attempt(201), _attempt(204)]
        assert compute_health_status(attempts) is HealthStatus.healthy

    def test_single_success_returns_healthy(self):
        assert compute_health_status([_attempt(200)]) is HealthStatus.healthy

    def test_single_failure_returns_degraded(self):
        """One failure is below the consecutive threshold (3) so it's degraded, not failing."""
        assert compute_health_status([_attempt(500)]) is HealthStatus.degraded

    def test_two_leading_failures_then_success_returns_degraded(self):
        attempts = [_attempt(500, 0), _attempt(502, 1), _attempt(200, 2)]
        assert compute_health_status(attempts) is HealthStatus.degraded

    def test_three_consecutive_failures_returns_failing(self):
        attempts = [_attempt(500, 0), _attempt(503, 1), _attempt(502, 2)]
        assert compute_health_status(attempts) is HealthStatus.failing

    def test_three_failures_then_success_returns_failing(self):
        """Threshold is met by the leading failures -- trailing success doesn't help."""
        attempts = [
            _attempt(500, 0),
            _attempt(500, 1),
            _attempt(500, 2),
            _attempt(200, 3),
        ]
        assert compute_health_status(attempts) is HealthStatus.failing

    def test_mixed_non_consecutive_failures_returns_degraded(self):
        attempts = [_attempt(200, 0), _attempt(500, 1), _attempt(200, 2)]
        assert compute_health_status(attempts) is HealthStatus.degraded

    def test_custom_threshold_of_one(self):
        """With threshold=1, a single leading failure marks as failing."""
        attempts = [_attempt(500)]
        assert (
            compute_health_status(attempts, consecutive_failure_threshold=1) is HealthStatus.failing
        )

    def test_custom_threshold_of_five(self):
        """With threshold=5, three failures are still just degraded."""
        attempts = [_attempt(500, i) for i in range(3)]
        assert (
            compute_health_status(attempts, consecutive_failure_threshold=5)
            is HealthStatus.degraded
        )

    def test_boundary_exactly_at_threshold(self):
        """Exactly threshold failures -> failing."""
        attempts = [_attempt(500, i) for i in range(3)]
        assert (
            compute_health_status(attempts, consecutive_failure_threshold=3) is HealthStatus.failing
        )

    def test_boundary_one_below_threshold(self):
        """Threshold - 1 failures -> degraded (not failing)."""
        attempts = [_attempt(500, 0), _attempt(500, 1)]
        assert (
            compute_health_status(attempts, consecutive_failure_threshold=3)
            is HealthStatus.degraded
        )

    def test_4xx_counts_as_failure(self):
        """Non-2xx status codes (including 4xx) are treated as failures."""
        attempts = [_attempt(404, 0), _attempt(403, 1), _attempt(400, 2)]
        assert compute_health_status(attempts) is HealthStatus.failing

    def test_zero_status_code_counts_as_failure(self):
        """Status code 0 (connection failure) counts as failure."""
        attempts = [_attempt(0, 0), _attempt(0, 1), _attempt(0, 2)]
        assert compute_health_status(attempts) is HealthStatus.failing

    def test_299_counts_as_success(self):
        """Edge: 299 is within the 2xx range."""
        assert compute_health_status([_attempt(299)]) is HealthStatus.healthy

    def test_300_counts_as_failure(self):
        """Edge: 300 is outside the 2xx range."""
        assert compute_health_status([_attempt(300)]) is HealthStatus.degraded


# ---------------------------------------------------------------------------
# EventType enum
# ---------------------------------------------------------------------------


class TestEventType:
    """Tests for the dynamically-derived EventType enum."""

    def test_contains_all_sync_events(self):
        for member in SyncEventType:
            key = member.value.upper().replace(".", "_")
            assert hasattr(EventType, key), f"Missing EventType.{key}"
            assert EventType[key].value == member.value

    def test_contains_all_collection_events(self):
        for member in CollectionEventType:
            key = member.value.upper().replace(".", "_")
            assert hasattr(EventType, key), f"Missing EventType.{key}"

    def test_contains_all_source_connection_events(self):
        for member in SourceConnectionEventType:
            key = member.value.upper().replace(".", "_")
            assert hasattr(EventType, key), f"Missing EventType.{key}"

    def test_total_member_count_matches_all_enums(self):
        expected_count = sum(len(cls) for cls in ALL_EVENT_TYPE_ENUMS)
        assert len(EventType) == expected_count

    def test_values_are_dotted_strings(self):
        for member in EventType:
            assert "." in member.value, f"EventType.{member.name} = {member.value!r} has no dot"


# ---------------------------------------------------------------------------
# HealthStatus enum
# ---------------------------------------------------------------------------


class TestHealthStatus:
    """Tests for the HealthStatus enum."""

    def test_values(self):
        assert HealthStatus.healthy.value == "healthy"
        assert HealthStatus.degraded.value == "degraded"
        assert HealthStatus.failing.value == "failing"
        assert HealthStatus.unknown.value == "unknown"

    def test_is_string_enum(self):
        assert isinstance(HealthStatus.healthy, str)


# ---------------------------------------------------------------------------
# Error types
# ---------------------------------------------------------------------------


class TestWebhooksError:
    """Tests for the WebhooksError exception."""

    def test_stores_message_and_status_code(self):
        err = WebhooksError("not found", 404)
        assert err.message == "not found"
        assert err.status_code == 404
        assert str(err) == "not found"

    def test_default_status_code(self):
        err = WebhooksError("internal failure")
        assert err.status_code == 500

    def test_is_exception(self):
        assert issubclass(WebhooksError, Exception)


class TestWebhookPublishError:
    """Tests for the WebhookPublishError exception."""

    def test_stores_event_type_and_cause(self):
        cause = RuntimeError("connection lost")
        err = WebhookPublishError("sync.completed", cause)
        assert err.event_type == "sync.completed"
        assert err.cause is cause
        assert "sync.completed" in str(err)
        assert "connection lost" in str(err)

    def test_is_exception(self):
        assert issubclass(WebhookPublishError, Exception)


# ---------------------------------------------------------------------------
# Domain dataclass basics
# ---------------------------------------------------------------------------


class TestSubscriptionDataclass:
    """Verify Subscription defaults."""

    def test_defaults(self):
        sub = Subscription(id="sub_1", url="https://example.com", event_types=["sync.completed"])
        assert sub.disabled is False
        assert sub.created_at is None
        assert sub.updated_at is None
        assert sub.secret is None
        assert sub.delivery_attempts == []
