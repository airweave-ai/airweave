"""Unit tests for ConnectionRepository."""

from unittest.mock import AsyncMock

import pytest

from airweave.core.shared_models import IntegrationType
from airweave.domains.connections.repository import ConnectionRepository


@pytest.mark.asyncio
async def test_get_by_integration_type_delegates(monkeypatch):
    expected = ["conn-1"]
    mock = AsyncMock(return_value=expected)
    monkeypatch.setattr(
        "airweave.domains.connections.repository.crud.connection.get_by_integration_type",
        mock,
    )

    repo = ConnectionRepository()
    result = await repo.get_by_integration_type(
        "db",
        integration_type=IntegrationType.AUTH_PROVIDER,
        ctx="ctx",
    )
    assert result == expected


@pytest.mark.asyncio
async def test_update_delegates(monkeypatch):
    expected = {"ok": True}
    mock = AsyncMock(return_value=expected)
    monkeypatch.setattr("airweave.domains.connections.repository.crud.connection.update", mock)

    repo = ConnectionRepository()
    result = await repo.update(
        "db",
        db_obj="connection",
        obj_in={"name": "new"},
        ctx="ctx",
        uow="uow",
    )
    assert result == expected


@pytest.mark.asyncio
async def test_remove_delegates(monkeypatch):
    expected = {"deleted": True}
    mock = AsyncMock(return_value=expected)
    monkeypatch.setattr("airweave.domains.connections.repository.crud.connection.remove", mock)

    repo = ConnectionRepository()
    result = await repo.remove("db", id="uuid", ctx="ctx")
    assert result == expected
