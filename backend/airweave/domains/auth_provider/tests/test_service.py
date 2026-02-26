"""Unit tests for AuthProviderService."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import BaseModel

from airweave.core.shared_models import IntegrationType
from airweave.domains.auth_provider.service import AuthProviderService
from airweave.domains.auth_provider.types import AuthProviderRegistryEntry
from airweave.platform.configs._base import Fields


class _AuthConfig(BaseModel):
    api_key: str
    client_id: str | None = None


class _BadAuthConfig:
    def __init__(self, **kwargs):
        raise RuntimeError("boom")


class _ProviderInstance:
    def __init__(self):
        self.logger = None
        self.should_fail = False
        self.http_error = False

    def set_logger(self, logger):
        self.logger = logger

    async def validate(self):
        if self.http_error:
            raise HTTPException(status_code=418, detail="teapot")
        if self.should_fail:
            raise RuntimeError("validate failed")


class _ProviderClass:
    instance = _ProviderInstance()

    @classmethod
    async def create(cls, credentials, config):
        return cls.instance


def _entry(short_name: str = "composio", auth_config_ref: type = _AuthConfig) -> AuthProviderRegistryEntry:
    return AuthProviderRegistryEntry(
        short_name=short_name,
        name="Composio",
        description="Composio",
        class_name="ComposioProvider",
        provider_class_ref=_ProviderClass,
        config_ref=_AuthConfig,
        auth_config_ref=auth_config_ref,
        config_fields=Fields(fields=[]),
        auth_config_fields=Fields(fields=[]),
        blocked_sources=[],
        field_name_mapping={},
        slug_name_mapping={},
    )


def _ctx(has_user_context: bool = True):
    logger = SimpleNamespace(info=lambda *a, **k: None, error=lambda *a, **k: None)
    return SimpleNamespace(
        logger=logger,
        has_user_context=has_user_context,
        tracking_email="owner@airweave.ai",
    )


def _service(entry_obj: AuthProviderRegistryEntry | None = None):
    entry_obj = entry_obj or _entry()
    registry = SimpleNamespace(get=lambda short_name: entry_obj)
    connection_repo = SimpleNamespace(
        get_by_integration_type=AsyncMock(return_value=[]),
        get_by_readable_id=AsyncMock(return_value=None),
        create=AsyncMock(),
        update=AsyncMock(),
        remove=AsyncMock(),
    )
    credential_repo = SimpleNamespace(
        get=AsyncMock(return_value=None),
        create=AsyncMock(),
        update=AsyncMock(),
    )
    return (
        AuthProviderService(registry, connection_repo, credential_repo),
        connection_repo,
        credential_repo,
    )


class _DummyUow:
    session = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock(), add=AsyncMock())

    def __init__(self, db):
        self.db = db
        self.session = _DummyUow.session

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_list_connections_maps_and_applies_pagination(monkeypatch):
    service, connection_repo, _ = _service()
    c1 = SimpleNamespace(id=uuid4())
    c2 = SimpleNamespace(id=uuid4())
    c3 = SimpleNamespace(id=uuid4())
    connection_repo.get_by_integration_type = AsyncMock(return_value=[c1, c2, c3])
    service._to_schema = AsyncMock(side_effect=["a", "b", "c"])

    result = await service.list_connections("db", ctx=_ctx(), skip=1, limit=1)
    assert result == ["a"]


@pytest.mark.asyncio
async def test_get_connection_maps_schema():
    service, _, _ = _service()
    conn = SimpleNamespace(id=uuid4())
    service._get_auth_provider_connection = AsyncMock(return_value=conn)
    service._to_schema = AsyncMock(return_value="mapped")

    result = await service.get_connection("db", readable_id="conn-1", ctx=_ctx())
    assert result == "mapped"


@pytest.mark.asyncio
async def test_create_connection_happy_path(monkeypatch):
    service, connection_repo, credential_repo = _service()
    monkeypatch.setattr("airweave.domains.auth_provider.service.UnitOfWork", _DummyUow)
    monkeypatch.setattr("airweave.domains.auth_provider.service.credentials.encrypt", lambda data: "enc")
    service._validate_credentials = AsyncMock()
    service._to_schema = AsyncMock(return_value="response")

    credential_repo.create = AsyncMock(return_value=SimpleNamespace(id=uuid4()))
    connection_repo.create = AsyncMock(
        return_value=SimpleNamespace(
            id=uuid4(),
            name="n",
            readable_id="rid",
            short_name="composio",
            description="d",
            created_by_email=None,
            modified_by_email=None,
            created_at=SimpleNamespace(),
            modified_at=SimpleNamespace(),
        )
    )

    obj_in = SimpleNamespace(name="Composio Conn", short_name="composio", readable_id="rid", auth_fields={"api_key": "k"})
    result = await service.create_connection("db", obj_in=obj_in, ctx=_ctx())
    assert result == "response"
    assert credential_repo.create.await_count == 1
    assert connection_repo.create.await_count == 1


@pytest.mark.asyncio
async def test_update_connection_branches(monkeypatch):
    service, connection_repo, _ = _service()
    monkeypatch.setattr("airweave.domains.auth_provider.service.UnitOfWork", _DummyUow)
    service._to_schema = AsyncMock(return_value="updated")
    service._update_auth_credentials = AsyncMock()
    conn = SimpleNamespace(
        id=uuid4(),
        integration_credential_id=uuid4(),
        short_name="composio",
        readable_id="rid",
        integration_type=IntegrationType.AUTH_PROVIDER,
        name="old",
        description="old",
        created_by_email=None,
        modified_by_email=None,
        created_at=SimpleNamespace(),
        modified_at=SimpleNamespace(),
    )
    service._get_auth_provider_connection = AsyncMock(return_value=conn)

    update = SimpleNamespace(name="new", description="new-desc", auth_fields={"api_key": "k"})
    result = await service.update_connection("db", readable_id="rid", obj_in=update, ctx=_ctx())
    assert result == "updated"
    assert connection_repo.update.await_count == 1
    assert _DummyUow.session.flush.await_count >= 1
    assert _DummyUow.session.refresh.await_count >= 1


@pytest.mark.asyncio
async def test_update_connection_no_updates(monkeypatch):
    service, connection_repo, _ = _service()
    monkeypatch.setattr("airweave.domains.auth_provider.service.UnitOfWork", _DummyUow)
    service._to_schema = AsyncMock(return_value="updated")
    conn = SimpleNamespace(
        id=uuid4(),
        integration_credential_id=uuid4(),
        short_name="composio",
        readable_id="rid",
        integration_type=IntegrationType.AUTH_PROVIDER,
        name="old",
        description="old",
        created_by_email=None,
        modified_by_email=None,
        created_at=SimpleNamespace(),
        modified_at=SimpleNamespace(),
    )
    service._get_auth_provider_connection = AsyncMock(return_value=conn)
    update = SimpleNamespace(name=None, description=None, auth_fields=None)

    result = await service.update_connection("db", readable_id="rid", obj_in=update, ctx=_ctx(False))
    assert result == "updated"
    assert connection_repo.update.await_count == 0


@pytest.mark.asyncio
async def test_delete_connection(monkeypatch):
    service, connection_repo, _ = _service()
    service._to_schema = AsyncMock(return_value="deleted")
    conn = SimpleNamespace(id=uuid4())
    service._get_auth_provider_connection = AsyncMock(return_value=conn)

    result = await service.delete_connection("db", readable_id="rid", ctx=_ctx())
    assert result == "deleted"
    connection_repo.remove.assert_awaited_once()


def test_get_registry_entry_not_found():
    service, _, _ = _service()
    service._registry = SimpleNamespace(get=lambda short_name: (_ for _ in ()).throw(KeyError("missing")))
    with pytest.raises(HTTPException) as exc:
        service._get_registry_entry("missing")
    assert exc.value.status_code == 404


def test_validate_auth_fields_paths():
    service, _, _ = _service(_entry(auth_config_ref=_AuthConfig))
    out = service._validate_auth_fields(_entry(auth_config_ref=_AuthConfig), {"api_key": "x"})
    assert out["api_key"] == "x"

    class Dumpable:
        def model_dump(self):
            return {"api_key": "k"}

    out2 = service._validate_auth_fields(_entry(auth_config_ref=_AuthConfig), Dumpable())
    assert out2["api_key"] == "k"

    with pytest.raises(HTTPException) as missing:
        service._validate_auth_fields(_entry(auth_config_ref=_AuthConfig), None)
    assert missing.value.status_code == 422

    with pytest.raises(HTTPException) as invalid:
        service._validate_auth_fields(_entry(auth_config_ref=_AuthConfig), {})
    assert invalid.value.status_code == 422

    with pytest.raises(HTTPException) as generic:
        service._validate_auth_fields(_entry(auth_config_ref=_BadAuthConfig), {"api_key": "x"})
    assert generic.value.status_code == 422


@pytest.mark.asyncio
async def test_validate_credentials_paths():
    service, _, _ = _service()
    ctx = _ctx()
    await service._validate_credentials(
        entry=_entry(),
        validated_auth_fields={"api_key": "x"},
        validated_provider_config={},
        ctx=ctx,
    )

    _ProviderClass.instance.should_fail = True
    with pytest.raises(HTTPException) as exc:
        await service._validate_credentials(
            entry=_entry(),
            validated_auth_fields={"api_key": "x"},
            validated_provider_config={},
            ctx=ctx,
        )
    assert exc.value.status_code == 422
    _ProviderClass.instance.should_fail = False

    _ProviderClass.instance.http_error = True
    with pytest.raises(HTTPException) as http_exc:
        await service._validate_credentials(
            entry=_entry(),
            validated_auth_fields={"api_key": "x"},
            validated_provider_config={},
            ctx=ctx,
        )
    assert http_exc.value.status_code == 418
    _ProviderClass.instance.http_error = False


@pytest.mark.asyncio
async def test_update_auth_credentials_paths(monkeypatch):
    service, _, credential_repo = _service()
    monkeypatch.setattr("airweave.domains.auth_provider.service.credentials.encrypt", lambda data: "enc")
    uow = SimpleNamespace(
        session=SimpleNamespace(flush=AsyncMock()),
    )
    connection = SimpleNamespace(short_name="composio", integration_credential_id=None)
    with pytest.raises(HTTPException) as missing:
        await service._update_auth_credentials(
            uow=uow, connection=connection, auth_fields={"api_key": "x"}, ctx=_ctx()
        )
    assert missing.value.status_code == 500

    connection.integration_credential_id = uuid4()
    credential_repo.get = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as not_found:
        await service._update_auth_credentials(
            uow=uow, connection=connection, auth_fields={"api_key": "x"}, ctx=_ctx()
        )
    assert not_found.value.status_code == 404

    credential = SimpleNamespace(id=uuid4())
    credential_repo.get = AsyncMock(return_value=credential)
    credential_repo.update = AsyncMock(return_value=credential)
    await service._update_auth_credentials(
        uow=uow, connection=connection, auth_fields={"api_key": "x"}, ctx=_ctx()
    )
    assert credential_repo.update.await_count == 1


@pytest.mark.asyncio
async def test_get_masked_client_id_paths(monkeypatch):
    service, _, credential_repo = _service()
    ctx = _ctx()
    connection = SimpleNamespace(integration_credential_id=None)
    assert await service._get_masked_client_id("db", connection=connection, ctx=ctx) is None

    connection.integration_credential_id = uuid4()
    credential_repo.get = AsyncMock(return_value=None)
    assert await service._get_masked_client_id("db", connection=connection, ctx=ctx) is None

    credential_repo.get = AsyncMock(return_value=SimpleNamespace(encrypted_credentials="enc"))
    monkeypatch.setattr("airweave.domains.auth_provider.service.credentials.decrypt", lambda _: {})
    assert await service._get_masked_client_id("db", connection=connection, ctx=ctx) is None

    monkeypatch.setattr(
        "airweave.domains.auth_provider.service.credentials.decrypt",
        lambda _: {"client_id": "abcd1234"},
    )
    assert (await service._get_masked_client_id("db", connection=connection, ctx=ctx)) == "abcd..."

    monkeypatch.setattr(
        "airweave.domains.auth_provider.service.credentials.decrypt",
        lambda _: {"client_id": "client_1234567890_abcd"},
    )
    assert (await service._get_masked_client_id("db", connection=connection, ctx=ctx)) == (
        "client_...abcd"
    )

    def _raise(_):
        raise RuntimeError("decrypt fail")

    monkeypatch.setattr("airweave.domains.auth_provider.service.credentials.decrypt", _raise)
    assert await service._get_masked_client_id("db", connection=connection, ctx=ctx) is None


@pytest.mark.asyncio
async def test_get_auth_provider_connection_paths():
    service, connection_repo, _ = _service()
    connection_repo.get_by_readable_id = AsyncMock(return_value=None)
    with pytest.raises(HTTPException) as missing:
        await service._get_auth_provider_connection("db", readable_id="rid", ctx=_ctx())
    assert missing.value.status_code == 404

    bad = SimpleNamespace(integration_type=IntegrationType.DESTINATION)
    connection_repo.get_by_readable_id = AsyncMock(return_value=bad)
    with pytest.raises(HTTPException) as wrong_type:
        await service._get_auth_provider_connection("db", readable_id="rid", ctx=_ctx())
    assert wrong_type.value.status_code == 400

    good = SimpleNamespace(integration_type=IntegrationType.AUTH_PROVIDER)
    connection_repo.get_by_readable_id = AsyncMock(return_value=good)
    out = await service._get_auth_provider_connection("db", readable_id="rid", ctx=_ctx())
    assert out is good


@pytest.mark.asyncio
async def test_to_schema_include_and_exclude_masked():
    service, _, _ = _service()
    service._get_masked_client_id = AsyncMock(return_value="client_1...abcd")
    conn = SimpleNamespace(
        id=uuid4(),
        name="Composio",
        readable_id="rid",
        short_name="composio",
        description="desc",
        created_by_email=None,
        modified_by_email=None,
        created_at=datetime.now(timezone.utc),
        modified_at=datetime.now(timezone.utc),
    )
    with_mask = await service._to_schema("db", conn, _ctx(), include_masked_client_id=True)
    assert with_mask.masked_client_id == "client_1...abcd"

    no_mask = await service._to_schema("db", conn, _ctx(), include_masked_client_id=False)
    assert no_mask.masked_client_id is None
