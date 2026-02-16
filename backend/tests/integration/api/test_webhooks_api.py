"""API integration tests for webhook endpoints.

Hits real FastAPI endpoints with an async client, but all infrastructure
(Svix, DB, auth) is replaced by fakes injected via the test_container
and overridden get_context.

Fixtures used:
- client: from conftest (AsyncClient with faked DI)
- fake_webhook_service: from root conftest (FakeWebhookService -- the
  service the API layer injects via WebhookServiceProtocol)
"""

from datetime import datetime, timezone

import pytest

from airweave.domains.webhooks.types import EventMessage


class TestWebhookSubscriptionsAPI:
    """Tests for /webhooks/subscriptions endpoints."""

    # -----------------------------------------------------------------
    # LIST
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_list_subscriptions_empty(self, client):
        response = await client.get("/webhooks/subscriptions")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_subscriptions_after_create(self, client, fake_webhook_service):
        payload = {
            "url": "https://example.com/hook",
            "event_types": ["sync.completed"],
        }
        await client.post("/webhooks/subscriptions", json=payload)

        response = await client.get("/webhooks/subscriptions")
        assert response.status_code == 200

        subs = response.json()
        assert len(subs) == 1
        assert subs[0]["url"] == "https://example.com/hook"
        assert subs[0]["health_status"] == "unknown"
        # List endpoint should NOT include delivery_attempts or secret
        assert "delivery_attempts" not in subs[0]
        assert "secret" not in subs[0]

    # -----------------------------------------------------------------
    # CREATE
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_create_subscription(self, client, fake_webhook_service):
        payload = {
            "url": "https://example.com/webhook",
            "event_types": ["sync.completed", "sync.failed"],
        }
        response = await client.post("/webhooks/subscriptions", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["url"] == "https://example.com/webhook"
        assert "sync.completed" in data["filter_types"]
        assert "sync.failed" in data["filter_types"]
        assert data["disabled"] is False
        assert "id" in data
        assert "created_at" in data

        # Verify the fake recorded the operation
        fake_webhook_service.assert_subscription_created("https://example.com/webhook")

    @pytest.mark.asyncio
    async def test_create_subscription_with_custom_secret(self, client):
        payload = {
            "url": "https://example.com/webhook",
            "event_types": ["sync.completed"],
            "secret": "whsec_test_secret_value_24chars",
        }
        response = await client.post("/webhooks/subscriptions", json=payload)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_create_subscription_invalid_event_type(self, client):
        payload = {
            "url": "https://example.com/webhook",
            "event_types": ["invalid.event.type"],
        }
        response = await client.post("/webhooks/subscriptions", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_subscription_empty_event_types(self, client):
        payload = {
            "url": "https://example.com/webhook",
            "event_types": [],
        }
        response = await client.post("/webhooks/subscriptions", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_subscription_short_secret(self, client):
        payload = {
            "url": "https://example.com/webhook",
            "event_types": ["sync.completed"],
            "secret": "tooshort",
        }
        response = await client.post("/webhooks/subscriptions", json=payload)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_subscription_invalid_url(self, client):
        payload = {
            "url": "not-a-url",
            "event_types": ["sync.completed"],
        }
        response = await client.post("/webhooks/subscriptions", json=payload)
        assert response.status_code == 422

    # -----------------------------------------------------------------
    # GET (detail)
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_get_subscription_by_id(self, client, fake_webhook_service):
        # Create first
        create_resp = await client.post(
            "/webhooks/subscriptions",
            json={
                "url": "https://example.com/hook",
                "event_types": ["sync.completed"],
            },
        )
        sub_id = create_resp.json()["id"]

        # Get detail
        response = await client.get(f"/webhooks/subscriptions/{sub_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == sub_id
        assert data["url"] == "https://example.com/hook"
        assert data["health_status"] == "unknown"
        # Detail endpoint includes delivery_attempts
        assert "delivery_attempts" in data
        assert data["delivery_attempts"] == []
        # Secret should be None by default
        assert data["secret"] is None

    @pytest.mark.asyncio
    async def test_get_subscription_with_secret(self, client, fake_webhook_service):
        create_resp = await client.post(
            "/webhooks/subscriptions",
            json={
                "url": "https://example.com/hook",
                "event_types": ["sync.completed"],
            },
        )
        sub_id = create_resp.json()["id"]

        response = await client.get(f"/webhooks/subscriptions/{sub_id}?include_secret=true")
        assert response.status_code == 200
        data = response.json()
        assert data["secret"] is not None

    @pytest.mark.asyncio
    async def test_get_nonexistent_subscription(self, client):
        response = await client.get("/webhooks/subscriptions/nonexistent-id")
        assert response.status_code == 500  # KeyError from fake

    # -----------------------------------------------------------------
    # DELETE
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_delete_subscription(self, client, fake_webhook_service):
        # Create
        create_resp = await client.post(
            "/webhooks/subscriptions",
            json={
                "url": "https://example.com/hook",
                "event_types": ["sync.completed"],
            },
        )
        sub_id = create_resp.json()["id"]

        # Delete
        response = await client.delete(f"/webhooks/subscriptions/{sub_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sub_id

        # Verify it's gone
        list_resp = await client.get("/webhooks/subscriptions")
        assert list_resp.json() == []

    # -----------------------------------------------------------------
    # PATCH (update)
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_update_subscription_url(self, client, fake_webhook_service):
        create_resp = await client.post(
            "/webhooks/subscriptions",
            json={
                "url": "https://example.com/hook",
                "event_types": ["sync.completed"],
            },
        )
        sub_id = create_resp.json()["id"]

        response = await client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"url": "https://new.example.com/hook"},
        )
        assert response.status_code == 200
        assert response.json()["url"] == "https://new.example.com/hook"

    @pytest.mark.asyncio
    async def test_disable_subscription(self, client, fake_webhook_service):
        create_resp = await client.post(
            "/webhooks/subscriptions",
            json={
                "url": "https://example.com/hook",
                "event_types": ["sync.completed"],
            },
        )
        sub_id = create_resp.json()["id"]

        response = await client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"disabled": True},
        )
        assert response.status_code == 200
        assert response.json()["disabled"] is True

    @pytest.mark.asyncio
    async def test_reenable_subscription(self, client, fake_webhook_service):
        create_resp = await client.post(
            "/webhooks/subscriptions",
            json={
                "url": "https://example.com/hook",
                "event_types": ["sync.completed"],
            },
        )
        sub_id = create_resp.json()["id"]

        # Disable
        await client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"disabled": True},
        )

        # Re-enable
        response = await client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"disabled": False},
        )
        assert response.status_code == 200
        assert response.json()["disabled"] is False

    @pytest.mark.asyncio
    async def test_update_event_types(self, client, fake_webhook_service):
        create_resp = await client.post(
            "/webhooks/subscriptions",
            json={
                "url": "https://example.com/hook",
                "event_types": ["sync.completed"],
            },
        )
        sub_id = create_resp.json()["id"]

        response = await client.patch(
            f"/webhooks/subscriptions/{sub_id}",
            json={"event_types": ["sync.completed", "sync.failed", "sync.running"]},
        )
        assert response.status_code == 200
        assert set(response.json()["filter_types"]) == {
            "sync.completed",
            "sync.failed",
            "sync.running",
        }

    # -----------------------------------------------------------------
    # RECOVER
    # -----------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_recover_messages(self, client, fake_webhook_service):
        create_resp = await client.post(
            "/webhooks/subscriptions",
            json={
                "url": "https://example.com/hook",
                "event_types": ["sync.completed"],
            },
        )
        sub_id = create_resp.json()["id"]

        response = await client.post(
            f"/webhooks/subscriptions/{sub_id}/recover",
            json={"since": "2024-01-01T00:00:00Z"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["status"] == "completed"

    @pytest.mark.asyncio
    async def test_recover_messages_with_until(self, client, fake_webhook_service):
        create_resp = await client.post(
            "/webhooks/subscriptions",
            json={
                "url": "https://example.com/hook",
                "event_types": ["sync.completed"],
            },
        )
        sub_id = create_resp.json()["id"]

        response = await client.post(
            f"/webhooks/subscriptions/{sub_id}/recover",
            json={
                "since": "2024-01-01T00:00:00Z",
                "until": "2024-02-01T00:00:00Z",
            },
        )
        assert response.status_code == 200


class TestWebhookMessagesAPI:
    """Tests for /webhooks/messages endpoints."""

    @pytest.mark.asyncio
    async def test_list_messages_empty(self, client):
        response = await client.get("/webhooks/messages")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_messages_with_data(self, client, fake_webhook_service):
        now = datetime.now(timezone.utc)
        fake_webhook_service._admin.messages.append(
            EventMessage(
                id="msg_1",
                event_type="sync.completed",
                payload={"status": "completed"},
                timestamp=now,
                channels=["sync.completed"],
            )
        )
        fake_webhook_service._admin.messages.append(
            EventMessage(
                id="msg_2",
                event_type="sync.failed",
                payload={"status": "failed"},
                timestamp=now,
                channels=["sync.failed"],
            )
        )

        response = await client.get("/webhooks/messages")
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 2

    @pytest.mark.asyncio
    async def test_list_messages_filtered_by_event_type(self, client, fake_webhook_service):
        now = datetime.now(timezone.utc)
        fake_webhook_service._admin.messages.extend(
            [
                EventMessage(
                    id="msg_1",
                    event_type="sync.completed",
                    payload={},
                    timestamp=now,
                ),
                EventMessage(
                    id="msg_2",
                    event_type="sync.failed",
                    payload={},
                    timestamp=now,
                ),
            ]
        )

        response = await client.get("/webhooks/messages?event_types=sync.completed")
        assert response.status_code == 200
        messages = response.json()
        assert len(messages) == 1
        assert messages[0]["event_type"] == "sync.completed"

    @pytest.mark.asyncio
    async def test_get_message_by_id(self, client, fake_webhook_service):
        now = datetime.now(timezone.utc)
        fake_webhook_service._admin.messages.append(
            EventMessage(
                id="msg_1",
                event_type="sync.completed",
                payload={"key": "value"},
                timestamp=now,
            )
        )

        response = await client.get("/webhooks/messages/msg_1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "msg_1"
        assert data["payload"] == {"key": "value"}
        assert data["delivery_attempts"] is None

    @pytest.mark.asyncio
    async def test_get_message_with_attempts(self, client, fake_webhook_service):
        now = datetime.now(timezone.utc)
        fake_webhook_service._admin.messages.append(
            EventMessage(
                id="msg_1",
                event_type="sync.completed",
                payload={},
                timestamp=now,
            )
        )

        response = await client.get("/webhooks/messages/msg_1?include_attempts=true")
        assert response.status_code == 200
        data = response.json()
        # FakeWebhookAdmin.get_message_attempts returns []
        assert data["delivery_attempts"] == []

    @pytest.mark.asyncio
    async def test_get_nonexistent_message(self, client):
        response = await client.get("/webhooks/messages/nonexistent-id")
        assert response.status_code == 500  # KeyError from fake
