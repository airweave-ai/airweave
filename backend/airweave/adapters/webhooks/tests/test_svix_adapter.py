"""Unit tests for SvixAdapter class methods.

Mocks the SvixAsync client so we can test the adapter's orchestration
logic (retry, _auto_create_org, error conversion, CRUD methods) without
a running Svix server.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from svix.exceptions import HttpError as SvixHttpError

from airweave.domains.webhooks.types import WebhookPublishError, WebhooksError

NOW = datetime(2024, 3, 15, 9, 0, 0, tzinfo=timezone.utc)
ORG_ID = uuid4()


# ---------------------------------------------------------------------------
# Helpers to build mock Svix SDK return objects
# ---------------------------------------------------------------------------


def _mock_endpoint_out(**overrides):
    """Build a mock EndpointOut returned by Svix SDK."""
    defaults = dict(
        id="ep_123",
        url="https://example.com/hook",
        channels=["sync.completed"],
        disabled=False,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _mock_message_out(**overrides):
    defaults = dict(
        id="msg_456",
        event_type="sync.completed",
        payload={"status": "completed"},
        timestamp=NOW,
        channels=["sync.completed"],
    )
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _mock_attempt_out(**overrides):
    defaults = dict(
        id="atmpt_789",
        msg_id="msg_456",
        endpoint_id="ep_123",
        timestamp=NOW,
        response_status_code=200,
        response='{"ok": true}',
        url="https://example.com/hook",
    )
    defaults.update(overrides)
    m = MagicMock()
    for k, v in defaults.items():
        setattr(m, k, v)
    return m


def _mock_recover_out(status: int = 0):
    m = MagicMock()
    m.id = "rcvr_001"
    m.status = status
    return m


def _make_not_found_error():
    """Create a SvixHttpError with code='not_found'."""
    err = SvixHttpError.__new__(SvixHttpError)
    err.code = "not_found"
    err.detail = "Not found"
    err.status_code = 404
    err.args = ("Not found",)
    return err


def _make_conflict_error():
    err = SvixHttpError.__new__(SvixHttpError)
    err.code = "conflict"
    err.detail = "Already exists"
    err.status_code = 409
    err.args = ("Already exists",)
    return err


def _make_svix_500_error():
    err = SvixHttpError.__new__(SvixHttpError)
    err.code = "internal_error"
    err.detail = "Internal Server Error"
    err.status_code = 500
    err.args = ("Internal Server Error",)
    return err


def _make_svix_validation_error():
    err = SvixHttpError.__new__(SvixHttpError)
    err.code = "validation"
    err.detail = "Invalid URL"
    err.status_code = 422
    err.args = ("Invalid URL",)
    return err


# ---------------------------------------------------------------------------
# Fixture: SvixAdapter with mocked _svix client
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter():
    """Create a SvixAdapter with a fully mocked SvixAsync client.

    Bypasses __init__ which reads settings and creates a real SvixAsync,
    and replaces _svix with a mock that has async sub-clients.
    """
    from airweave.adapters.webhooks.svix import SvixAdapter

    with patch.object(SvixAdapter, "__init__", lambda self: None):
        a = SvixAdapter()

    # Build mock Svix client with async sub-clients
    svix_mock = MagicMock()

    # application
    svix_mock.application.create = AsyncMock()
    svix_mock.application.delete = AsyncMock()

    # endpoint
    svix_mock.endpoint.list = AsyncMock()
    svix_mock.endpoint.get = AsyncMock()
    svix_mock.endpoint.create = AsyncMock()
    svix_mock.endpoint.patch = AsyncMock()
    svix_mock.endpoint.delete = AsyncMock()
    svix_mock.endpoint.get_secret = AsyncMock()
    svix_mock.endpoint.recover = AsyncMock()

    # message
    svix_mock.message.create = AsyncMock()
    svix_mock.message.list = AsyncMock()
    svix_mock.message.get = AsyncMock()

    # message_attempt
    svix_mock.message_attempt.list_by_msg = AsyncMock()
    svix_mock.message_attempt.list_by_endpoint = AsyncMock()

    a._svix = svix_mock
    return a


# ---------------------------------------------------------------------------
# delete_organization
# ---------------------------------------------------------------------------


class TestDeleteOrganization:
    """Tests for SvixAdapter.delete_organization."""

    @pytest.mark.asyncio
    async def test_success(self, adapter):
        await adapter.delete_organization(ORG_ID)
        adapter._svix.application.delete.assert_called_once_with(str(ORG_ID))

    @pytest.mark.asyncio
    async def test_error_is_swallowed(self, adapter):
        """delete_organization is best-effort -- exceptions are logged, not raised."""
        adapter._svix.application.delete.side_effect = RuntimeError("Svix down")
        # Should not raise
        await adapter.delete_organization(ORG_ID)


# ---------------------------------------------------------------------------
# publish_event (retry logic)
# ---------------------------------------------------------------------------


class TestPublishEvent:
    """Tests for SvixAdapter.publish_event retry logic."""

    def _make_event(self):
        """Build a minimal mock DomainEvent."""
        event = MagicMock()
        event.event_type.value = "sync.completed"
        event.organization_id = ORG_ID
        event.model_dump.return_value = {"event_type": "sync.completed"}
        return event

    @pytest.mark.asyncio
    async def test_success_first_attempt(self, adapter):
        """Successful publish on first try -- no retries."""
        event = self._make_event()

        msg_result = MagicMock(id="msg_1", channels=["sync.completed"])
        adapter._svix.message.create = AsyncMock(return_value=msg_result)
        # message.list for the verification step
        list_result = MagicMock(data=[msg_result])
        adapter._svix.message.list = AsyncMock(return_value=list_result)

        await adapter.publish_event(event)
        adapter._svix.message.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_transient_error_fails_immediately(self, adapter):
        """Validation errors (non-transient) should not be retried."""
        event = self._make_event()

        adapter._svix.message.create = AsyncMock(side_effect=_make_svix_validation_error())

        with pytest.raises(WebhookPublishError) as exc_info:
            await adapter.publish_event(event)

        assert exc_info.value.event_type == "sync.completed"
        # Should have been called only once (no retry)
        assert adapter._svix.message.create.call_count == 1

    @pytest.mark.asyncio
    async def test_transient_error_retries_then_succeeds(self, adapter):
        """Transient 500 on first attempt, success on second."""
        event = self._make_event()

        msg_result = MagicMock(id="msg_1", channels=["sync.completed"])
        list_result = MagicMock(data=[msg_result])

        adapter._svix.message.create = AsyncMock(side_effect=[_make_svix_500_error(), msg_result])
        adapter._svix.message.list = AsyncMock(return_value=list_result)

        await adapter.publish_event(event)
        assert adapter._svix.message.create.call_count == 2

    @pytest.mark.asyncio
    async def test_transient_error_exhausts_retries(self, adapter):
        """Three consecutive transient errors exhaust retries -- raises WebhookPublishError."""
        event = self._make_event()

        adapter._svix.message.create = AsyncMock(
            side_effect=[
                _make_svix_500_error(),
                _make_svix_500_error(),
                _make_svix_500_error(),
            ]
        )

        with pytest.raises(WebhookPublishError):
            await adapter.publish_event(event)

        assert adapter._svix.message.create.call_count == 3

    @pytest.mark.asyncio
    async def test_connection_error_retries(self, adapter):
        """ConnectionError is transient and should be retried."""
        event = self._make_event()

        msg_result = MagicMock(id="msg_1", channels=["sync.completed"])
        list_result = MagicMock(data=[msg_result])

        adapter._svix.message.create = AsyncMock(
            side_effect=[ConnectionError("refused"), msg_result]
        )
        adapter._svix.message.list = AsyncMock(return_value=list_result)

        await adapter.publish_event(event)
        assert adapter._svix.message.create.call_count == 2


# ---------------------------------------------------------------------------
# _auto_create_org decorator (tested via _list_endpoints_internal)
# ---------------------------------------------------------------------------


class TestAutoCreateOrg:
    """Tests for the _auto_create_org decorator behavior."""

    @pytest.mark.asyncio
    async def test_auto_creates_org_on_not_found(self, adapter):
        """If endpoint.list returns not_found, auto-create org and retry."""
        ep = _mock_endpoint_out()
        list_result = MagicMock(data=[ep])

        adapter._svix.endpoint.list = AsyncMock(side_effect=[_make_not_found_error(), list_result])

        subs = await adapter.list_subscriptions(ORG_ID)
        assert len(subs) == 1
        adapter._svix.application.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_auto_create_handles_conflict(self, adapter):
        """If auto-create gets conflict (already exists), still retry original call."""
        ep = _mock_endpoint_out()
        list_result = MagicMock(data=[ep])

        adapter._svix.endpoint.list = AsyncMock(side_effect=[_make_not_found_error(), list_result])
        adapter._svix.application.create = AsyncMock(side_effect=_make_conflict_error())

        subs = await adapter.list_subscriptions(ORG_ID)
        assert len(subs) == 1

    @pytest.mark.asyncio
    async def test_auto_create_non_conflict_error_re_raises_original(self, adapter):
        """If auto-create fails with non-conflict error, re-raise the original not_found."""
        adapter._svix.endpoint.list = AsyncMock(side_effect=_make_not_found_error())
        adapter._svix.application.create = AsyncMock(side_effect=RuntimeError("Unexpected error"))

        with pytest.raises(WebhooksError) as exc_info:
            await adapter.list_subscriptions(ORG_ID)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_non_not_found_error_is_not_retried(self, adapter):
        """Errors other than not_found are not caught by _auto_create_org."""
        adapter._svix.endpoint.list = AsyncMock(side_effect=_make_svix_validation_error())

        with pytest.raises(WebhooksError) as exc_info:
            await adapter.list_subscriptions(ORG_ID)
        assert exc_info.value.status_code == 422
        adapter._svix.application.create.assert_not_called()


# ---------------------------------------------------------------------------
# Subscription CRUD
# ---------------------------------------------------------------------------


class TestListSubscriptions:
    @pytest.mark.asyncio
    async def test_returns_domain_subscriptions(self, adapter):
        ep1 = _mock_endpoint_out(id="ep_1", url="https://a.com")
        ep2 = _mock_endpoint_out(id="ep_2", url="https://b.com")
        adapter._svix.endpoint.list = AsyncMock(return_value=MagicMock(data=[ep1, ep2]))

        subs = await adapter.list_subscriptions(ORG_ID)
        assert len(subs) == 2
        assert subs[0].id == "ep_1"
        assert subs[1].url == "https://b.com"

    @pytest.mark.asyncio
    async def test_empty_list(self, adapter):
        adapter._svix.endpoint.list = AsyncMock(return_value=MagicMock(data=[]))
        subs = await adapter.list_subscriptions(ORG_ID)
        assert subs == []

    @pytest.mark.asyncio
    async def test_error_converts_to_webhooks_error(self, adapter):
        adapter._svix.endpoint.list = AsyncMock(side_effect=RuntimeError("Svix unreachable"))
        with pytest.raises(WebhooksError) as exc_info:
            await adapter.list_subscriptions(ORG_ID)
        assert exc_info.value.status_code == 500


class TestGetSubscription:
    @pytest.mark.asyncio
    async def test_returns_domain_subscription(self, adapter):
        ep = _mock_endpoint_out()
        adapter._svix.endpoint.get = AsyncMock(return_value=ep)

        sub = await adapter.get_subscription(ORG_ID, "ep_123")
        assert sub.id == "ep_123"
        assert sub.url == "https://example.com/hook"

    @pytest.mark.asyncio
    async def test_not_found_raises_404(self, adapter):
        adapter._svix.endpoint.get = AsyncMock(side_effect=_make_not_found_error())
        # _auto_create_org will try to create the org then retry
        # The retry will also get not_found -> raises WebhooksError(404)
        adapter._svix.application.create = AsyncMock()

        with pytest.raises(WebhooksError) as exc_info:
            await adapter.get_subscription(ORG_ID, "nonexistent")
        assert exc_info.value.status_code == 404


class TestCreateSubscription:
    @pytest.mark.asyncio
    async def test_returns_domain_subscription(self, adapter):
        ep = _mock_endpoint_out(id="new_ep")
        adapter._svix.endpoint.create = AsyncMock(return_value=ep)

        sub = await adapter.create_subscription(
            ORG_ID, "https://example.com/hook", ["sync.completed"]
        )
        assert sub.id == "new_ep"
        adapter._svix.endpoint.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_with_secret(self, adapter):
        ep = _mock_endpoint_out()
        adapter._svix.endpoint.create = AsyncMock(return_value=ep)

        await adapter.create_subscription(
            ORG_ID,
            "https://example.com/hook",
            ["sync.completed"],
            secret="whsec_test_secret_24chars_min",
        )
        # Verify the EndpointIn was created with the secret
        call_args = adapter._svix.endpoint.create.call_args
        endpoint_in = call_args[0][1]
        assert endpoint_in.secret == "whsec_test_secret_24chars_min"

    @pytest.mark.asyncio
    async def test_validation_error_raises_422(self, adapter):
        adapter._svix.endpoint.create = AsyncMock(side_effect=_make_svix_validation_error())
        with pytest.raises(WebhooksError) as exc_info:
            await adapter.create_subscription(ORG_ID, "bad-url", ["sync.completed"])
        assert exc_info.value.status_code == 422


class TestUpdateSubscription:
    @pytest.mark.asyncio
    async def test_updates_url(self, adapter):
        ep = _mock_endpoint_out(url="https://new.example.com")
        adapter._svix.endpoint.patch = AsyncMock(return_value=ep)

        sub = await adapter.update_subscription(ORG_ID, "ep_123", url="https://new.example.com")
        assert sub.url == "https://new.example.com"
        call_args = adapter._svix.endpoint.patch.call_args
        patch_obj = call_args[0][2]
        assert patch_obj.url == "https://new.example.com"

    @pytest.mark.asyncio
    async def test_updates_disabled(self, adapter):
        ep = _mock_endpoint_out(disabled=True)
        adapter._svix.endpoint.patch = AsyncMock(return_value=ep)

        sub = await adapter.update_subscription(ORG_ID, "ep_123", disabled=True)
        assert sub.disabled is True

    @pytest.mark.asyncio
    async def test_updates_event_types(self, adapter):
        ep = _mock_endpoint_out(channels=["sync.completed", "sync.failed"])
        adapter._svix.endpoint.patch = AsyncMock(return_value=ep)

        sub = await adapter.update_subscription(
            ORG_ID, "ep_123", event_types=["sync.completed", "sync.failed"]
        )
        assert sub.event_types == ["sync.completed", "sync.failed"]

    @pytest.mark.asyncio
    async def test_none_fields_not_included_in_patch(self, adapter):
        """Fields set to None should not appear in the patch data."""
        ep = _mock_endpoint_out()
        adapter._svix.endpoint.patch = AsyncMock(return_value=ep)

        await adapter.update_subscription(ORG_ID, "ep_123")
        call_args = adapter._svix.endpoint.patch.call_args
        patch_obj = call_args[0][2]
        # EndpointPatch was created with no arguments
        assert not hasattr(patch_obj, "url") or patch_obj.url is None


class TestDeleteSubscription:
    @pytest.mark.asyncio
    async def test_success(self, adapter):
        adapter._svix.endpoint.delete = AsyncMock()
        await adapter.delete_subscription(ORG_ID, "ep_123")
        adapter._svix.endpoint.delete.assert_called_once_with(str(ORG_ID), "ep_123")

    @pytest.mark.asyncio
    async def test_not_found_raises_404(self, adapter):
        adapter._svix.endpoint.delete = AsyncMock(side_effect=_make_not_found_error())
        with pytest.raises(WebhooksError) as exc_info:
            await adapter.delete_subscription(ORG_ID, "nonexistent")
        assert exc_info.value.status_code == 404


class TestGetSubscriptionSecret:
    @pytest.mark.asyncio
    async def test_returns_key(self, adapter):
        secret_obj = MagicMock(key="whsec_abc123")
        adapter._svix.endpoint.get_secret = AsyncMock(return_value=secret_obj)

        secret = await adapter.get_subscription_secret(ORG_ID, "ep_123")
        assert secret == "whsec_abc123"


class TestRecoverMessages:
    @pytest.mark.asyncio
    async def test_running_status(self, adapter):
        adapter._svix.endpoint.recover = AsyncMock(return_value=_mock_recover_out(status=0))
        task = await adapter.recover_messages(ORG_ID, "ep_123", since=NOW)
        assert task.id == "rcvr_001"
        assert task.status == "running"

    @pytest.mark.asyncio
    async def test_completed_status(self, adapter):
        adapter._svix.endpoint.recover = AsyncMock(return_value=_mock_recover_out(status=1))
        task = await adapter.recover_messages(ORG_ID, "ep_123", since=NOW)
        assert task.status == "completed"

    @pytest.mark.asyncio
    async def test_unknown_status(self, adapter):
        adapter._svix.endpoint.recover = AsyncMock(return_value=_mock_recover_out(status=99))
        task = await adapter.recover_messages(ORG_ID, "ep_123", since=NOW)
        assert task.status == "unknown"


# ---------------------------------------------------------------------------
# Message history
# ---------------------------------------------------------------------------


class TestGetMessages:
    @pytest.mark.asyncio
    async def test_returns_domain_messages(self, adapter):
        msg = _mock_message_out()
        adapter._svix.message.list = AsyncMock(return_value=MagicMock(data=[msg]))

        messages = await adapter.get_messages(ORG_ID)
        assert len(messages) == 1
        assert messages[0].id == "msg_456"
        assert messages[0].event_type == "sync.completed"

    @pytest.mark.asyncio
    async def test_with_event_type_filter(self, adapter):
        adapter._svix.message.list = AsyncMock(return_value=MagicMock(data=[]))

        await adapter.get_messages(ORG_ID, event_types=["sync.failed"])
        adapter._svix.message.list.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_list(self, adapter):
        adapter._svix.message.list = AsyncMock(return_value=MagicMock(data=[]))
        messages = await adapter.get_messages(ORG_ID)
        assert messages == []


class TestGetMessage:
    @pytest.mark.asyncio
    async def test_returns_domain_message(self, adapter):
        msg = _mock_message_out(id="msg_specific")
        adapter._svix.message.get = AsyncMock(return_value=msg)

        message = await adapter.get_message(ORG_ID, "msg_specific")
        assert message.id == "msg_specific"

    @pytest.mark.asyncio
    async def test_not_found(self, adapter):
        adapter._svix.message.get = AsyncMock(side_effect=_make_not_found_error())
        adapter._svix.application.create = AsyncMock()

        with pytest.raises(WebhooksError) as exc_info:
            await adapter.get_message(ORG_ID, "nonexistent")
        assert exc_info.value.status_code == 404


class TestGetMessageAttempts:
    @pytest.mark.asyncio
    async def test_returns_domain_attempts(self, adapter):
        attempt = _mock_attempt_out()
        adapter._svix.message_attempt.list_by_msg = AsyncMock(
            return_value=MagicMock(data=[attempt])
        )

        attempts = await adapter.get_message_attempts(ORG_ID, "msg_456")
        assert len(attempts) == 1
        assert attempts[0].id == "atmpt_789"
        assert attempts[0].message_id == "msg_456"

    @pytest.mark.asyncio
    async def test_empty(self, adapter):
        adapter._svix.message_attempt.list_by_msg = AsyncMock(return_value=MagicMock(data=[]))
        attempts = await adapter.get_message_attempts(ORG_ID, "msg_456")
        assert attempts == []


class TestGetSubscriptionAttempts:
    @pytest.mark.asyncio
    async def test_returns_domain_attempts(self, adapter):
        attempt = _mock_attempt_out()
        adapter._svix.message_attempt.list_by_endpoint = AsyncMock(
            return_value=MagicMock(data=[attempt])
        )

        attempts = await adapter.get_subscription_attempts(ORG_ID, "ep_123")
        assert len(attempts) == 1

    @pytest.mark.asyncio
    async def test_custom_limit(self, adapter):
        adapter._svix.message_attempt.list_by_endpoint = AsyncMock(return_value=MagicMock(data=[]))

        await adapter.get_subscription_attempts(ORG_ID, "ep_123", limit=5)
        call_args = adapter._svix.message_attempt.list_by_endpoint.call_args
        options = call_args[0][2]
        assert options.limit == 5

    @pytest.mark.asyncio
    async def test_error_converts_to_webhooks_error(self, adapter):
        adapter._svix.message_attempt.list_by_endpoint = AsyncMock(
            side_effect=RuntimeError("connection failed")
        )
        with pytest.raises(WebhooksError) as exc_info:
            await adapter.get_subscription_attempts(ORG_ID, "ep_123")
        assert exc_info.value.status_code == 500
