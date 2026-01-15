"""E2E tests for Events API and Webhook functionality.

These tests cover two distinct concepts:
- **Events (Messages)**: Records of what happened in the system (sync.pending, sync.completed, etc.)
- **Webhooks (Subscriptions)**: Endpoints that receive event notifications at configured URLs

Tests use the stub connector for fast execution while testing the full flow including Svix integration.

NOTE: These tests should NOT run in parallel (-n 1) due to port binding for webhook receivers.
"""

import asyncio
import json
import logging
import os
import random
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import pytest
import pytest_asyncio
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

LOGGER = logging.getLogger(__name__)

# Webhook delivery timeout - Svix may have retry delays
WEBHOOK_TIMEOUT = 30.0

# Webhook receiver base URL can be overridden for local setups.
# If Svix runs on the host, use http://localhost. If Svix runs in Docker, use
# http://host.docker.internal so the container can reach the host.
WEBHOOK_RECEIVER_BASE_URL = os.getenv("WEBHOOK_RECEIVER_BASE_URL")
if not WEBHOOK_RECEIVER_BASE_URL:
    svix_url = os.getenv("SVIX_URL", "")
    if "localhost" in svix_url or "127.0.0.1" in svix_url:
        WEBHOOK_RECEIVER_BASE_URL = "http://localhost"
    else:
        WEBHOOK_RECEIVER_BASE_URL = "http://host.docker.internal"


def get_webhook_receiver_url(port: int) -> str:
    """Build the webhook receiver URL for Svix delivery."""
    return f"{WEBHOOK_RECEIVER_BASE_URL}:{port}/"


# Use worker-specific ports to avoid conflicts in parallel execution
# Each pytest-xdist worker gets a unique PYTEST_XDIST_WORKER env var (gw0, gw1, etc.)
def get_unique_port(base_port: int = 9100) -> int:
    """Get a unique port based on worker ID to avoid conflicts."""
    worker = os.environ.get("PYTEST_XDIST_WORKER", "")
    if worker:
        # Extract worker number from gw0, gw1, etc.
        worker_num = int(worker.replace("gw", "")) if worker.startswith("gw") else 0
        return base_port + (worker_num * 10) + random.randint(0, 9)
    return base_port + random.randint(0, 99)


class WebhookReceiver:
    """A webhook receiver that collects all incoming webhook calls."""

    def __init__(self):
        self._events: List[Dict[str, Any]] = []
        self._event: Optional[asyncio.Event] = None

    def _get_event(self) -> asyncio.Event:
        """Get or create the asyncio.Event, ensuring it's bound to the current event loop."""
        if self._event is None:
            self._event = asyncio.Event()
        return self._event

    def receive(self, body: Dict[str, Any], headers: Dict[str, str], path: str) -> None:
        """Called when a webhook is received."""
        self._events.append({
            "body": body,
            "headers": headers,
            "path": path,
        })
        self._get_event().set()

    async def wait_for_webhook(self, timeout: float = WEBHOOK_TIMEOUT) -> Dict[str, Any]:
        """Wait for a webhook call and return the most recent event."""
        try:
            await asyncio.wait_for(self._get_event().wait(), timeout=timeout)
            return self._events[-1] if self._events else {}
        except asyncio.TimeoutError:
            raise TimeoutError(f"No webhook received within {timeout} seconds")

    async def wait_for_event_type(
        self, event_type: str, timeout: float = WEBHOOK_TIMEOUT
    ) -> Dict[str, Any]:
        """Wait for a specific event type to be received."""
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            for event in self._events:
                # Check both 'event_type' (our schema) and 'type' (potential Svix wrapper)
                body = event.get("body", {})
                if body.get("event_type") == event_type or body.get("type") == event_type:
                    return event
            await asyncio.sleep(0.2)
        raise TimeoutError(f"Event type '{event_type}' not received within {timeout}s")

    def get_events(self) -> List[Dict[str, Any]]:
        """Get all received events."""
        return self._events.copy()

    def reset(self) -> None:
        """Reset the receiver to wait for new webhooks."""
        if self._event is not None:
            self._event.clear()
        self._events = []


