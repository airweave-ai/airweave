"""API tests for auth provider connection endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from airweave import schemas


def _make_connection(readable_id: str = "composio-main") -> schemas.AuthProviderConnection:
    now = datetime.now(timezone.utc)
    return schemas.AuthProviderConnection(
        id=uuid4(),
        name="Composio Main",
        readable_id=readable_id,
        short_name="composio",
        description="Main auth provider connection",
        created_by_email="test@airweave.ai",
        modified_by_email="test@airweave.ai",
        created_at=now,
        modified_at=now,
        masked_client_id="client_1...abcd",
    )


class TestAuthProviderConnections:
    """Tests for /auth-providers/connections endpoints via injected service."""

    @pytest.mark.asyncio
    async def test_list_connections(self, client, fake_auth_provider_service):
        fake_auth_provider_service.seed_connection(_make_connection("composio-main"))
        fake_auth_provider_service.seed_connection(_make_connection("pipedream-main"))

        response = await client.get("/auth-providers/connections/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert {item["readable_id"] for item in data} == {"composio-main", "pipedream-main"}

    @pytest.mark.asyncio
    async def test_get_connection(self, client, fake_auth_provider_service):
        fake_auth_provider_service.seed_connection(_make_connection("composio-main"))

        response = await client.get("/auth-providers/connections/composio-main")
        assert response.status_code == 200
        assert response.json()["readable_id"] == "composio-main"

    @pytest.mark.asyncio
    async def test_create_connection(self, client, fake_auth_provider_service):
        fake_auth_provider_service.seed_connection(_make_connection("composio-main"))

        response = await client.post(
            "/auth-providers/",
            json={
                "name": "Composio Main",
                "readable_id": "composio-main",
                "short_name": "composio",
                "auth_fields": {"api_key": "secret"},
            },
        )
        assert response.status_code == 200
        assert response.json()["readable_id"] == "composio-main"

    @pytest.mark.asyncio
    async def test_update_connection(self, client, fake_auth_provider_service):
        fake_auth_provider_service.seed_connection(_make_connection("composio-main"))

        response = await client.put(
            "/auth-providers/composio-main",
            json={"name": "Composio Main Updated"},
        )
        assert response.status_code == 200
        assert response.json()["readable_id"] == "composio-main"

    @pytest.mark.asyncio
    async def test_delete_connection(self, client, fake_auth_provider_service):
        fake_auth_provider_service.seed_connection(_make_connection("composio-main"))

        response = await client.delete("/auth-providers/composio-main")
        assert response.status_code == 200
        assert response.json()["readable_id"] == "composio-main"
