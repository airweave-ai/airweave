"""API tests for auth provider connection endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from airweave import schemas
from airweave.domains.auth_provider.types import AuthProviderMetadata
from airweave.platform.configs._base import Fields


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


class TestAuthProviderMetadata:
    """Tests for /auth-providers/list and /auth-providers/detail/{short_name}."""

    @pytest.mark.asyncio
    async def test_list_auth_providers(self, client, fake_auth_provider_service):
        fake_auth_provider_service.seed_metadata(
            AuthProviderMetadata(
                short_name="composio",
                name="Composio",
                description="Composio provider",
                class_name="ComposioAuthProvider",
                auth_config_class="ComposioAuthConfig",
                config_class="ComposioConfig",
                auth_fields=Fields(fields=[]),
                config_fields=Fields(fields=[]),
            )
        )

        response = await client.get("/auth-providers/list")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["short_name"] == "composio"
        assert data[0]["auth_fields"] is not None
        assert data[0]["config_fields"] is not None

    @pytest.mark.asyncio
    async def test_list_auth_providers_can_return_empty(self, client, fake_auth_provider_service):
        response = await client.get("/auth-providers/list")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_get_auth_provider_detail(self, client, fake_auth_provider_service):
        fake_auth_provider_service.seed_metadata(
            AuthProviderMetadata(
                short_name="composio",
                name="Composio",
                description="Composio provider",
                class_name="ComposioAuthProvider",
                auth_config_class="ComposioAuthConfig",
                config_class="ComposioConfig",
                auth_fields=Fields(fields=[]),
                config_fields=Fields(fields=[]),
            )
        )

        response = await client.get("/auth-providers/detail/composio")
        assert response.status_code == 200
        body = response.json()
        assert body["short_name"] == "composio"
        assert body["auth_fields"] is not None

    @pytest.mark.asyncio
    async def test_get_auth_provider_detail_not_found(self, client):
        response = await client.get("/auth-providers/detail/missing")
        assert response.status_code == 404
        assert response.json()["detail"] == "Auth provider not found: missing"