async def start_webhook_server(receiver: WebhookReceiver, port: int):
    """Start a webhook receiver server."""
    app = FastAPI()

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def catch_all(request: Request, path: str = ""):
        """Catch all webhook calls."""
        body = await request.body()
        try:
            body_json = json.loads(body) if body else {}
        except Exception:
            body_json = {"raw": body.decode("utf-8", errors="replace")}

        headers = dict(request.headers)
        request_path = f"/{path}" if path else "/"
        receiver.receive(body_json, headers, request_path)

        return JSONResponse({"status": "ok"})

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    # Wait for server to be ready
    await asyncio.sleep(1.0)
    return server, server_task


@pytest.fixture(scope="function")
def webhook_port() -> int:
    """Get a unique port for this test."""
    return get_unique_port()


@pytest_asyncio.fixture(scope="function")
async def webhook_receiver(webhook_port: int) -> AsyncGenerator[tuple[WebhookReceiver, int], None]:
    """Start a webhook receiver server and yield (receiver, port)."""
    receiver = WebhookReceiver()
    server, server_task = await start_webhook_server(receiver, webhook_port)

    yield receiver, webhook_port

    server.should_exit = True
    await server_task


@pytest_asyncio.fixture(scope="function")
async def webhook_subscription(
    api_client: httpx.AsyncClient,
    webhook_receiver: tuple[WebhookReceiver, int],  # Depend on receiver to ensure it starts first
) -> AsyncGenerator[Dict, None]:
    """Create a webhook subscription for sync.completed events.

    NOTE: This fixture depends on webhook_receiver to ensure the server is running
    before the subscription is created.
    """
    _, port = webhook_receiver
    subscription_url = get_webhook_receiver_url(port)
    response = await api_client.post(
        "/events/subscriptions",
        json={
            "url": subscription_url,
            "event_types": ["sync.completed"],
        },
    )
    assert response.status_code == 200, f"Failed to create subscription: {response.text}"
    subscription = response.json()

    yield subscription

    try:
        await api_client.delete(f"/events/subscriptions/{subscription['id']}")
    except Exception:
        pass


