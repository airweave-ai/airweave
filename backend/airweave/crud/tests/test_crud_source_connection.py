"""Unit tests for CRUDSourceConnection sync-status helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.core.shared_models import SyncStatus
from airweave.crud.crud_source_connection import CRUDSourceConnection
from airweave.models.source_connection import SourceConnection


def _crud() -> CRUDSourceConnection:
    return CRUDSourceConnection(SourceConnection)


# ---------------------------------------------------------------------------
# _fetch_sync_statuses
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_sync_statuses_returns_mapping():
    """Maps sync status back to source connection IDs."""
    crud = _crud()
    sc_id, sync_id = uuid4(), uuid4()
    sc = SimpleNamespace(id=sc_id, sync_id=sync_id)

    mock_db = AsyncMock()
    mock_db.execute.return_value = [SimpleNamespace(id=sync_id, status="paused")]

    result = await crud._fetch_sync_statuses(mock_db, [sc])  # type: ignore[list-item]

    assert result == {sc_id: SyncStatus.PAUSED}


@pytest.mark.asyncio
async def test_fetch_sync_statuses_empty_when_no_sync_ids():
    """Returns empty dict when no source connections have sync_id."""
    crud = _crud()
    sc = SimpleNamespace(id=uuid4(), sync_id=None)

    mock_db = AsyncMock()
    result = await crud._fetch_sync_statuses(mock_db, [sc])  # type: ignore[list-item]

    assert result == {}
    mock_db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_fetch_sync_statuses_skips_unknown_sync_ids():
    """Rows with sync IDs not in the source connection list are ignored."""
    crud = _crud()
    sc_id, sync_id = uuid4(), uuid4()
    sc = SimpleNamespace(id=sc_id, sync_id=sync_id)
    unknown_sync_id = uuid4()

    mock_db = AsyncMock()
    mock_db.execute.return_value = [
        SimpleNamespace(id=sync_id, status="active"),
        SimpleNamespace(id=unknown_sync_id, status="paused"),
    ]

    result = await crud._fetch_sync_statuses(mock_db, [sc])  # type: ignore[list-item]

    assert result == {sc_id: SyncStatus.ACTIVE}


# ---------------------------------------------------------------------------
# get_multi_with_stats — covers the _fetch_sync_statuses call site (line 101)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_multi_with_stats_includes_sync_status():
    """get_multi_with_stats passes sync_status through in result dicts."""
    crud = _crud()
    sc_id, sync_id, org_id = uuid4(), uuid4(), uuid4()

    sc = SimpleNamespace(
        id=sc_id,
        sync_id=sync_id,
        organization_id=org_id,
        name="Test SC",
        short_name="test",
        readable_collection_id="col-1",
        created_at=None,
        modified_at=None,
        is_authenticated=True,
        readable_auth_provider_id=None,
        connection_init_session_id=None,
        is_active=True,
    )

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [sc]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars

    mock_db = AsyncMock()
    mock_db.execute.return_value = mock_result

    ctx = SimpleNamespace(organization=SimpleNamespace(id=org_id))

    with (
        patch.object(crud, "_fetch_auth_methods", new_callable=AsyncMock, return_value={}),
        patch.object(crud, "_fetch_last_jobs", new_callable=AsyncMock, return_value={}),
        patch.object(crud, "_fetch_entity_counts", new_callable=AsyncMock, return_value={}),
        patch.object(
            crud,
            "_fetch_sync_statuses",
            new_callable=AsyncMock,
            return_value={sc_id: SyncStatus.PAUSED},
        ),
    ):
        results = await crud.get_multi_with_stats(mock_db, ctx=ctx)

    assert len(results) == 1
    assert results[0]["sync_status"] == SyncStatus.PAUSED
