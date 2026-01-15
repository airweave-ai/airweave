"""Unit tests for WebhooksService.

Tests the webhook service methods with mocked Svix client.
"""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.core.shared_models import SyncJobStatus
from airweave.webhooks.constants.event_types import EventType
from airweave.webhooks.service import (
    WebhooksError,
    WebhooksService,
    generate_org_token,
)


@pytest.fixture
def organization_id():
    """Create a test organization ID."""
    return uuid.uuid4()


@pytest.fixture
def mock_organization(organization_id):
    """Create a mock organization schema."""
    mock = MagicMock()
    mock.id = organization_id
    mock.name = "Test Organization"
    return mock


@pytest.fixture
def mock_sync_job():
    """Create a mock sync job schema."""
    mock = MagicMock()
    mock.id = uuid.uuid4()
    mock.status = SyncJobStatus.COMPLETED
    mock.error = None
    return mock


@pytest.fixture
def mock_collection():
    """Create a mock collection schema."""
    mock = MagicMock()
    mock.readable_id = "test-collection-abc123"
    mock.name = "Test Collection"
    return mock


@pytest.fixture
def mock_svix():
    """Create a mock Svix client."""
    mock = MagicMock()

    # Mock application methods
    mock.application.create = AsyncMock(return_value=None)
    mock.application.delete = AsyncMock(return_value=None)

    # Mock endpoint methods
    mock_endpoint = MagicMock()
    mock_endpoint.id = "ep_test123"
    mock_endpoint.url = "https://example.com/webhook"
    mock_endpoint.channels = ["sync.completed"]

    mock.endpoint.create = AsyncMock(return_value=mock_endpoint)
    mock.endpoint.delete = AsyncMock(return_value=None)
    mock.endpoint.patch = AsyncMock(return_value=mock_endpoint)
    mock.endpoint.get = AsyncMock(return_value=mock_endpoint)
    mock.endpoint.list = AsyncMock(return_value=MagicMock(data=[mock_endpoint]))
    mock.endpoint.get_secret = AsyncMock(
        return_value=MagicMock(key="whsec_test_secret")
    )

    # Mock message methods
    mock_message = MagicMock()
    mock_message.id = "msg_test123"
    mock_message.event_type = "sync.completed"
    mock_message.payload = {"test": "data"}
    mock_message.timestamp = datetime.utcnow()

    mock.message.create = AsyncMock(return_value=mock_message)
    mock.message.get = AsyncMock(return_value=mock_message)
    mock.message.list = AsyncMock(return_value=MagicMock(data=[mock_message]))

    # Mock message_attempt methods
    mock_attempt = MagicMock()
    mock_attempt.id = "atmpt_test123"
    mock_attempt.status = 0  # Success
    mock_attempt.response_status_code = 200
    mock_attempt.timestamp = datetime.utcnow()

    mock.message_attempt.list_by_msg = AsyncMock(return_value=MagicMock(data=[mock_attempt]))
    mock.message_attempt.list_by_endpoint = AsyncMock(
        return_value=MagicMock(data=[mock_attempt])
    )

    return mock


@pytest.fixture
def webhooks_service(mock_svix):
    """Create a webhooks service with mocked Svix client."""
    with patch("airweave.webhooks.service.SvixAsync", return_value=mock_svix):
        service = WebhooksService()
        service.svix = mock_svix
        return service


class TestGenerateOrgToken:
    """Tests for JWT token generation."""

    def test_generate_org_token_returns_string(self):
        """Test that generate_org_token returns a JWT string."""
        token = generate_org_token("test_secret")
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_org_token_is_valid_jwt(self):
        """Test that generated token is a valid JWT format."""
        import jwt

        secret = "test_secret_key"
        token = generate_org_token(secret)

        # Should be decodable
        decoded = jwt.decode(token, secret, algorithms=["HS256"])
        assert "iat" in decoded
        assert "exp" in decoded
        assert "nbf" in decoded
        assert decoded["iss"] == "svix-server"

    def test_generate_org_token_expiry(self):
        """Test that token has expected 10-year expiry."""
        import jwt
        import time

        secret = "test_secret_key"
        token = generate_org_token(secret)
        decoded = jwt.decode(token, secret, algorithms=["HS256"])

        # Should expire ~10 years from now
        expected_duration = 24 * 365 * 10 * 60 * 60  # 10 years in seconds
        actual_duration = decoded["exp"] - decoded["iat"]
        assert actual_duration == expected_duration