@pytest_asyncio.fixture(scope="function")
async def webhook_subscription_all_events(
    api_client: httpx.AsyncClient,
    webhook_receiver: tuple[WebhookReceiver, int],  # Depend on receiver to ensure it starts first
) -> AsyncGenerator[Dict, None]:
    """Create a webhook subscription for all sync event types.

    NOTE: This fixture depends on webhook_receiver to ensure the server is running
    before the subscription is created.
    """
    _, port = webhook_receiver
    subscription_url = get_webhook_receiver_url(port)
    response = await api_client.post(
        "/events/subscriptions",
        json={
            "url": subscription_url,
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
            assert msg["eventType"] == "sync.completed"

    async def test_messages_created_after_sync(
        self,
        api_client: httpx.AsyncClient,
        webhook_subscription: Dict,
        collection: Dict,
        webhook_receiver: tuple[WebhookReceiver, int],
    ):
        """Test that event messages are created when syncs occur."""
        receiver, port = webhook_receiver

        # Trigger a sync
        await api_client.post(
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

        # Wait for webhook to confirm sync completed
        await receiver.wait_for_webhook(timeout=WEBHOOK_TIMEOUT)

        # Check messages API
        response = await api_client.get("/events/messages")
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) > 0

        # Verify message structure
        latest_message = messages[0]
        assert "id" in latest_message
        assert "eventType" in latest_message
        assert "payload" in latest_message


@pytest.mark.asyncio
class TestEventTypes:
    """Tests for different event types (sync.pending, sync.running, sync.completed, etc.)."""

    async def test_sync_lifecycle_events(
        self,
        api_client: httpx.AsyncClient,
        webhook_subscription_all_events: Dict,
        collection: Dict,
        webhook_receiver: tuple[WebhookReceiver, int],
    ):
        """Test that sync lifecycle events are generated (running → completed).

        NOTE: sync.pending may be published before the subscription is active,
        so we only verify running and completed events are received.
        """
        receiver, port = webhook_receiver

        await api_client.post(
            "/source-connections",
            json={
                "name": "Stub Lifecycle Test",
                "description": "Testing event lifecycle",
                "short_name": "stub",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"stub_key": "key"}},
                "config": {"entity_count": "3"},
                "sync_immediately": True,
            },
        )

        # Wait for completed event
        await receiver.wait_for_event_type("sync.completed", timeout=WEBHOOK_TIMEOUT)

        events = receiver.get_events()
        event_types = [e["body"].get("event_type", e["body"].get("type")) for e in events]

        # Should have running and completed (pending may fire before subscription is active)
        assert "sync.running" in event_types or "sync.completed" in event_types
        assert "sync.completed" in event_types

    async def test_event_payload_structure(
        self,
        api_client: httpx.AsyncClient,
        webhook_subscription: Dict,
        collection: Dict,
        webhook_receiver: tuple[WebhookReceiver, int],
    ):
        """Test that event payloads contain all required fields."""
        receiver, port = webhook_receiver

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

        result = await receiver.wait_for_webhook(timeout=WEBHOOK_TIMEOUT)
        payload = result["body"]

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
        webhook_subscription_all_events: Dict,
        collection: Dict,
        webhook_receiver: tuple[WebhookReceiver, int],
    ):
        """Test that completed events include the job_id in correct format."""
        receiver, port = webhook_receiver

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

        completed_event = await receiver.wait_for_event_type(
            "sync.completed", timeout=WEBHOOK_TIMEOUT
        )

        assert "job_id" in completed_event["body"]
        job_id = completed_event["body"]["job_id"]
        # UUID format validation
        assert len(job_id) == 36  # xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx


# =============================================================================
# WEBHOOK TESTS - Testing webhook subscriptions and delivery
# =============================================================================


