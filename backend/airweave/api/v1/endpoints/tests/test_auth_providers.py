"""API tests for auth provider connection endpoints."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from airweave import schemas
from airweave.api.v1.endpoints import auth_providers as auth_providers_endpoint
from airweave.platform.configs._base import BaseConfig


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


class _AuthConfig(BaseConfig):
    api_key: str


class _ProviderConfig(BaseConfig):
    account_id: str = ""


class TestAuthProviderMetadata:
    """Tests for /auth-providers/list and /auth-providers/detail/{short_name}."""

    @pytest.mark.asyncio
    async def test_list_auth_providers(self, client, monkeypatch):
        now = datetime.now(timezone.utc)
        provider = SimpleNamespace(
            id=uuid4(),
            name="Composio",
            short_name="composio",
            class_name="ComposioAuthProvider",
            auth_config_class="ComposioAuthConfig",
            config_class="ComposioConfig",
            description="Composio provider",
            organization_id=None,
            created_at=now,
            modified_at=now,
        )
        monkeypatch.setattr(
            auth_providers_endpoint.crud.auth_provider,
            "get_multi",
            AsyncMock(return_value=[provider]),
        )
        monkeypatch.setattr(auth_providers_endpoint.resource_locator, "get_auth_config", lambda _: _AuthConfig)
        monkeypatch.setattr(auth_providers_endpoint.resource_locator, "get_config", lambda _: _ProviderConfig)

        response = await client.get("/auth-providers/list")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["short_name"] == "composio"
        assert data[0]["auth_fields"] is not None
        assert data[0]["config_fields"] is not None

    @pytest.mark.asyncio
    async def test_list_auth_providers_no_auth_config_class(self, client, monkeypatch):
        now = datetime.now(timezone.utc)
        provider = SimpleNamespace(
            id=uuid4(),
            name="NoConfig",
            short_name="no_config",
            class_name="NoConfigProvider",
            auth_config_class="",
            config_class="",
            description="No config provider",
            organization_id=None,
            created_at=now,
            modified_at=now,
        )
        monkeypatch.setattr(
            auth_providers_endpoint.crud.auth_provider,
            "get_multi",
            AsyncMock(return_value=[provider]),
        )

        response = await client.get("/auth-providers/list")
        assert response.status_code == 200
        assert response.json()[0]["short_name"] == "no_config"

    @pytest.mark.asyncio
    async def test_list_auth_providers_config_error_sets_none(self, client, monkeypatch):
        now = datetime.now(timezone.utc)
        provider = SimpleNamespace(
            id=uuid4(),
            name="Composio",
            short_name="composio",
            class_name="ComposioAuthProvider",
            auth_config_class="ComposioAuthConfig",
            config_class="ComposioConfig",
            description="Composio provider",
            organization_id=None,
            created_at=now,
            modified_at=now,
        )
        monkeypatch.setattr(
            auth_providers_endpoint.crud.auth_provider,
            "get_multi",
            AsyncMock(return_value=[provider]),
        )
        monkeypatch.setattr(auth_providers_endpoint.resource_locator, "get_auth_config", lambda _: _AuthConfig)
        monkeypatch.setattr(
            auth_providers_endpoint.resource_locator,
            "get_config",
            lambda _: (_ for _ in ()).throw(RuntimeError("config failed")),
        )

        response = await client.get("/auth-providers/list")
        assert response.status_code == 200
        assert response.json()[0]["config_fields"] is None

    @pytest.mark.asyncio
    async def test_list_auth_providers_provider_processing_fallback(self, client, monkeypatch):
        now = datetime.now(timezone.utc)
        bad_provider = SimpleNamespace(
            id=uuid4(),
            name="Broken",
            short_name="broken",
            class_name="BrokenProvider",
            auth_config_class="BrokenAuthConfig",
            config_class="BrokenConfig",
            description="broken",
            organization_id=None,
            created_at=now,
            modified_at=now,
        )
        monkeypatch.setattr(
            auth_providers_endpoint.crud.auth_provider,
            "get_multi",
            AsyncMock(return_value=[bad_provider]),
        )
        monkeypatch.setattr(
            auth_providers_endpoint.resource_locator,
            "get_auth_config",
            lambda _: (_ for _ in ()).throw(RuntimeError("broken auth config")),
        )

        response = await client.get("/auth-providers/list")
        assert response.status_code == 200
        assert response.json()[0]["short_name"] == "broken"

    @pytest.mark.asyncio
    async def test_get_auth_provider_detail(self, client, monkeypatch):
        now = datetime.now(timezone.utc)
        provider = SimpleNamespace(
            id=uuid4(),
            name="Composio",
            short_name="composio",
            class_name="ComposioAuthProvider",
            auth_config_class="ComposioAuthConfig",
            config_class="ComposioConfig",
            description="Composio provider",
            organization_id=None,
            created_at=now,
            modified_at=now,
        )
        monkeypatch.setattr(
            auth_providers_endpoint.crud.auth_provider,
            "get_by_short_name",
            AsyncMock(return_value=provider),
        )
        monkeypatch.setattr(auth_providers_endpoint.resource_locator, "get_auth_config", lambda _: _AuthConfig)
        monkeypatch.setattr(auth_providers_endpoint.resource_locator, "get_config", lambda _: _ProviderConfig)

        response = await client.get("/auth-providers/detail/composio")
        assert response.status_code == 200
        body = response.json()
        assert body["short_name"] == "composio"
        assert body["auth_fields"] is not None

    @pytest.mark.asyncio
    async def test_get_auth_provider_detail_not_found(self, client, monkeypatch):
        monkeypatch.setattr(
            auth_providers_endpoint.crud.auth_provider,
            "get_by_short_name",
            AsyncMock(return_value=None),
        )

        response = await client.get("/auth-providers/detail/missing")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_auth_provider_detail_config_error_sets_none(self, client, monkeypatch):
        now = datetime.now(timezone.utc)
        provider = SimpleNamespace(
            id=uuid4(),
            name="Composio",
            short_name="composio",
            class_name="ComposioAuthProvider",
            auth_config_class="ComposioAuthConfig",
            config_class="ComposioConfig",
            description="Composio provider",
            organization_id=None,
            created_at=now,
            modified_at=now,
        )
        monkeypatch.setattr(
            auth_providers_endpoint.crud.auth_provider,
            "get_by_short_name",
            AsyncMock(return_value=provider),
        )
        monkeypatch.setattr(auth_providers_endpoint.resource_locator, "get_auth_config", lambda _: _AuthConfig)
        monkeypatch.setattr(
            auth_providers_endpoint.resource_locator,
            "get_config",
            lambda _: (_ for _ in ()).throw(RuntimeError("config failed")),
        )

        response = await client.get("/auth-providers/detail/composio")
        assert response.status_code == 200
        assert response.json()["config_fields"] is None

    @pytest.mark.asyncio
    async def test_get_auth_provider_detail_outer_exception_returns_raw_provider(
        self, client, monkeypatch
    ):
        now = datetime.now(timezone.utc)
        provider = SimpleNamespace(
            id=uuid4(),
            name="Composio",
            short_name="composio",
            class_name="ComposioAuthProvider",
            auth_config_class="ComposioAuthConfig",
            config_class="ComposioConfig",
            description="Composio provider",
            organization_id=None,
            created_at=now,
            modified_at=now,
        )
        monkeypatch.setattr(
            auth_providers_endpoint.crud.auth_provider,
            "get_by_short_name",
            AsyncMock(return_value=provider),
        )
        monkeypatch.setattr(
            auth_providers_endpoint.resource_locator,
            "get_auth_config",
            lambda _: (_ for _ in ()).throw(RuntimeError("auth config failed")),
        )

        response = await client.get("/auth-providers/detail/composio")
        assert response.status_code == 200
        assert response.json()["short_name"] == "composio"