class TestWebhooksServiceOrganization:
    """Tests for organization management."""

    @pytest.mark.asyncio
    async def test_create_organization(self, webhooks_service, mock_organization, mock_svix):
        """Test creating an organization in Svix."""
        await webhooks_service.create_organization(mock_organization)

        mock_svix.application.create.assert_called_once()
        call_args = mock_svix.application.create.call_args
        assert call_args[0][0].name == mock_organization.name
        assert call_args[0][0].uid == str(mock_organization.id)

    @pytest.mark.asyncio
    async def test_delete_organization(self, webhooks_service, mock_organization, mock_svix):
        """Test deleting an organization from Svix."""
        await webhooks_service.delete_organization(mock_organization)

        mock_svix.application.delete.assert_called_once_with(mock_organization.id)

    @pytest.mark.asyncio
    async def test_delete_organization_handles_error(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test that delete_organization handles errors gracefully."""
        mock_svix.application.delete.side_effect = Exception("Not found")

        # Should not raise
        await webhooks_service.delete_organization(mock_organization)


class TestWebhooksServiceEndpoints:
    """Tests for endpoint (subscription) management."""

    @pytest.mark.asyncio
    async def test_create_endpoint_success(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test creating a webhook endpoint successfully."""
        url = "https://example.com/webhook"
        event_types = [EventType.SYNC_COMPLETED]

        endpoint, error = await webhooks_service.create_endpoint(
            mock_organization, url, event_types
        )

        assert endpoint is not None
        assert error is None
        mock_svix.endpoint.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_endpoint_with_secret(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test creating an endpoint with custom secret."""
        url = "https://example.com/webhook"
        secret = "whsec_custom_secret"

        endpoint, error = await webhooks_service.create_endpoint(
            mock_organization, url, secret=secret
        )

        assert endpoint is not None
        assert error is None
        call_args = mock_svix.endpoint.create.call_args
        assert call_args[0][1].secret == secret

    @pytest.mark.asyncio
    async def test_create_endpoint_failure(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test endpoint creation failure returns error."""
        mock_svix.endpoint.create.side_effect = Exception("Connection failed")

        endpoint, error = await webhooks_service.create_endpoint(
            mock_organization, "https://example.com/webhook"
        )

        assert endpoint is None
        assert error is not None
        assert isinstance(error, WebhooksError)
        assert "Failed to create endpoint" in error.message

    @pytest.mark.asyncio
    async def test_delete_endpoint_success(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test deleting a webhook endpoint."""
        error = await webhooks_service.delete_endpoint(mock_organization, "ep_test123")

        assert error is None
        mock_svix.endpoint.delete.assert_called_once_with(
            mock_organization.id, "ep_test123"
        )

    @pytest.mark.asyncio
    async def test_delete_endpoint_failure(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test endpoint deletion failure returns error."""
        mock_svix.endpoint.delete.side_effect = Exception("Not found")

        error = await webhooks_service.delete_endpoint(mock_organization, "ep_test123")

        assert error is not None
        assert "Failed to delete endpoint" in error.message

    @pytest.mark.asyncio
    async def test_patch_endpoint_success(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test updating a webhook endpoint."""
        new_url = "https://newexample.com/webhook"
        new_event_types = [EventType.SYNC_FAILED]

        endpoint, error = await webhooks_service.patch_endpoint(
            mock_organization, "ep_test123", url=new_url, event_types=new_event_types
        )

        assert endpoint is not None
        assert error is None
        mock_svix.endpoint.patch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_endpoints_success(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test getting all endpoints for an organization."""
        endpoints, error = await webhooks_service.get_endpoints(mock_organization)

        assert endpoints is not None
        assert error is None
        assert len(endpoints) == 1
        mock_svix.endpoint.list.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_endpoint_success(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test getting a specific endpoint."""
        endpoint, error = await webhooks_service.get_endpoint(
            mock_organization, "ep_test123"
        )

        assert endpoint is not None
        assert error is None
        mock_svix.endpoint.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_endpoint_secret(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test getting endpoint signing secret."""
        secret, error = await webhooks_service.get_endpoint_secret(
            mock_organization, "ep_test123"
        )

        assert secret is not None
        assert error is None
        assert secret.key == "whsec_test_secret"


class TestWebhooksServicePublishEvent:
    """Tests for event publishing."""

    @pytest.mark.asyncio
    async def test_publish_event_sync_completed(
        self,
        webhooks_service,
        mock_organization,
        mock_sync_job,
        mock_collection,
        mock_svix,
    ):
        """Test publishing a completed sync event."""
        source_connection_id = uuid.uuid4()
        mock_sync_job.status = SyncJobStatus.COMPLETED

        await webhooks_service.publish_event_sync(
            source_connection_id=source_connection_id,
            organisation=mock_organization,
            sync_job=mock_sync_job,
            collection=mock_collection,
            source_type="slack",
        )

        mock_svix.message.create.assert_called_once()
        call_args = mock_svix.message.create.call_args
        message_in = call_args[0][1]
        assert message_in.event_type == EventType.SYNC_COMPLETED
        assert "sync.completed" in message_in.channels

    @pytest.mark.asyncio
    async def test_publish_event_sync_failed_with_error(
        self,
        webhooks_service,
        mock_organization,
        mock_sync_job,
        mock_collection,
        mock_svix,
    ):
        """Test publishing a failed sync event includes error message."""
        source_connection_id = uuid.uuid4()
        mock_sync_job.status = SyncJobStatus.FAILED
        mock_sync_job.error = "Authentication failed"

        await webhooks_service.publish_event_sync(
            source_connection_id=source_connection_id,
            organisation=mock_organization,
            sync_job=mock_sync_job,
            collection=mock_collection,
            source_type="notion",
            error="Custom error message",
        )

        mock_svix.message.create.assert_called_once()
        call_args = mock_svix.message.create.call_args
        message_in = call_args[0][1]
        payload = message_in.payload
        assert payload["error"] == "Custom error message"

    @pytest.mark.asyncio
    async def test_publish_event_sync_running(
        self,
        webhooks_service,
        mock_organization,
        mock_sync_job,
        mock_collection,
        mock_svix,
    ):
        """Test publishing a running sync event."""
        source_connection_id = uuid.uuid4()
        mock_sync_job.status = SyncJobStatus.RUNNING

        await webhooks_service.publish_event_sync(
            source_connection_id=source_connection_id,
            organisation=mock_organization,
            sync_job=mock_sync_job,
            collection=mock_collection,
            source_type="asana",
        )

        mock_svix.message.create.assert_called_once()
        call_args = mock_svix.message.create.call_args
        message_in = call_args[0][1]
        assert message_in.event_type == EventType.SYNC_RUNNING
        assert "sync.running" in message_in.channels

    @pytest.mark.asyncio
    async def test_publish_event_sync_pending(
        self,
        webhooks_service,
        mock_organization,
        mock_sync_job,
        mock_collection,
        mock_svix,
    ):
        """Test publishing a pending sync event."""
        source_connection_id = uuid.uuid4()
        mock_sync_job.status = SyncJobStatus.PENDING

        await webhooks_service.publish_event_sync(
            source_connection_id=source_connection_id,
            organisation=mock_organization,
            sync_job=mock_sync_job,
            collection=mock_collection,
            source_type="notion",
        )

        mock_svix.message.create.assert_called_once()
        call_args = mock_svix.message.create.call_args
        message_in = call_args[0][1]
        assert message_in.event_type == EventType.SYNC_PENDING

    @pytest.mark.asyncio
    async def test_publish_event_sync_cancelled(
        self,
        webhooks_service,
        mock_organization,
        mock_sync_job,
        mock_collection,
        mock_svix,
    ):
        """Test publishing a cancelled sync event."""
        source_connection_id = uuid.uuid4()
        mock_sync_job.status = SyncJobStatus.CANCELLED

        await webhooks_service.publish_event_sync(
            source_connection_id=source_connection_id,
            organisation=mock_organization,
            sync_job=mock_sync_job,
            collection=mock_collection,
            source_type="jira",
        )

        mock_svix.message.create.assert_called_once()
        call_args = mock_svix.message.create.call_args
        message_in = call_args[0][1]
        assert message_in.event_type == EventType.SYNC_CANCELLED

    @pytest.mark.asyncio
    async def test_publish_event_sync_skips_created_status(
        self,
        webhooks_service,
        mock_organization,
        mock_sync_job,
        mock_collection,
        mock_svix,
    ):
        """Test that CREATED status does not trigger a webhook."""
        source_connection_id = uuid.uuid4()
        mock_sync_job.status = SyncJobStatus.CREATED

        await webhooks_service.publish_event_sync(
            source_connection_id=source_connection_id,
            organisation=mock_organization,
            sync_job=mock_sync_job,
            collection=mock_collection,
            source_type="jira",
        )

        mock_svix.message.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_event_sync_skips_cancelling_status(
        self,
        webhooks_service,
        mock_organization,
        mock_sync_job,
        mock_collection,
        mock_svix,
    ):
        """Test that CANCELLING status does not trigger a webhook."""
        source_connection_id = uuid.uuid4()
        mock_sync_job.status = SyncJobStatus.CANCELLING

        await webhooks_service.publish_event_sync(
            source_connection_id=source_connection_id,
            organisation=mock_organization,
            sync_job=mock_sync_job,
            collection=mock_collection,
            source_type="confluence",
        )

        mock_svix.message.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_publish_event_handles_svix_error(
        self,
        webhooks_service,
        mock_organization,
        mock_sync_job,
        mock_collection,
        mock_svix,
    ):
        """Test that publish event handles Svix errors gracefully."""
        source_connection_id = uuid.uuid4()
        mock_sync_job.status = SyncJobStatus.COMPLETED
        mock_svix.message.create.side_effect = Exception("Svix error")

        # Should not raise
        await webhooks_service.publish_event_sync(
            source_connection_id=source_connection_id,
            organisation=mock_organization,
            sync_job=mock_sync_job,
            collection=mock_collection,
            source_type="hubspot",
        )


class TestWebhooksServiceMessages:
    """Tests for message retrieval."""

    @pytest.mark.asyncio
    async def test_get_messages_success(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test getting messages for an organization."""
        messages, error = await webhooks_service.get_messages(mock_organization)

        assert messages is not None
        assert error is None
        assert len(messages) == 1
        mock_svix.message.list.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_messages_with_event_type_filter(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test getting messages filtered by event type."""
        messages, error = await webhooks_service.get_messages(
            mock_organization, event_types=["sync.completed", "sync.failed"]
        )

        assert messages is not None
        assert error is None
        call_args = mock_svix.message.list.call_args
        options = call_args[0][1]
        assert options.event_types == ["sync.completed", "sync.failed"]

    @pytest.mark.asyncio
    async def test_get_message_success(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test getting a specific message."""
        message, error = await webhooks_service.get_message(
            mock_organization, "msg_test123"
        )

        assert message is not None
        assert error is None
        mock_svix.message.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_message_attempts_by_message(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test getting delivery attempts for a message."""
        attempts, error = await webhooks_service.get_message_attempts_by_message(
            mock_organization, "msg_test123"
        )

        assert attempts is not None
        assert error is None
        assert len(attempts) == 1
        mock_svix.message_attempt.list_by_msg.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_message_attempts_by_endpoint(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test getting delivery attempts for an endpoint."""
        attempts, error = await webhooks_service.get_message_attempts_by_endpoint(
            mock_organization, "ep_test123", limit=50
        )

        assert attempts is not None
        assert error is None
        assert len(attempts) == 1
        mock_svix.message_attempt.list_by_endpoint.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_message_attempts(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test getting all message attempts across endpoints."""
        attempts, error = await webhooks_service.get_all_message_attempts(
            mock_organization
        )

        assert attempts is not None
        assert error is None
        # Should get endpoints first, then attempts for each
        mock_svix.endpoint.list.assert_called()
        mock_svix.message_attempt.list_by_endpoint.assert_called()

    @pytest.mark.asyncio
    async def test_get_all_message_attempts_with_status_filter(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test getting message attempts filtered by status."""
        attempts, error = await webhooks_service.get_all_message_attempts(
            mock_organization, status="succeeded"
        )

        assert attempts is not None
        assert error is None

    @pytest.mark.asyncio
    async def test_get_all_message_attempts_empty_endpoints(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test that empty endpoints returns empty attempts."""
        mock_svix.endpoint.list.return_value = MagicMock(data=[])

        attempts, error = await webhooks_service.get_all_message_attempts(
            mock_organization
        )

        assert attempts == []
        assert error is None


class TestAutoCreateOrgDecorator:
    """Tests for the auto_create_org_on_not_found decorator."""

    @pytest.mark.asyncio
    async def test_decorator_creates_org_on_not_found(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test that decorator creates org when not_found error occurs."""
        # First call fails with not_found, second succeeds
        not_found_error = Exception("not_found")
        not_found_error.code = "not_found"

        mock_endpoint = MagicMock()
        mock_endpoint.id = "ep_created"
        mock_svix.endpoint.list.side_effect = [
            not_found_error,
            MagicMock(data=[mock_endpoint]),
        ]

        endpoints, error = await webhooks_service.get_endpoints(mock_organization)

        # Should have called application.create to create the org
        mock_svix.application.create.assert_called_once()
        assert endpoints is not None

    @pytest.mark.asyncio
    async def test_decorator_raises_on_other_errors(
        self, webhooks_service, mock_organization, mock_svix
    ):
        """Test that decorator raises non-not_found errors."""
        other_error = Exception("Server error")
        other_error.code = "server_error"
        mock_svix.endpoint.list.side_effect = other_error

        endpoints, error = await webhooks_service.get_endpoints(mock_organization)

        assert endpoints is None
        assert error is not None


class TestWebhooksError:
    """Tests for WebhooksError class."""

    def test_webhooks_error_stores_message(self):
        """Test that WebhooksError stores the error message."""
        error = WebhooksError("Test error message")
        assert error.message == "Test error message"

    def test_webhooks_error_with_empty_message(self):
        """Test WebhooksError with empty message."""
        error = WebhooksError("")
        assert error.message == ""
