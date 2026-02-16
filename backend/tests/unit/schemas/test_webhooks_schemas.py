"""Unit tests for webhook Pydantic schemas.

Tests from_domain() conversions and request model validation.
"""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from airweave.domains.webhooks.types import (
    DeliveryAttempt as DomainDeliveryAttempt,
)
from airweave.domains.webhooks.types import (
    EventMessage as DomainEventMessage,
)
from airweave.domains.webhooks.types import (
    HealthStatus,
)
from airweave.domains.webhooks.types import (
    Subscription as DomainSubscription,
)
from airweave.schemas.webhooks import (
    CreateSubscriptionRequest,
    DeliveryAttempt,
    PatchSubscriptionRequest,
    RecoverMessagesRequest,
    RecoveryTask,
    WebhookMessage,
    WebhookMessageWithAttempts,
    WebhookSubscription,
    WebhookSubscriptionDetail,
)

NOW = datetime(2024, 3, 15, 9, 45, 32, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# WebhookMessage.from_domain
# ---------------------------------------------------------------------------


class TestWebhookMessageFromDomain:
    """Tests for WebhookMessage.from_domain()."""

    def test_maps_all_fields(self):
        domain_msg = DomainEventMessage(
            id="msg_1",
            event_type="sync.completed",
            payload={"status": "completed"},
            timestamp=NOW,
            channels=["sync.completed"],
        )
        schema = WebhookMessage.from_domain(domain_msg)

        assert schema.id == "msg_1"
        assert schema.event_type == "sync.completed"
        assert schema.payload == {"status": "completed"}
        assert schema.timestamp == NOW
        assert schema.channels == ["sync.completed"]
        assert schema.tags is None

    def test_empty_channels(self):
        domain_msg = DomainEventMessage(
            id="msg_2",
            event_type="sync.failed",
            payload={},
            timestamp=NOW,
            channels=[],
        )
        schema = WebhookMessage.from_domain(domain_msg)
        assert schema.channels == []


# ---------------------------------------------------------------------------
# WebhookMessageWithAttempts.from_domain
# ---------------------------------------------------------------------------


class TestWebhookMessageWithAttemptsFromDomain:
    """Tests for WebhookMessageWithAttempts.from_domain()."""

    def test_without_attempts(self):
        domain_msg = DomainEventMessage(
            id="msg_1", event_type="sync.completed", payload={}, timestamp=NOW
        )
        schema = WebhookMessageWithAttempts.from_domain(domain_msg)
        assert schema.delivery_attempts is None

    def test_with_attempts(self):
        domain_msg = DomainEventMessage(
            id="msg_1", event_type="sync.completed", payload={}, timestamp=NOW
        )
        attempt = DeliveryAttempt(
            id="atmpt_1",
            message_id="msg_1",
            endpoint_id="ep_1",
            response_status_code=200,
            status="success",
            timestamp=NOW,
        )
        schema = WebhookMessageWithAttempts.from_domain(domain_msg, attempts=[attempt])
        assert schema.delivery_attempts is not None
        assert len(schema.delivery_attempts) == 1
        assert schema.delivery_attempts[0].id == "atmpt_1"


# ---------------------------------------------------------------------------
# WebhookSubscription.from_domain
# ---------------------------------------------------------------------------


class TestWebhookSubscriptionFromDomain:
    """Tests for WebhookSubscription.from_domain()."""

    def _make_domain_sub(self, **overrides) -> DomainSubscription:
        defaults = {
            "id": "sub_1",
            "url": "https://example.com/hook",
            "event_types": ["sync.completed", "sync.failed"],
            "disabled": False,
            "created_at": NOW,
            "updated_at": NOW,
        }
        defaults.update(overrides)
        return DomainSubscription(**defaults)

    def test_basic_conversion(self):
        sub = self._make_domain_sub()
        schema = WebhookSubscription.from_domain(sub)

        assert schema.id == "sub_1"
        assert schema.url == "https://example.com/hook"
        assert schema.filter_types == ["sync.completed", "sync.failed"]
        assert schema.disabled is False
        assert schema.created_at == NOW
        assert schema.updated_at == NOW
        assert schema.health_status is HealthStatus.unknown

    def test_with_health(self):
        sub = self._make_domain_sub()
        schema = WebhookSubscription.from_domain(sub, health=HealthStatus.healthy)
        assert schema.health_status is HealthStatus.healthy

    def test_description_is_always_none(self):
        sub = self._make_domain_sub()
        schema = WebhookSubscription.from_domain(sub)
        assert schema.description is None


# ---------------------------------------------------------------------------
# WebhookSubscriptionDetail.from_domain
# ---------------------------------------------------------------------------


class TestWebhookSubscriptionDetailFromDomain:
    """Tests for WebhookSubscriptionDetail.from_domain()."""

    def _make_domain_sub(self, **overrides) -> DomainSubscription:
        defaults = {
            "id": "sub_1",
            "url": "https://example.com/hook",
            "event_types": ["sync.completed"],
            "disabled": False,
            "created_at": NOW,
            "updated_at": NOW,
        }
        defaults.update(overrides)
        return DomainSubscription(**defaults)

    def test_with_delivery_attempts_and_secret(self):
        sub = self._make_domain_sub()
        attempt = DeliveryAttempt(
            id="atmpt_1",
            message_id="msg_1",
            endpoint_id="ep_1",
            response_status_code=200,
            status="success",
            timestamp=NOW,
        )
        schema = WebhookSubscriptionDetail.from_domain(
            sub,
            health=HealthStatus.healthy,
            delivery_attempts=[attempt],
            secret="whsec_test_secret",
        )
        assert schema.delivery_attempts is not None
        assert len(schema.delivery_attempts) == 1
        assert schema.secret == "whsec_test_secret"
        assert schema.health_status is HealthStatus.healthy

    def test_without_optional_fields(self):
        sub = self._make_domain_sub()
        schema = WebhookSubscriptionDetail.from_domain(sub)
        assert schema.delivery_attempts is None
        assert schema.secret is None
        assert schema.health_status is HealthStatus.unknown

    def test_inherits_from_webhook_subscription(self):
        assert issubclass(WebhookSubscriptionDetail, WebhookSubscription)


# ---------------------------------------------------------------------------
# DeliveryAttempt.from_domain
# ---------------------------------------------------------------------------


class TestDeliveryAttemptFromDomain:
    """Tests for DeliveryAttempt.from_domain() status derivation."""

    def _make_attempt(self, status_code: int) -> DomainDeliveryAttempt:
        return DomainDeliveryAttempt(
            id="atmpt_1",
            message_id="msg_1",
            endpoint_id="ep_1",
            timestamp=NOW,
            response_status_code=status_code,
            response="OK",
            url="https://example.com/hook",
        )

    def test_2xx_is_success(self):
        for code in [200, 201, 204, 299]:
            schema = DeliveryAttempt.from_domain(self._make_attempt(code))
            assert schema.status == "success", f"Expected success for {code}"

    def test_zero_is_pending(self):
        schema = DeliveryAttempt.from_domain(self._make_attempt(0))
        assert schema.status == "pending"

    def test_4xx_is_failed(self):
        for code in [400, 403, 404, 422]:
            schema = DeliveryAttempt.from_domain(self._make_attempt(code))
            assert schema.status == "failed", f"Expected failed for {code}"

    def test_5xx_is_failed(self):
        for code in [500, 502, 503]:
            schema = DeliveryAttempt.from_domain(self._make_attempt(code))
            assert schema.status == "failed", f"Expected failed for {code}"

    def test_3xx_is_failed(self):
        schema = DeliveryAttempt.from_domain(self._make_attempt(301))
        assert schema.status == "failed"

    def test_maps_all_fields(self):
        schema = DeliveryAttempt.from_domain(self._make_attempt(200))
        assert schema.id == "atmpt_1"
        assert schema.message_id == "msg_1"
        assert schema.endpoint_id == "ep_1"
        assert schema.timestamp == NOW
        assert schema.response == "OK"
        assert schema.url == "https://example.com/hook"


# ---------------------------------------------------------------------------
# RecoveryTask
# ---------------------------------------------------------------------------


class TestRecoveryTaskSchema:
    """Tests for RecoveryTask schema."""

    def test_basic_instantiation(self):
        task = RecoveryTask(id="rcvr_1", status="running")
        assert task.id == "rcvr_1"
        assert task.status == "running"


# ---------------------------------------------------------------------------
# CreateSubscriptionRequest validation
# ---------------------------------------------------------------------------


class TestCreateSubscriptionRequestValidation:
    """Tests for CreateSubscriptionRequest validation."""

    def test_valid_request(self):
        req = CreateSubscriptionRequest(
            url="https://example.com/hook",
            event_types=["sync.completed", "sync.failed"],
        )
        assert "example.com" in str(req.url)
        assert len(req.event_types) == 2

    def test_empty_event_types_rejected(self):
        with pytest.raises(ValidationError, match="event_types"):
            CreateSubscriptionRequest(
                url="https://example.com/hook",
                event_types=[],
            )

    def test_invalid_event_type_rejected(self):
        with pytest.raises(ValidationError):
            CreateSubscriptionRequest(
                url="https://example.com/hook",
                event_types=["not.a.valid.type"],
            )

    def test_secret_too_short_rejected(self):
        with pytest.raises(ValidationError, match="24"):
            CreateSubscriptionRequest(
                url="https://example.com/hook",
                event_types=["sync.completed"],
                secret="tooshort",
            )

    def test_secret_exactly_24_chars_accepted(self):
        req = CreateSubscriptionRequest(
            url="https://example.com/hook",
            event_types=["sync.completed"],
            secret="a" * 24,
        )
        assert req.secret == "a" * 24

    def test_secret_none_accepted(self):
        req = CreateSubscriptionRequest(
            url="https://example.com/hook",
            event_types=["sync.completed"],
        )
        assert req.secret is None

    def test_invalid_url_rejected(self):
        with pytest.raises(ValidationError):
            CreateSubscriptionRequest(
                url="not-a-url",
                event_types=["sync.completed"],
            )


# ---------------------------------------------------------------------------
# PatchSubscriptionRequest validation
# ---------------------------------------------------------------------------


class TestPatchSubscriptionRequestValidation:
    """Tests for PatchSubscriptionRequest validation."""

    def test_all_fields_optional(self):
        req = PatchSubscriptionRequest()
        assert req.url is None
        assert req.event_types is None
        assert req.disabled is None
        assert req.recover_since is None

    def test_partial_update_url_only(self):
        req = PatchSubscriptionRequest(url="https://new.example.com/hook")
        assert "new.example.com" in str(req.url)
        assert req.disabled is None

    def test_partial_update_disabled_only(self):
        req = PatchSubscriptionRequest(disabled=True)
        assert req.disabled is True
        assert req.url is None

    def test_recover_since_with_reenable(self):
        req = PatchSubscriptionRequest(
            disabled=False,
            recover_since=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )
        assert req.disabled is False
        assert req.recover_since is not None


# ---------------------------------------------------------------------------
# RecoverMessagesRequest validation
# ---------------------------------------------------------------------------


class TestRecoverMessagesRequestValidation:
    """Tests for RecoverMessagesRequest validation."""

    def test_valid_with_since_only(self):
        req = RecoverMessagesRequest(since=datetime(2024, 1, 1, tzinfo=timezone.utc))
        assert req.until is None

    def test_valid_with_since_and_until(self):
        req = RecoverMessagesRequest(
            since=datetime(2024, 1, 1, tzinfo=timezone.utc),
            until=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        assert req.since < req.until

    def test_since_is_required(self):
        with pytest.raises(ValidationError, match="since"):
            RecoverMessagesRequest()
