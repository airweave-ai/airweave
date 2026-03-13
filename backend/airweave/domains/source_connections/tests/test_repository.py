"""Unit tests for SourceConnectionRepository — delegation and enrichment logic."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.source_connections.repository import SourceConnectionRepository
from airweave.domains.source_connections.types import SourceConnectionStats
from airweave.domains.sources.fakes.registry import FakeSourceRegistry
from airweave.domains.sources.types import SourceRegistryEntry
from airweave.platform.configs._base import Fields

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMPTY_FIELDS = Fields(fields=[])

_ENTRY_DEFAULTS: dict = {
    "name": "Test",
    "description": None,
    "class_name": "TestSource",
    "source_class_ref": type,
    "config_ref": None,
    "auth_config_ref": None,
    "auth_fields": _EMPTY_FIELDS,
    "config_fields": _EMPTY_FIELDS,
    "supported_auth_providers": [],
    "runtime_auth_all_fields": [],
    "runtime_auth_optional_fields": set(),
    "auth_methods": None,
    "oauth_type": None,
    "requires_byoc": False,
    "supports_continuous": False,
    "federated_search": False,
    "supports_temporal_relevance": False,
    "supports_access_control": False,
    "supports_browse_tree": False,
    "rate_limit_level": None,
    "feature_flag": None,
    "labels": None,
    "output_entity_definitions": [],
}


def _entry(short_name: str, **overrides) -> SourceRegistryEntry:
    return SourceRegistryEntry(short_name=short_name, **{**_ENTRY_DEFAULTS, **overrides})


def _repo(
    federated_map: dict[str, bool] | None = None,
) -> SourceConnectionRepository:
    reg = FakeSourceRegistry()
    for short_name, federated in (federated_map or {}).items():
        reg.seed(_entry(short_name, federated_search=federated))
    return SourceConnectionRepository(source_registry=reg)


def _stat_row(**overrides) -> dict:
    """Build a minimal stat row dict as returned by crud.source_connection.get_multi_with_stats."""
    now = datetime.now(timezone.utc)
    defaults = {
        "id": uuid4(),
        "name": "Test SC",
        "short_name": "github",
        "readable_collection_id": "col-1",
        "created_at": now,
        "modified_at": now,
        "is_authenticated": True,
        "readable_auth_provider_id": None,
        "connection_init_session_id": None,
        "is_active": True,
        "authentication_method": None,
        "last_job": None,
        "entity_count": 0,
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# get_multi_with_stats — enrichment logic
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetMultiWithStats:
    async def test_enriches_federated_search_true(self):
        repo = _repo({"slack": True})
        row = _stat_row(short_name="slack")

        with patch("airweave.domains.source_connections.repository.crud") as mock_crud:
            mock_crud.source_connection.get_multi_with_stats = AsyncMock(return_value=[row])

            result = await repo.get_multi_with_stats(
                MagicMock(), ctx=MagicMock(), collection_id=None
            )

        assert len(result) == 1
        assert isinstance(result[0], SourceConnectionStats)
        assert result[0].federated_search is True

    async def test_enriches_federated_search_false(self):
        repo = _repo({"github": False})
        row = _stat_row(short_name="github")

        with patch("airweave.domains.source_connections.repository.crud") as mock_crud:
            mock_crud.source_connection.get_multi_with_stats = AsyncMock(return_value=[row])

            result = await repo.get_multi_with_stats(
                MagicMock(), ctx=MagicMock(), collection_id=None
            )

        assert result[0].federated_search is False

    async def test_unknown_source_defaults_federated_to_false(self):
        repo = _repo({})
        row = _stat_row(short_name="unknown_source")

        with patch("airweave.domains.source_connections.repository.crud") as mock_crud:
            mock_crud.source_connection.get_multi_with_stats = AsyncMock(return_value=[row])

            result = await repo.get_multi_with_stats(
                MagicMock(), ctx=MagicMock(), collection_id=None
            )

        assert result[0].federated_search is False

    async def test_empty_rows_returns_empty(self):
        repo = _repo()

        with patch("airweave.domains.source_connections.repository.crud") as mock_crud:
            mock_crud.source_connection.get_multi_with_stats = AsyncMock(return_value=[])

            result = await repo.get_multi_with_stats(
                MagicMock(), ctx=MagicMock(), collection_id=None
            )

        assert result == []


# ---------------------------------------------------------------------------
# get_by_collection_ids
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGetByCollectionIds:
    async def test_returns_matching_connections(self):
        repo = _repo()
        sc = SimpleNamespace(id=uuid4(), short_name="github")

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sc]
        db.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_collection_ids(
            db, organization_id=uuid4(), readable_collection_ids=["col-1"]
        )

        assert result == [sc]
        db.execute.assert_awaited_once()

    async def test_returns_empty_when_no_match(self):
        repo = _repo()

        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_collection_ids(
            db, organization_id=uuid4(), readable_collection_ids=["nonexistent"]
        )

        assert result == []


# ---------------------------------------------------------------------------
# fetch_last_jobs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestFetchLastJobs:
    async def test_delegates_to_crud(self):
        repo = _repo()
        sc_id = uuid4()
        sc = SimpleNamespace(id=sc_id)
        expected = {sc_id: {"status": "completed"}}

        with patch("airweave.domains.source_connections.repository.crud") as mock_crud:
            mock_crud.source_connection._fetch_last_jobs = AsyncMock(return_value=expected)

            result = await repo.fetch_last_jobs(MagicMock(), [sc])

        assert result == expected
