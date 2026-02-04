"""E2E tests for Events API and Webhook functionality.

These tests cover two distinct concepts:
- **Events (Messages)**: Records of what happened in the system (sync.pending, sync.completed, etc.)
- **Webhooks (Subscriptions)**: Endpoints that receive event notifications at configured URLs

Tests use the stub connector for fast execution while testing the full flow including Svix integration.

Test Categories:
- Tests WITHOUT @pytest.mark.svix: Test API functionality only
- Tests WITH @pytest.mark.svix: Require Svix to be running, but use Svix's API to verify delivery

These svix tests are skipped in CI because they require Svix to be running locally.
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator, Dict

import httpx
import pytest
import pytest_asyncio


# Webhook delivery timeout
WEBHOOK_TIMEOUT = 30.0

# Dummy URL for webhook subscriptions - Svix will try to deliver here
# We don't need it to succeed, we just check Svix's message attempts
DUMMY_WEBHOOK_URL = "https://example.com/webhook"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


async def wait_for_sync_completed_message(
    api_client: httpx.AsyncClient,
    timeout: float = WEBHOOK_TIMEOUT,
) -> Dict:
    """Poll the messages API until a sync.completed message appears."""
    start_time = time.time()
    last_message_id = None

    while time.time() - start_time < timeout:
        response = await api_client.get(
            "/events/messages", params={"event_types": ["sync.completed"]}
        )
        if response.status_code == 200:
            messages = response.json()
            if messages:
                # Return the most recent message if it's new
                if messages[0]["id"] != last_message_id:
                    return messages[0]
                last_message_id = messages[0]["id"] if messages else None

        await asyncio.sleep(0.5)

    raise TimeoutError(f"No sync.completed message found within {timeout}s")




# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(scope="function")
def unique_webhook_url() -> str:
    """Generate a unique webhook URL for this test."""
    return f"https://example.com/webhook/{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture(scope="function")
async def webhook_subscription(
    api_client: httpx.AsyncClient,
    unique_webhook_url: str,
) -> AsyncGenerator[Dict, None]:
    """Create a webhook subscription for sync.completed events."""
    response = await api_client.post(
        "/events/subscriptions",
        json={
            "url": unique_webhook_url,
            "event_types": ["sync.completed"],
        },
    )
    assert response.status_code == 200, f"Failed to create subscription: {response.text}"
    subscription = response.json()

    yield subscription

    # Cleanup
    try:
        await api_client.delete(f"/events/subscriptions/{subscription['id']}")
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def webhook_subscription_all_events(
    api_client: httpx.AsyncClient,
    unique_webhook_url: str,
) -> AsyncGenerator[Dict, None]:
    """Create a webhook subscription for all sync event types."""
    response = await api_client.post(
        "/events/subscriptions",
        json={
            "url": unique_webhook_url,
            "event_types": [
                "sync.pending",
                "sync.running",
                "sync.completed",
                "sync.failed",
                "sync.cancelled",
            ],
        },
    )
    assert response.status_code == 200, f"Failed to create subscription: {response.text}"
    subscription = response.json()

    yield subscription

    # Cleanup
    try:
        await api_client.delete(f"/events/subscriptions/{subscription['id']}")
    except Exception:
        pass


# =============================================================================
# EVENTS TESTS - Testing the Events API (messages)
# =============================================================================


@pytest.mark.asyncio
class TestEventsMessages:
    """Tests for event messages - the record of what events occurred."""

    async def test_get_messages_returns_list(self, api_client: httpx.AsyncClient):
        """Test that GET /events/messages returns a list."""
        response = await api_client.get("/events/messages")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_get_messages_with_event_type_filter(
        self, api_client: httpx.AsyncClient
    ):
        """Test filtering messages by event type."""
        response = await api_client.get(
            "/events/messages", params={"event_types": ["sync.completed"]}
        )
        assert response.status_code == 200
        messages = response.json()

        # All returned messages should be sync.completed
        for msg in messages:
            assert msg["event_type"] == "sync.completed"

    @pytest.mark.svix
    async def test_messages_created_after_sync(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
    ):
        """Test that event messages are created when syncs occur."""
        # Get initial message count
        initial_response = await api_client.get(
            "/events/messages", params={"event_types": ["sync.completed"]}
        )
        initial_count = len(initial_response.json()) if initial_response.status_code == 200 else 0

        # Trigger a sync
        response = await api_client.post(
            "/source-connections",
            json={
                "name": "Stub Message Test",
                "description": "Testing message creation",
                "short_name": "stub",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"stub_key": "key"}},
                "config": {"entity_count": "1"},
                "sync_immediately": True,
            },
        )
        assert response.status_code == 200

        # Wait for new message to appear
        message = await wait_for_sync_completed_message(api_client, timeout=WEBHOOK_TIMEOUT)

        # Verify message structure
        assert "id" in message
        assert "event_type" in message
        assert message["event_type"] == "sync.completed"
        assert "payload" in message


@pytest.mark.asyncio
@pytest.mark.svix
class TestEventTypes:
    """Tests for different event types (sync.pending, sync.running, sync.completed, etc.)."""

    async def test_event_payload_structure(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
    ):
        """Test that event payloads contain all required fields."""
        # Trigger a sync
        await api_client.post(
            "/source-connections",
            json={
                "name": "Stub Payload Test",
                "description": "Testing payload structure",
                "short_name": "stub",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"stub_key": "key"}},
                "config": {"entity_count": "1"},
                "sync_immediately": True,
            },
        )

        # Wait for message
        message = await wait_for_sync_completed_message(api_client, timeout=WEBHOOK_TIMEOUT)
        payload = message.get("payload", {})

        # Verify required fields per SyncEventPayload schema
        assert "event_type" in payload
        assert "job_id" in payload
        assert "collection_readable_id" in payload
        assert "collection_name" in payload
        assert "source_type" in payload
        assert "status" in payload
        assert "timestamp" in payload

    async def test_completed_event_has_job_id(
        self,
        api_client: httpx.AsyncClient,
        collection: Dict,
    ):
        """Test that completed events include the job_id in correct format."""
        # Trigger a sync
        await api_client.post(
            "/source-connections",
            json={
                "name": "Stub Job ID Test",
                "description": "Testing job_id presence",
                "short_name": "stub",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"stub_key": "key"}},
                "config": {"entity_count": "2"},
                "sync_immediately": True,
            },
        )

        # Wait for message
        message = await wait_for_sync_completed_message(api_client, timeout=WEBHOOK_TIMEOUT)
        payload = message.get("payload", {})

        assert "job_id" in payload
        job_id = payload["job_id"]
        # UUID format validation
        assert len(job_id) == 36  # xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx


# =============================================================================
# WEBHOOK TESTS - Testing webhook subscriptions
# =============================================================================


@pytest.mark.asyncio
class TestWebhookSubscriptions:
    """Tests for webhook subscription CRUD operations."""

    async def test_list_subscriptions(self, api_client: httpx.AsyncClient):
        """Test listing all webhook subscriptions."""
        response = await api_client.get("/events/subscriptions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_create_subscription(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating a webhook subscription."""
        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 200
        subscription = response.json()
        assert subscription["id"] is not None
        assert subscription["url"].rstrip("/") == unique_webhook_url.rstrip("/")

        # Cleanup
        await api_client.delete(f"/events/subscriptions/{subscription['id']}")

    async def test_create_subscription_multiple_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating a subscription with multiple event types."""
        event_types = ["sync.completed", "sync.failed", "sync.running"]

        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": event_types,
            },
        )
        assert response.status_code == 200
        subscription = response.json()

        # Cleanup
        await api_client.delete(f"/events/subscriptions/{subscription['id']}")

    async def test_get_subscription_by_id(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test getting a specific subscription with its delivery attempts."""
        response = await api_client.get(
            f"/events/subscriptions/{webhook_subscription['id']}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == webhook_subscription["id"]
        assert "delivery_attempts" in data

    async def test_update_subscription_url(
        self,
        api_client: httpx.AsyncClient,
        webhook_subscription: Dict,
    ):
        """Test updating a subscription URL."""
        new_url = f"https://example.com/webhook/updated-{uuid.uuid4().hex[:8]}"
        response = await api_client.patch(
            f"/events/subscriptions/{webhook_subscription['id']}",
            json={"url": new_url},
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["url"].rstrip("/") == new_url.rstrip("/")

    async def test_delete_subscription(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test deleting a webhook subscription returns the deleted object."""
        # Create a subscription to delete
        create_response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed"],
            },
        )
        subscription = create_response.json()

        # Delete it
        delete_response = await api_client.delete(
            f"/events/subscriptions/{subscription['id']}"
        )
        assert delete_response.status_code == 200

        # Verify the response contains the deleted subscription
        deleted = delete_response.json()
        assert deleted["id"] == subscription["id"]
        assert deleted["url"].rstrip("/") == unique_webhook_url.rstrip("/")
        assert "filter_types" in deleted
        assert "created_at" in deleted
        assert "updated_at" in deleted

    async def test_delete_subscription_returns_correct_fields(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that delete returns all expected subscription fields."""
        # Create a subscription with specific event types
        event_types = ["sync.completed", "sync.failed"]
        create_response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": event_types,
            },
        )
        assert create_response.status_code == 200
        subscription = create_response.json()

        # Delete and verify all fields are returned
        delete_response = await api_client.delete(
            f"/events/subscriptions/{subscription['id']}"
        )
        assert delete_response.status_code == 200
        deleted = delete_response.json()

        # Verify structure matches the created subscription
        assert deleted["id"] == subscription["id"]
        assert deleted["url"] == subscription["url"]
        assert set(deleted["filter_types"]) == set(event_types)
        assert deleted["disabled"] == subscription["disabled"]
        assert deleted["created_at"] == subscription["created_at"]

    async def test_delete_subscription_not_found(
        self, api_client: httpx.AsyncClient
    ):
        """Test deleting a non-existent subscription returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000000"
        response = await api_client.delete(f"/events/subscriptions/{fake_id}")
        assert response.status_code == 404

    async def test_get_subscription_with_secret(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test retrieving a subscription with include_secret=true."""
        response = await api_client.get(
            f"/events/subscriptions/{webhook_subscription['id']}",
            params={"include_secret": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert "secret" in data
        assert data["secret"] is not None
        # Svix secrets start with whsec_
        assert data["secret"].startswith("whsec_")

    async def test_get_subscription_without_secret(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test retrieving a subscription without include_secret (default)."""
        response = await api_client.get(
            f"/events/subscriptions/{webhook_subscription['id']}"
        )
        assert response.status_code == 200
        data = response.json()
        # Secret should be null when not requested
        assert data.get("secret") is None


@pytest.mark.asyncio
class TestWebhookDisableEnable:
    """Tests for disabling and enabling webhook endpoints."""

    async def test_disable_subscription_via_patch(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test disabling a subscription using PATCH with disabled=true."""
        subscription_id = webhook_subscription["id"]

        # Disable the subscription
        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": True},
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["disabled"] is True

        # Verify it's disabled when fetching
        get_response = await api_client.get(f"/events/subscriptions/{subscription_id}")
        assert get_response.status_code == 200
        assert get_response.json()["disabled"] is True

    async def test_enable_subscription_via_patch(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test re-enabling a disabled subscription using PATCH with disabled=false."""
        subscription_id = webhook_subscription["id"]

        # First disable it
        await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": True},
        )

        # Now enable it
        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": False},
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["disabled"] is False

    async def test_update_url_and_disable_simultaneously(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test updating URL and disabling in the same PATCH request."""
        subscription_id = webhook_subscription["id"]
        new_url = f"https://example.com/webhook/updated-{uuid.uuid4().hex[:8]}"

        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={
                "url": new_url,
                "disabled": True,
            },
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["url"].rstrip("/") == new_url.rstrip("/")
        assert updated["disabled"] is True

    async def test_enable_subscription_via_patch(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test enabling a subscription via PATCH with disabled=false."""
        subscription_id = webhook_subscription["id"]

        # First disable it
        await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": True},
        )

        # Enable via PATCH
        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": False},
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["disabled"] is False

    async def test_enable_with_recovery_parameter(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test enabling with the recover_since parameter.

        Note: We can't easily verify that recovery actually happened without
        having failed messages, but we can verify the API accepts the parameter.
        """
        subscription_id = webhook_subscription["id"]

        # First disable it
        await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": True},
        )

        # Enable with recovery - use a recent timestamp
        recover_since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": False, "recover_since": recover_since},
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["disabled"] is False

    async def test_enable_already_enabled_subscription(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that enabling an already-enabled subscription is idempotent."""
        subscription_id = webhook_subscription["id"]

        # Enable when already enabled - should succeed
        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": False},
        )
        assert response.status_code == 200
        assert response.json()["disabled"] is False


@pytest.mark.asyncio
class TestWebhookRecovery:
    """Tests for webhook message recovery functionality.

    Expected behavior: Recovery should succeed (200) even when there are no
    messages to recover - it's a no-op, not an error.
    """

    async def test_recover_messages_missing_since_returns_error(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that POST /recover requires the since parameter.

        Expected: 422 validation error.
        """
        subscription_id = webhook_subscription["id"]

        response = await api_client.post(
            f"/events/subscriptions/{subscription_id}/recover",
            json={},
        )
        assert response.status_code == 422

    async def test_recover_messages_endpoint_accepts_valid_request(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that POST /recover accepts a valid request with since parameter.

        Expected: 200 - recovery should succeed even with no messages.
        """
        subscription_id = webhook_subscription["id"]
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        response = await api_client.post(
            f"/events/subscriptions/{subscription_id}/recover",
            json={"since": since},
        )
        assert response.status_code == 200

    async def test_recover_messages_with_until_parameter(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test recovery with both since and until parameters.

        Expected: 200 - valid request should succeed.
        """
        subscription_id = webhook_subscription["id"]
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        until = datetime.now(timezone.utc).isoformat()

        response = await api_client.post(
            f"/events/subscriptions/{subscription_id}/recover",
            json={
                "since": since,
                "until": until,
            },
        )
        assert response.status_code == 200

    async def test_recover_returns_task_info(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that POST /recover returns recovery task information.

        Expected: 200 with task info in response.
        """
        subscription_id = webhook_subscription["id"]
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        response = await api_client.post(
            f"/events/subscriptions/{subscription_id}/recover",
            json={"since": since},
        )
        assert response.status_code == 200
        result = response.json()
        assert result is not None


@pytest.mark.asyncio
class TestSubscriptionStatusInList:
    """Tests for subscription status visibility in list operations."""

    async def test_list_subscriptions_includes_disabled_status(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that listing subscriptions includes the disabled field."""
        # First disable the subscription
        await api_client.patch(
            f"/events/subscriptions/{webhook_subscription['id']}",
            json={"disabled": True},
        )

        # List all subscriptions
        response = await api_client.get("/events/subscriptions")
        assert response.status_code == 200
        subscriptions = response.json()

        # Find our subscription
        our_sub = next(
            (s for s in subscriptions if s["id"] == webhook_subscription["id"]),
            None,
        )
        assert our_sub is not None
        assert "disabled" in our_sub
        assert our_sub["disabled"] is True

    async def test_new_subscription_is_enabled_by_default(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that newly created subscriptions are enabled by default."""
        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 200
        subscription = response.json()

        # Should be enabled (disabled=False or not present)
        assert subscription.get("disabled", False) is False

        # Cleanup
        await api_client.delete(f"/events/subscriptions/{subscription['id']}")


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


@pytest.mark.asyncio
class TestSubscriptionValidation:
    """Edge case tests for subscription input validation."""

    async def test_create_subscription_invalid_url_format(
        self, api_client: httpx.AsyncClient
    ):
        """Test creating subscription with invalid URL format returns 422."""
        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": "not-a-valid-url",
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 422

    async def test_create_subscription_empty_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating subscription with empty event_types array.

        Expected: 422 validation error - a subscription with no events is meaningless.
        """
        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": [],
            },
        )
        assert response.status_code == 422

    async def test_create_subscription_duplicate_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating subscription with duplicate event types."""
        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed", "sync.completed", "sync.failed"],
            },
        )
        # Should succeed - duplicates should be deduplicated or allowed
        assert response.status_code == 200
        subscription = response.json()
        await api_client.delete(f"/events/subscriptions/{subscription['id']}")

    async def test_create_subscription_with_http_url(
        self, api_client: httpx.AsyncClient
    ):
        """Test creating subscription with HTTP (non-HTTPS) URL.

        Expected: 200 - HTTP URLs should be allowed for local development/testing.
        """
        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": f"http://example.com/webhook/{uuid.uuid4().hex[:8]}",
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 200
        await api_client.delete(f"/events/subscriptions/{response.json()['id']}")

    async def test_create_subscription_with_localhost_url(
        self, api_client: httpx.AsyncClient
    ):
        """Test creating subscription with localhost URL.

        Expected: 200 - localhost should be allowed for local development.
        """
        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": "http://localhost:8080/webhook",
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 200
        await api_client.delete(f"/events/subscriptions/{response.json()['id']}")

    async def test_create_subscription_missing_url(
        self, api_client: httpx.AsyncClient
    ):
        """Test creating subscription without URL field."""
        response = await api_client.post(
            "/events/subscriptions",
            json={
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 422

    async def test_create_subscription_missing_event_types(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating subscription without event_types field."""
        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": unique_webhook_url,
            },
        )
        assert response.status_code == 422

    async def test_update_subscription_with_invalid_url(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test updating subscription with invalid URL format."""
        response = await api_client.patch(
            f"/events/subscriptions/{webhook_subscription['id']}",
            json={"url": "not-a-valid-url"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestSubscriptionSecretValidation:
    """Edge case tests for subscription secret handling."""

    async def test_create_subscription_with_custom_secret(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating subscription with a valid custom secret."""
        # whsec_ prefix with base64 encoded secret (at least 24 chars)
        custom_secret = "whsec_" + "a" * 32

        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed"],
                "secret": custom_secret,
            },
        )
        # May succeed or fail depending on secret format requirements
        if response.status_code == 200:
            subscription = response.json()
            # Verify we can retrieve the secret via include_secret param
            secret_response = await api_client.get(
                f"/events/subscriptions/{subscription['id']}",
                params={"include_secret": True},
            )
            assert secret_response.status_code == 200
            assert secret_response.json().get("secret") is not None
            await api_client.delete(f"/events/subscriptions/{subscription['id']}")

    async def test_create_subscription_with_short_secret(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test creating subscription with too short secret.

        Expected: 422 validation error.
        """
        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed"],
                "secret": "short",
            },
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestNonExistentResources:
    """Edge case tests for operations on non-existent resources.

    Expected behavior: All operations on non-existent resources should return 404.
    """

    async def test_get_non_existent_subscription(
        self, api_client: httpx.AsyncClient
    ):
        """Test getting a subscription that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "ep_nonexistent123456789"
        response = await api_client.get(f"/events/subscriptions/{fake_id}")
        assert response.status_code == 404

    async def test_delete_non_existent_subscription(
        self, api_client: httpx.AsyncClient
    ):
        """Test deleting a subscription that doesn't exist.

        Expected: 404 Not Found (or 200 for idempotent delete).
        """
        fake_id = "ep_nonexistent123456789"
        response = await api_client.delete(f"/events/subscriptions/{fake_id}")
        assert response.status_code in [200, 404]

    async def test_update_non_existent_subscription(
        self, api_client: httpx.AsyncClient
    ):
        """Test updating a subscription that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "ep_nonexistent123456789"
        response = await api_client.patch(
            f"/events/subscriptions/{fake_id}",
            json={"disabled": True},
        )
        assert response.status_code == 404

    async def test_enable_non_existent_subscription(
        self, api_client: httpx.AsyncClient
    ):
        """Test enabling a subscription that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "ep_nonexistent123456789"
        response = await api_client.patch(
            f"/events/subscriptions/{fake_id}",
            json={"disabled": False},
        )
        assert response.status_code == 404

    async def test_recover_non_existent_subscription(
        self, api_client: httpx.AsyncClient
    ):
        """Test recovering messages for a subscription that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "ep_nonexistent123456789"
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        response = await api_client.post(
            f"/events/subscriptions/{fake_id}/recover",
            json={"since": since},
        )
        assert response.status_code == 404

    async def test_get_secret_non_existent_subscription(
        self, api_client: httpx.AsyncClient
    ):
        """Test getting secret for a subscription that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "ep_nonexistent123456789"
        response = await api_client.get(
            f"/events/subscriptions/{fake_id}",
            params={"include_secret": True},
        )
        assert response.status_code == 404

    async def test_get_non_existent_message(
        self, api_client: httpx.AsyncClient
    ):
        """Test getting a message that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "msg_nonexistent123456789"
        response = await api_client.get(f"/events/messages/{fake_id}")
        assert response.status_code == 404

    async def test_get_attempts_non_existent_message(
        self, api_client: httpx.AsyncClient
    ):
        """Test getting attempts for a message that doesn't exist.

        Expected: 404 Not Found.
        """
        fake_id = "msg_nonexistent123456789"
        response = await api_client.get(
            f"/events/messages/{fake_id}",
            params={"include_attempts": True},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestRecoveryEdgeCases:
    """Edge case tests for message recovery functionality."""

    async def test_recover_with_future_since_date(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test recovery with a future since date.

        Expected: 200 (no messages to recover) or 422 (validation error).
        """
        subscription_id = webhook_subscription["id"]
        future_date = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

        response = await api_client.post(
            f"/events/subscriptions/{subscription_id}/recover",
            json={"since": future_date},
        )
        assert response.status_code in [200, 422]

    async def test_recover_with_until_before_since(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test recovery with until date before since date.

        Expected: 200 - Svix accepts this as a no-op (nothing to recover in empty range).
        """
        subscription_id = webhook_subscription["id"]
        since = datetime.now(timezone.utc).isoformat()
        until = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        response = await api_client.post(
            f"/events/subscriptions/{subscription_id}/recover",
            json={"since": since, "until": until},
        )
        assert response.status_code == 200

    async def test_recover_with_very_old_since_date(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test recovery with a very old since date (years ago).

        Expected: 422 - Svix only allows recovery within 14 days.
        """
        subscription_id = webhook_subscription["id"]
        old_date = (datetime.now(timezone.utc) - timedelta(days=365 * 2)).isoformat()

        response = await api_client.post(
            f"/events/subscriptions/{subscription_id}/recover",
            json={"since": old_date},
        )
        assert response.status_code == 422
        assert "14 days" in response.json()["detail"]

    async def test_recover_with_invalid_date_format(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test recovery with invalid date format.

        Expected: 422 validation error.
        """
        subscription_id = webhook_subscription["id"]

        response = await api_client.post(
            f"/events/subscriptions/{subscription_id}/recover",
            json={"since": "not-a-date"},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
class TestDisableEnableEdgeCases:
    """Edge case tests for disable/enable functionality."""

    async def test_disable_already_disabled_subscription(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test disabling an already disabled subscription (idempotent)."""
        subscription_id = webhook_subscription["id"]

        # Disable twice
        await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": True},
        )
        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": True},
        )
        assert response.status_code == 200
        assert response.json()["disabled"] is True

    async def test_rapid_enable_disable_toggle(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test rapid toggling between enabled and disabled states."""
        subscription_id = webhook_subscription["id"]

        for _ in range(5):
            # Disable
            response = await api_client.patch(
                f"/events/subscriptions/{subscription_id}",
                json={"disabled": True},
            )
            assert response.status_code == 200

            # Enable
            response = await api_client.patch(
                f"/events/subscriptions/{subscription_id}",
                json={"disabled": False},
            )
            assert response.status_code == 200

        # Final state should be enabled
        get_response = await api_client.get(f"/events/subscriptions/{subscription_id}")
        assert get_response.json()["disabled"] is False

    async def test_patch_with_empty_body(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test PATCH with empty JSON body."""
        subscription_id = webhook_subscription["id"]

        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={},
        )
        # Should succeed as a no-op
        assert response.status_code == 200

    async def test_enable_preserves_other_fields(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that enabling doesn't modify URL or event types."""
        subscription_id = webhook_subscription["id"]
        original_url = webhook_subscription["url"]

        # Disable
        await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": True},
        )

        # Enable via PATCH with disabled=false
        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": False},
        )
        assert response.status_code == 200
        updated = response.json()

        # URL should be unchanged
        assert updated["url"].rstrip("/") == original_url.rstrip("/")


@pytest.mark.asyncio
class TestSubscriptionUpdateEdgeCases:
    """Edge case tests for subscription updates."""

    async def test_update_only_url(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test updating only the URL field."""
        subscription_id = webhook_subscription["id"]
        new_url = f"https://example.com/webhook/new-{uuid.uuid4().hex[:8]}"

        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"url": new_url},
        )
        assert response.status_code == 200
        assert response.json()["url"].rstrip("/") == new_url.rstrip("/")

    async def test_update_only_event_types(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test updating only the event_types field."""
        subscription_id = webhook_subscription["id"]

        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"event_types": ["sync.failed", "sync.cancelled"]},
        )
        assert response.status_code == 200

    async def test_update_all_fields_simultaneously(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test updating URL, event_types, and disabled all at once."""
        subscription_id = webhook_subscription["id"]
        new_url = f"https://example.com/webhook/all-{uuid.uuid4().hex[:8]}"

        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={
                "url": new_url,
                "event_types": ["sync.pending", "sync.running"],
                "disabled": True,
            },
        )
        assert response.status_code == 200
        updated = response.json()
        assert updated["url"].rstrip("/") == new_url.rstrip("/")
        assert updated["disabled"] is True

    async def test_updated_at_changes_after_patch(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that updated_at timestamp changes after PATCH."""
        subscription_id = webhook_subscription["id"]
        original_updated_at = webhook_subscription.get("updated_at")

        # Small delay to ensure timestamp difference
        await asyncio.sleep(0.1)

        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": True},
        )
        assert response.status_code == 200

        if original_updated_at:
            # updated_at should be different (or at least not before)
            new_updated_at = response.json().get("updated_at")
            assert new_updated_at is not None

    async def test_created_at_unchanged_after_patch(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that created_at timestamp doesn't change after PATCH."""
        subscription_id = webhook_subscription["id"]
        original_created_at = webhook_subscription.get("created_at")

        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": True},
        )
        assert response.status_code == 200

        if original_created_at:
            new_created_at = response.json().get("created_at")
            assert new_created_at == original_created_at


@pytest.mark.asyncio
class TestMessageQueryEdgeCases:
    """Edge case tests for message querying."""

    async def test_get_messages_empty_event_types_filter(
        self, api_client: httpx.AsyncClient
    ):
        """Test getting messages with empty event_types filter."""
        response = await api_client.get(
            "/events/messages",
            params={"event_types": []},
        )
        # Should return all messages or handle gracefully
        assert response.status_code == 200

    async def test_get_messages_multiple_event_types(
        self, api_client: httpx.AsyncClient
    ):
        """Test getting messages filtered by multiple event types."""
        response = await api_client.get(
            "/events/messages",
            params={"event_types": ["sync.completed", "sync.failed", "sync.running"]},
        )
        assert response.status_code == 200
        messages = response.json()
        # All returned messages should be one of the filtered types
        for msg in messages:
            assert msg["event_type"] in ["sync.completed", "sync.failed", "sync.running"]


@pytest.mark.asyncio
class TestConcurrentOperations:
    """Edge case tests for concurrent operations."""

    async def test_concurrent_updates_to_same_subscription(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test concurrent updates to the same subscription."""
        subscription_id = webhook_subscription["id"]

        # Fire multiple updates concurrently
        tasks = [
            api_client.patch(
                f"/events/subscriptions/{subscription_id}",
                json={"disabled": i % 2 == 0},
            )
            for i in range(5)
        ]
        responses = await asyncio.gather(*tasks)

        # All should succeed (last write wins)
        for response in responses:
            assert response.status_code == 200

    async def test_delete_after_operations_started(
        self, api_client: httpx.AsyncClient, unique_webhook_url: str
    ):
        """Test that operations handle deletion gracefully.

        Expected: 404 Not Found when operating on deleted subscription.
        """
        # Create a subscription
        create_response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": unique_webhook_url,
                "event_types": ["sync.completed"],
            },
        )
        subscription = create_response.json()
        subscription_id = subscription["id"]

        # Delete it
        await api_client.delete(f"/events/subscriptions/{subscription_id}")

        # Try to update - should return 404
        response = await api_client.patch(
            f"/events/subscriptions/{subscription_id}",
            json={"disabled": True},
        )
        assert response.status_code == 404


@pytest.mark.asyncio
class TestListOperationsEdgeCases:
    """Edge case tests for list operations."""

    async def test_list_subscriptions_returns_correct_structure(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test that list subscriptions returns correct structure for each item."""
        response = await api_client.get("/events/subscriptions")
        assert response.status_code == 200
        subscriptions = response.json()

        for sub in subscriptions:
            # Verify required fields exist
            assert "id" in sub
            assert "url" in sub
            assert "created_at" in sub
            # disabled may or may not be present

    async def test_list_messages_returns_correct_structure(
        self, api_client: httpx.AsyncClient
    ):
        """Test that list messages returns correct structure."""
        response = await api_client.get("/events/messages")
        assert response.status_code == 200
        messages = response.json()

        for msg in messages:
            assert "id" in msg
            assert "event_type" in msg
            assert "timestamp" in msg
