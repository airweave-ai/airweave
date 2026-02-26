"""Unit tests for FakeSourceConnectionService."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.core.exceptions import NotFoundException
from airweave.domains.source_connections.fakes.delete import FakeSourceConnectionDeletionService
from airweave.domains.source_connections.fakes.service import FakeSourceConnectionService
from airweave.domains.syncs.fakes.sync_lifecycle_service import FakeSyncLifecycleService


def _make_source_connection():
    source_connection = MagicMock()
    source_connection.id = uuid4()
    return source_connection


async def test_delete_delegation_removes_fake_store_entry_on_success():
    source_connection = _make_source_connection()
    deletion_service = FakeSourceConnectionDeletionService()
    deletion_service.seed_response(source_connection.id, MagicMock())

    service = FakeSourceConnectionService(
        sync_lifecycle=FakeSyncLifecycleService(),
        deletion_service=deletion_service,
    )
    service.seed(source_connection.id, source_connection)

    await service.delete(AsyncMock(), source_connection.id, MagicMock())

    with pytest.raises(NotFoundException, match="Source connection not found"):
        await service.get(AsyncMock(), id=source_connection.id, ctx=MagicMock())


async def test_delete_delegation_keeps_fake_store_entry_when_delegate_raises():
    source_connection = _make_source_connection()
    deletion_service = FakeSourceConnectionDeletionService()
    deletion_service.set_should_raise(RuntimeError("boom"))

    service = FakeSourceConnectionService(
        sync_lifecycle=FakeSyncLifecycleService(),
        deletion_service=deletion_service,
    )
    service.seed(source_connection.id, source_connection)

    with pytest.raises(RuntimeError, match="boom"):
        await service.delete(AsyncMock(), source_connection.id, MagicMock())

    result = await service.get(AsyncMock(), id=source_connection.id, ctx=MagicMock())
    assert result is source_connection
