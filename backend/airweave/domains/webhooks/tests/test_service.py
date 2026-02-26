"""Unit tests for WebhookServiceImpl.

Uses FakeWebhookAdmin + FakeEndpointVerifier to test the service's
orchestration logic (health computation, verify-then-create, update-with-
recovery, delete-then-return) without touching any infrastructure.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from airweave.adapters.webhooks.fake import FakeEndpointVerifier, FakeWebhookAdmin
from airweave.domains.webhooks.service import WebhookServiceImpl
from airweave.domains.webhooks.types import (
    HealthStatus,
    WebhooksError,
)

ORG_ID = uuid4()
NOW = datetime.now(timezone.utc)


@pytest.fixture
def admin() -> FakeWebhookAdmin:
    return FakeWebhookAdmin()


@pytest.fixture
def verifier() -> FakeEndpointVerifier:
    return FakeEndpointVerifier()


@pytest.fixture
def service(admin, verifier) -> WebhookServiceImpl:
    """Service with endpoint verification enabled (default)."""
    return WebhookServiceImpl(
        webhook_admin=admin, endpoint_verifier=verifier, verify_endpoints=True
    )


@pytest.fixture
def service_no_verify(admin, verifier) -> WebhookServiceImpl:
    """Service with endpoint verification disabled."""
    return WebhookServiceImpl(
        webhook_admin=admin, endpoint_verifier=verifier, verify_endpoints=False
    )


async def _create_sub(admin, url="https://example.com/hook", event_types=None):
    """Helper to create a subscription directly on the fake admin."""
    return await admin.create_subscription(
        ORG_ID, url, event_types or ["sync.completed"], secret=None
    )


# ---------------------------------------------------------------------------
# list_subscriptions_with_health
# ---------------------------------------------------------------------------


class TestListSubscriptionsWithHealth:
    """Tests for list_subscriptions_with_health."""

    @pytest.mark.asyncio
    async def test_empty_list(self, service):
        result = await service.list_subscriptions_with_health(ORG_ID)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_subscriptions_with_unknown_health(self, service, admin):
        """FakeWebhookAdmin returns no attempts, so health should be 'unknown'."""
        await _create_sub(admin)
        result = await service.list_subscriptions_with_health(ORG_ID)
        assert len(result) == 1
        sub, health, attempts = result[0]
        assert sub.url == "https://example.com/hook"
        assert health is HealthStatus.unknown
        assert attempts == []

    @pytest.mark.asyncio
    async def test_multiple_subscriptions(self, service, admin):
        await _create_sub(admin, url="https://a.com/hook")
        await _create_sub(admin, url="https://b.com/hook")
        result = await service.list_subscriptions_with_health(ORG_ID)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_exception_on_attempts_yields_unknown(self, service, admin):
        """If fetching attempts for a sub fails, that sub gets unknown health."""
        sub = await _create_sub(admin)

        # Monkey-patch to raise on get_subscription_attempts
        original = admin.get_subscription_attempts

        async def failing_attempts(*args, **kwargs):
            raise WebhooksError("Svix error", 500)

        admin.get_subscription_attempts = failing_attempts

        result = await service.list_subscriptions_with_health(ORG_ID)
        assert len(result) == 1
        _, health, attempts = result[0]
        assert health is HealthStatus.unknown
        assert attempts == []

        admin.get_subscription_attempts = original


# ---------------------------------------------------------------------------
# get_subscription_detail
# ---------------------------------------------------------------------------


class TestGetSubscriptionDetail:
    """Tests for get_subscription_detail."""

    @pytest.mark.asyncio
    async def test_without_secret(self, service, admin):
        sub = await _create_sub(admin)
        result_sub, attempts, secret = await service.get_subscription_detail(
            ORG_ID, sub.id, include_secret=False
        )
        assert result_sub.id == sub.id
        assert attempts == []
        assert secret is None

    @pytest.mark.asyncio
    async def test_with_secret(self, service, admin):
        sub = await _create_sub(admin)
        _, _, secret = await service.get_subscription_detail(ORG_ID, sub.id, include_secret=True)
        assert secret is not None


# ---------------------------------------------------------------------------
# create_subscription
# ---------------------------------------------------------------------------


class TestCreateSubscription:
    """Tests for create_subscription."""

    @pytest.mark.asyncio
    async def test_creates_with_verification(self, service, admin, verifier):
        sub = await service.create_subscription(
            ORG_ID, "https://example.com/hook", ["sync.completed"]
        )
        assert sub.url == "https://example.com/hook"
        assert "https://example.com/hook" in verifier.verified_urls
        admin.assert_subscription_created("https://example.com/hook")

    @pytest.mark.asyncio
    async def test_creates_without_verification(self, service_no_verify, admin, verifier):
        sub = await service_no_verify.create_subscription(
            ORG_ID, "https://example.com/hook", ["sync.completed"]
        )
        assert sub.url == "https://example.com/hook"
        assert verifier.verified_urls == []

    @pytest.mark.asyncio
    async def test_verification_failure_prevents_creation(self, service, admin, verifier):
        verifier.should_fail = True
        with pytest.raises(WebhooksError, match="Simulated"):
            await service.create_subscription(
                ORG_ID, "https://unreachable.example.com", ["sync.completed"]
            )
        assert len(admin.subscriptions) == 0

    @pytest.mark.asyncio
    async def test_creates_with_custom_secret(self, service, admin, verifier):
        sub = await service.create_subscription(
            ORG_ID,
            "https://example.com/hook",
            ["sync.completed"],
            secret="whsec_test_secret_value_24chars",
        )
        assert sub.secret == "whsec_test_secret_value_24chars"

    @pytest.mark.asyncio
    async def test_creates_with_multiple_event_types(self, service, admin, verifier):
        sub = await service.create_subscription(
            ORG_ID,
            "https://example.com/hook",
            ["sync.completed", "sync.failed", "collection.created"],
        )
        assert set(sub.event_types) == {"sync.completed", "sync.failed", "collection.created"}


# ---------------------------------------------------------------------------
# update_subscription
# ---------------------------------------------------------------------------


class TestUpdateSubscription:
    """Tests for update_subscription."""

    @pytest.mark.asyncio
    async def test_basic_update(self, service, admin):
        sub = await _create_sub(admin)
        updated = await service.update_subscription(
            ORG_ID, sub.id, url="https://new.example.com/hook"
        )
        assert updated.url == "https://new.example.com/hook"

    @pytest.mark.asyncio
    async def test_disable_subscription(self, service, admin):
        sub = await _create_sub(admin)
        updated = await service.update_subscription(ORG_ID, sub.id, disabled=True)
        assert updated.disabled is True

    @pytest.mark.asyncio
    async def test_reenable_with_recovery(self, service, admin):
        sub = await _create_sub(admin)
        await service.update_subscription(ORG_ID, sub.id, disabled=True)

        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        updated = await service.update_subscription(
            ORG_ID, sub.id, disabled=False, recover_since=since
        )
        assert updated.disabled is False
        # Verify recovery was triggered
        assert len(admin.recovered) == 1
        assert admin.recovered[0] == (ORG_ID, sub.id, since)

    @pytest.mark.asyncio
    async def test_reenable_recovery_failure_is_swallowed(self, service, admin):
        """If recovery fails, update still succeeds."""
        sub = await _create_sub(admin)

        # Monkey-patch to fail
        original = admin.recover_messages

        async def failing_recover(*args, **kwargs):
            raise WebhooksError("recovery failed", 500)

        admin.recover_messages = failing_recover

        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        updated = await service.update_subscription(
            ORG_ID, sub.id, disabled=False, recover_since=since
        )
        assert updated.disabled is False

        admin.recover_messages = original

    @pytest.mark.asyncio
    async def test_no_recovery_when_not_reenabling(self, service, admin):
        """Recovery should only trigger when disabled=False."""
        sub = await _create_sub(admin)
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)

        # disabled=None means we're not changing it, just updating URL
        await service.update_subscription(
            ORG_ID, sub.id, url="https://new.example.com", recover_since=since
        )
        assert len(admin.recovered) == 0

    @pytest.mark.asyncio
    async def test_no_recovery_when_disabling(self, service, admin):
        """Recovery should only trigger when disabled=False, not disabled=True."""
        sub = await _create_sub(admin)
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)

        await service.update_subscription(ORG_ID, sub.id, disabled=True, recover_since=since)
        assert len(admin.recovered) == 0


# ---------------------------------------------------------------------------
# delete_subscription
# ---------------------------------------------------------------------------


class TestDeleteSubscription:
    """Tests for delete_subscription."""

    @pytest.mark.asyncio
    async def test_returns_subscription_before_deletion(self, service, admin):
        sub = await _create_sub(admin)
        deleted = await service.delete_subscription(ORG_ID, sub.id)
        assert deleted.id == sub.id
        assert deleted.url == sub.url

    @pytest.mark.asyncio
    async def test_subscription_is_actually_removed(self, service, admin):
        sub = await _create_sub(admin)
        await service.delete_subscription(ORG_ID, sub.id)
        assert sub.id not in admin.subscriptions

    @pytest.mark.asyncio
    async def test_delete_nonexistent_raises(self, service, admin):
        with pytest.raises(KeyError):
            await service.delete_subscription(ORG_ID, "nonexistent-id")


# ---------------------------------------------------------------------------
# Messages (pass-through)
# ---------------------------------------------------------------------------


class TestMessages:
    """Tests for message pass-through methods."""

    @pytest.mark.asyncio
    async def test_get_messages_empty(self, service):
        messages = await service.get_messages(ORG_ID)
        assert messages == []

    @pytest.mark.asyncio
    async def test_get_messages_with_filter(self, service, admin):
        from airweave.domains.webhooks.types import EventMessage

        admin.messages.append(
            EventMessage(
                id="msg_1",
                event_type="sync.completed",
                payload={"key": "value"},
                timestamp=NOW,
            )
        )
        admin.messages.append(
            EventMessage(
                id="msg_2",
                event_type="sync.failed",
                payload={"key": "value"},
                timestamp=NOW,
            )
        )

        result = await service.get_messages(ORG_ID, event_types=["sync.completed"])
        assert len(result) == 1
        assert result[0].id == "msg_1"

    @pytest.mark.asyncio
    async def test_get_message_by_id(self, service, admin):
        from airweave.domains.webhooks.types import EventMessage

        admin.messages.append(
            EventMessage(
                id="msg_1",
                event_type="sync.completed",
                payload={"data": 42},
                timestamp=NOW,
            )
        )
        msg = await service.get_message(ORG_ID, "msg_1")
        assert msg.id == "msg_1"
        assert msg.payload == {"data": 42}

    @pytest.mark.asyncio
    async def test_get_message_attempts(self, service):
        attempts = await service.get_message_attempts(ORG_ID, "msg_1")
        assert attempts == []


# ---------------------------------------------------------------------------
# Recovery
# ---------------------------------------------------------------------------


class TestRecovery:
    """Tests for recover_messages."""

    @pytest.mark.asyncio
    async def test_recover_messages_delegates(self, service, admin):
        sub = await _create_sub(admin)
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        task = await service.recover_messages(ORG_ID, sub.id, since=since)
        assert task.status == "completed"
        assert len(admin.recovered) == 1

    @pytest.mark.asyncio
    async def test_recover_messages_with_until(self, service, admin):
        sub = await _create_sub(admin)
        since = datetime(2024, 1, 1, tzinfo=timezone.utc)
        until = datetime(2024, 2, 1, tzinfo=timezone.utc)
        task = await service.recover_messages(ORG_ID, sub.id, since=since, until=until)
        assert task.id  # Has an ID
        assert task.status == "completed"