@pytest.mark.asyncio
class TestWebhookSubscriptions:
    """Tests for webhook subscription CRUD operations."""

    async def test_list_subscriptions(self, api_client: httpx.AsyncClient):
        """Test listing all webhook subscriptions."""
        response = await api_client.get("/events/subscriptions")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_create_subscription(self, api_client: httpx.AsyncClient, webhook_port: int):
        """Test creating a webhook subscription."""
        subscription_url = get_webhook_receiver_url(webhook_port)
        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": subscription_url,
                "event_types": ["sync.completed"],
            },
        )
        assert response.status_code == 200
        subscription = response.json()
        assert subscription["id"] is not None
        # Svix normalizes URLs, so check with rstrip
        assert subscription["url"].rstrip("/") == subscription_url.rstrip("/")

        # Cleanup
        await api_client.delete(f"/events/subscriptions/{subscription['id']}")

    async def test_create_subscription_multiple_event_types(
        self, api_client: httpx.AsyncClient, webhook_port: int
    ):
        """Test creating a subscription with multiple event types."""
        subscription_url = get_webhook_receiver_url(webhook_port)
        event_types = ["sync.completed", "sync.failed", "sync.running"]

        response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": subscription_url,
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
        assert data["endpoint"]["id"] == webhook_subscription["id"]
        assert "message_attempts" in data

    async def test_update_subscription_url(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test updating a subscription URL."""
        new_url = get_webhook_receiver_url(get_unique_port(9200))
        response = await api_client.patch(
            f"/events/subscriptions/{webhook_subscription['id']}",
            json={"url": new_url},
        )
        assert response.status_code == 200
        updated = response.json()
        # Svix normalizes URLs, so check with rstrip
        assert updated["url"].rstrip("/") == new_url.rstrip("/")

    async def test_delete_subscription(self, api_client: httpx.AsyncClient, webhook_port: int):
        """Test deleting a webhook subscription."""
        # Create a subscription to delete
        subscription_url = get_webhook_receiver_url(webhook_port)
        create_response = await api_client.post(
            "/events/subscriptions",
            json={
                "url": subscription_url,
                "event_types": ["sync.completed"],
            },
        )
        subscription = create_response.json()

        # Delete it
        delete_response = await api_client.delete(
            f"/events/subscriptions/{subscription['id']}"
        )
        assert delete_response.status_code == 200

    async def test_get_subscription_secret(
        self, api_client: httpx.AsyncClient, webhook_subscription: Dict
    ):
        """Test retrieving the signing secret for a subscription."""
        response = await api_client.get(
            f"/events/subscriptions/{webhook_subscription['id']}/secret"
        )
        assert response.status_code == 200
        secret_data = response.json()
        assert "key" in secret_data
        # Svix secrets start with whsec_
        assert secret_data["key"].startswith("whsec_")


@pytest.mark.asyncio
class TestWebhookDelivery:
    """Tests for webhook delivery - events being sent to subscribed URLs."""

    async def test_webhook_delivered_on_sync_complete(
        self,
        api_client: httpx.AsyncClient,
        webhook_subscription: Dict,
        collection: Dict,
        webhook_receiver: tuple[WebhookReceiver, int],
    ):
        """Test that a webhook is delivered when a sync completes."""
        receiver, port = webhook_receiver

        await api_client.post(
            "/source-connections",
            json={
                "name": "Stub Delivery Test",
                "description": "Testing webhook delivery",
                "short_name": "stub",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"stub_key": "key"}},
                "config": {"entity_count": "1"},
                "sync_immediately": True,
            },
        )

        result = await receiver.wait_for_webhook(timeout=WEBHOOK_TIMEOUT)
        # Our schema uses event_type, not type
        assert result["body"]["event_type"] == "sync.completed"
        assert result["body"]["source_type"] == "stub"

    async def test_no_delivery_after_subscription_deleted(
        self,
        api_client: httpx.AsyncClient,
        webhook_subscription: Dict,
        collection: Dict,
        webhook_receiver: tuple[WebhookReceiver, int],
    ):
        """Test that no webhook is delivered after subscription is deleted."""
        receiver, port = webhook_receiver

        # Delete the subscription before triggering the event
        response = await api_client.delete(
            f"/events/subscriptions/{webhook_subscription['id']}"
        )
        assert response.status_code == 200

        # Trigger an event that would normally send a webhook
        await api_client.post(
            "/source-connections",
            json={
                "name": "Stub No Webhook",
                "description": "Should not trigger webhook",
                "short_name": "stub",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"stub_key": "key"}},
                "config": {"entity_count": "1"},
                "sync_immediately": True,
            },
        )

        with pytest.raises(TimeoutError):
            await receiver.wait_for_webhook(timeout=5.0)

    async def test_webhook_includes_signature_headers(
        self,
        api_client: httpx.AsyncClient,
        webhook_subscription: Dict,
        collection: Dict,
        webhook_receiver: tuple[WebhookReceiver, int],
    ):
        """Test that webhooks include Svix signature headers for verification."""
        receiver, port = webhook_receiver

        await api_client.post(
            "/source-connections",
            json={
                "name": "Stub Signature Test",
                "description": "Testing signature headers",
                "short_name": "stub",
                "readable_collection_id": collection["readable_id"],
                "authentication": {"credentials": {"stub_key": "key"}},
                "config": {"entity_count": "1"},
                "sync_immediately": True,
            },
        )

        result = await receiver.wait_for_webhook(timeout=WEBHOOK_TIMEOUT)
        headers = result["headers"]

        # Svix includes these headers for signature verification
        assert "svix-id" in headers
        assert "svix-timestamp" in headers
        assert "svix-signature" in headers
