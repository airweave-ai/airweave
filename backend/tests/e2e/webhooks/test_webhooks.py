import pytest
import httpx
import logging
import pytest_asyncio
import asyncio
import uvicorn
from typing import AsyncGenerator, Dict, Optional, Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

LOGGER = logging.getLogger(__name__)
WEBHOOK_RECEIVER_PORT_1 = 9086
WEBHOOK_RECEIVER_PORT_2 = 9087


@pytest.fixture(scope="function")
def webhook_receiver_port(request) -> int:
    """Return the port for the webhook receiver. Can be parametrized per test."""
    return getattr(request, "param", WEBHOOK_RECEIVER_PORT_1)


class WebhookReceiver:
    """A webhook receiver that waits for incoming webhook calls."""
    
    def __init__(self):
        self._event: Optional[asyncio.Event] = None
        self._body: Optional[Dict[str, Any]] = None
        self._headers: Optional[Dict[str, str]] = None
        self._path: Optional[str] = None
    
    def _get_event(self) -> asyncio.Event:
        """Get or create the asyncio.Event, ensuring it's bound to the current event loop."""
        if self._event is None:
            self._event = asyncio.Event()
        return self._event
    
    def receive(self, body: Dict[str, Any], headers: Dict[str, str], path: str) -> None:
        """Called when a webhook is received."""
        self._body = body
        self._headers = headers
        self._path = path
        self._get_event().set()
    
    async def wait_for_webhook(self, timeout: float = 10.0) -> Dict[str, Any]:
        """Wait for a webhook call and return the body, or raise TimeoutError."""
        try:
            await asyncio.wait_for(self._get_event().wait(), timeout=timeout)
            return {"body": self._body, "headers": self._headers, "path": self._path}
        except asyncio.TimeoutError:
            raise TimeoutError(f"No webhook received within {timeout} seconds")
    
    def reset(self) -> None:
        """Reset the receiver to wait for another webhook."""
        if self._event is not None:
            self._event.clear()
        self._body = None
        self._headers = None
        self._path = None



@pytest_asyncio.fixture(scope="function")
async def webhook_receiver(webhook_receiver_port: int) -> AsyncGenerator[WebhookReceiver, None]:
    """Start a webhook receiver server and yield a receiver object."""
    receiver = WebhookReceiver()
    
    app = FastAPI()
    
    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def catch_all(request: Request, path: str = ""):
        """Catch all webhook calls."""
        body = await request.body()
        try:
            import json
            body_json = json.loads(body) if body else {}
        except:
            body_json = {"raw": body.decode("utf-8", errors="replace")}
        
        headers = dict(request.headers)
        request_path = f"/{path}" if path else "/"
        receiver.receive(body_json, headers, request_path)
        
        return JSONResponse({"status": "ok"})
    
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=webhook_receiver_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)
    
    # Start server in background task
    server_task = asyncio.create_task(server.serve())
    
    # Wait a moment for server to start
    await asyncio.sleep(0.5)
    
    yield receiver
    
    # Shutdown server
    server.should_exit = True
    await server_task


@pytest_asyncio.fixture(scope="function")
async def subscription(api_client: httpx.AsyncClient, webhook_receiver_port: int) -> AsyncGenerator[Dict, None]:
    """Create a test subscription that's cleaned up after use."""
    subscription_url = f"http://host.docker.internal:{webhook_receiver_port}"
    response = await api_client.post("/events/subscriptions", json={
        "url": subscription_url,
        "event_types": ["sync.completed"],
    })
    assert response.status_code == 200
    subscription = response.json()
    
    yield subscription

    try:
        response = await api_client.delete(f"/events/subscriptions/{subscription['id']}")
    except:
        pass

@pytest.mark.asyncio
class TestWebhooks:
    """Test suite for webhooks functionality."""

    async def test_get_subscriptions(self, api_client: httpx.AsyncClient):
        """Test getting subscriptions."""
        response = await api_client.get("/events/subscriptions")
        assert response.status_code == 200
        assert response.json() is not None

    async def test_get_subscription(self, api_client: httpx.AsyncClient, subscription: Dict):
        """Test getting a subscription."""
        response = await api_client.get(f"/events/subscriptions/{subscription['id']}")
        assert response.status_code == 200
        assert response.json() is not None
        assert response.json()['endpoint']['id'] == subscription['id']

    async def test_create_subscription(self, api_client: httpx.AsyncClient):
        """Test creating a subscription."""
        subscription_url = f"http://host.docker.internal:{WEBHOOK_RECEIVER_PORT_1}"
        response = await api_client.post("/events/subscriptions", json={
            "url": subscription_url,
            "event_types": ["sync.completed"],
        })
        assert response.status_code == 200
        assert response.json() is not None
        subscription = response.json()

        # Cleanup
        response = await api_client.delete(f"/events/subscriptions/{subscription['id']}")
        assert response.status_code == 200

    @pytest.mark.parametrize("webhook_receiver_port", [WEBHOOK_RECEIVER_PORT_1], indirect=True)
    async def test_webhook_received(
        self,
        api_client: httpx.AsyncClient,
        subscription: Dict,
        collection: Dict,
        webhook_receiver: WebhookReceiver,
    ):
        """Test that a webhook is received when an event occurs."""

        await api_client.post(f"/source-connections", json={
            "name":"Stub",
            "description":"Stub",
            "short_name":"stub",
            "readable_collection_id":collection["readable_id"],
            "authentication":{"credentials":{"stub_key":"key"}},
            "config":{"entity_count":"1"},
            "sync_immediately":True
        })

        result = await webhook_receiver.wait_for_webhook(timeout=10.0)
        assert result["body"]["type"] == "sync.completed"

    @pytest.mark.parametrize("webhook_receiver_port", [WEBHOOK_RECEIVER_PORT_2], indirect=True)
    async def test_webhook_not_received_after_subscription_deleted(
        self,
        api_client: httpx.AsyncClient,
        subscription: Dict,
        collection: Dict,
        webhook_receiver: WebhookReceiver,
    ):
        """Test that no webhook is received after subscription is deleted."""
        # Delete the subscription before triggering the event
        response = await api_client.delete(f"/events/subscriptions/{subscription['id']}")
        assert response.status_code == 200

        # Trigger an event that would normally send a webhook
        await api_client.post(f"/source-connections", json={
            "name": "Stub",
            "description": "Stub",
            "short_name": "stub",
            "readable_collection_id": collection["readable_id"],
            "authentication": {"credentials": {"stub_key": "key"}},
            "config": {"entity_count": "1"},
            "sync_immediately": True
        })

        with pytest.raises(TimeoutError):
            await webhook_receiver.wait_for_webhook(timeout=5.0)

