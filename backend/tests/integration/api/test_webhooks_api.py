"""API integration tests for webhook endpoints.

Demonstrates the pattern: hit real FastAPI endpoints with an async client,
but all infrastructure (Svix, DB, auth) is replaced by fakes injected via
the test_container and overridden get_context.

Fixtures used:
- client: from conftest (AsyncClient with faked DI)
- fake_webhook_admin: from root conftest (FakeWebhookAdmin)
"""

import pytest


class TestWebhookSubscriptionsAPI:
    """Tests for /webhooks/subscriptions endpoints."""

    @pytest.mark.asyncio
    async def test_list_subscriptions_empty(self, client):
        response = await client.get("/webhooks/subscriptions")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_create_subscription(self, client, fake_webhook_admin):
        payload = {
            "url": "https://example.com/webhook",
            "event_types": ["sync.completed", "sync.failed"],
        }
        response = await client.post("/webhooks/subscriptions", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["url"] == "https://example.com/webhook"
        # API schema maps domain event_types -> filter_types
        assert "sync.completed" in data["filter_types"]
        assert "sync.failed" in data["filter_types"]

        # Verify the fake recorded the operation
        fake_webhook_admin.assert_subscription_created("https://example.com/webhook")

    @pytest.mark.asyncio
    async def test_list_subscriptions_after_create(self, client, fake_webhook_admin):
        # Create a subscription first
        payload = {
            "url": "https://example.com/hook",
            "event_types": ["sync.completed"],
        }
        await client.post("/webhooks/subscriptions", json=payload)

        # Now list
        response = await client.get("/webhooks/subscriptions")
        assert response.status_code == 200

        subs = response.json()
        assert len(subs) == 1
        assert subs[0]["url"] == "https://example.com/hook"


class TestWebhookMessagesAPI:
    """Tests for /webhooks/messages endpoints."""

    @pytest.mark.asyncio
    async def test_list_messages_empty(self, client):
        response = await client.get("/webhooks/messages")
        assert response.status_code == 200
        assert response.json() == []
