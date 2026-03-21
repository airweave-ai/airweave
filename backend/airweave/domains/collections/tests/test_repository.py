"""Unit tests for CollectionRepository — status computation and federated lookup."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.core.shared_models import CollectionStatus
from airweave.domains.collections.protocols import CollectionListResult
from airweave.domains.collections.repository import CollectionRepository
from airweave.domains.source_connections.fakes.repository import FakeSourceConnectionRepository
from airweave.schemas.collection import SourceConnectionSummary
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
    "supports_cursor": False,
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
    """Build a minimal SourceRegistryEntry with sensible defaults."""
    return SourceRegistryEntry(short_name=short_name, **{**_ENTRY_DEFAULTS, **overrides})


def _source_registry(federated_map: dict[str, bool] | None = None) -> FakeSourceRegistry:
    """Build a FakeSourceRegistry seeded from a {short_name: federated} map."""
    reg = FakeSourceRegistry()
    for short_name, federated in (federated_map or {}).items():
        reg.seed(_entry(short_name, federated_search=federated))
    return reg


def _repo(
    federated_map: dict[str, bool] | None = None,
    sc_repo: FakeSourceConnectionRepository | None = None,
) -> CollectionRepository:
    return CollectionRepository(
        source_registry=_source_registry(federated_map),
        sc_repo=sc_repo or FakeSourceConnectionRepository(),
    )


# ---------------------------------------------------------------------------
# _federated_lookup
# ---------------------------------------------------------------------------


class TestFederatedLookup:
    def test_returns_true_when_federated(self):
        repo = _repo({"slack": True})
        assert repo._federated_lookup("slack") is True

    def test_returns_false_when_not_federated(self):
        repo = _repo({"github": False})
        assert repo._federated_lookup("github") is False

    def test_returns_false_for_unknown_source(self):
        repo = _repo({})
        assert repo._federated_lookup("nonexistent") is False


# ---------------------------------------------------------------------------
# _compute_collection_status
# ---------------------------------------------------------------------------


class TestComputeCollectionStatus:
    def test_empty_connections_returns_needs_source(self):
        assert CollectionRepository._compute_collection_status([]) == CollectionStatus.NEEDS_SOURCE

    def test_no_authenticated_connections_returns_needs_source(self):
        conns = [{"is_authenticated": False, "federated_search": False, "last_job": None}]
        result = CollectionRepository._compute_collection_status(conns)
        assert result == CollectionStatus.NEEDS_SOURCE

    def test_federated_authenticated_returns_active(self):
        conns = [{"is_authenticated": True, "federated_search": True, "last_job": None}]
        assert CollectionRepository._compute_collection_status(conns) == CollectionStatus.ACTIVE

    def test_completed_sync_returns_active(self):
        conns = [
            {
                "is_authenticated": True,
                "federated_search": False,
                "last_job": {"status": "completed"},
            }
        ]
        assert CollectionRepository._compute_collection_status(conns) == CollectionStatus.ACTIVE

    def test_running_sync_returns_active(self):
        conns = [
            {
                "is_authenticated": True,
                "federated_search": False,
                "last_job": {"status": "running"},
            }
        ]
        assert CollectionRepository._compute_collection_status(conns) == CollectionStatus.ACTIVE

    def test_cancelling_sync_returns_active(self):
        conns = [
            {
                "is_authenticated": True,
                "federated_search": False,
                "last_job": {"status": "cancelling"},
            }
        ]
        assert CollectionRepository._compute_collection_status(conns) == CollectionStatus.ACTIVE

    def test_all_failed_returns_error(self):
        conns = [
            {
                "is_authenticated": True,
                "federated_search": False,
                "last_job": {"status": "failed"},
            },
            {
                "is_authenticated": True,
                "federated_search": False,
                "last_job": {"status": "failed"},
            },
        ]
        assert CollectionRepository._compute_collection_status(conns) == CollectionStatus.ERROR

    def test_mixed_failed_and_working_returns_active(self):
        conns = [
            {
                "is_authenticated": True,
                "federated_search": False,
                "last_job": {"status": "failed"},
            },
            {
                "is_authenticated": True,
                "federated_search": False,
                "last_job": {"status": "completed"},
            },
        ]
        assert CollectionRepository._compute_collection_status(conns) == CollectionStatus.ACTIVE

    def test_no_jobs_yet_returns_needs_source(self):
        conns = [{"is_authenticated": True, "federated_search": False, "last_job": None}]
        result = CollectionRepository._compute_collection_status(conns)
        assert result == CollectionStatus.NEEDS_SOURCE

    def test_last_job_empty_dict_returns_needs_source(self):
        conns = [{"is_authenticated": True, "federated_search": False, "last_job": {}}]
        result = CollectionRepository._compute_collection_status(conns)
        assert result == CollectionStatus.NEEDS_SOURCE


# ---------------------------------------------------------------------------
# _attach_ephemeral_status
# ---------------------------------------------------------------------------


def _sc(
    id=None,
    readable_collection_id="col",
    short_name="github",
    is_authenticated=True,
    name="Test",
):
    """Build a fake SourceConnection-like object for seeding."""
    return SimpleNamespace(
        id=id or uuid4(),
        readable_collection_id=readable_collection_id,
        short_name=short_name,
        is_authenticated=is_authenticated,
        name=name,
    )


def _col(readable_id: str) -> Any:
    return SimpleNamespace(readable_id=readable_id)


def _ctx() -> Any:
    return SimpleNamespace(organization=SimpleNamespace(id=uuid4()))


@pytest.mark.asyncio
class TestAttachEphemeralStatus:
    async def test_empty_collections_returns_empty(self):
        repo = _repo()
        result = await repo._attach_ephemeral_status(None, [], _ctx())
        assert isinstance(result, CollectionListResult)
        assert result.collections == []
        assert result.summaries_by_collection == {}

    async def test_no_source_connections_sets_needs_source(self):
        repo = _repo()
        col = _col("test-col")

        result = await repo._attach_ephemeral_status(None, [col], _ctx())
        assert len(result.collections) == 1
        assert result.collections[0].status == CollectionStatus.NEEDS_SOURCE
        assert result.summaries_by_collection == {}

    async def test_with_connections_computes_status(self):
        sc = _sc(readable_collection_id="my-col", short_name="github", name="GitHub")

        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc.id, sc)
        sc_repo.seed_last_jobs({sc.id: {"status": "completed"}})
        repo = _repo({"github": False}, sc_repo=sc_repo)

        col = _col("my-col")

        result = await repo._attach_ephemeral_status(None, [col], _ctx())

        assert len(result.collections) == 1
        assert result.collections[0].status == CollectionStatus.ACTIVE
        assert result.summaries_by_collection == {
            "my-col": [SourceConnectionSummary(short_name="github", name="GitHub")]
        }

    async def test_federated_source_sets_active(self):
        sc = _sc(readable_collection_id="slack-col", short_name="slack", name="Slack")

        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc.id, sc)
        repo = _repo({"slack": True}, sc_repo=sc_repo)

        col = _col("slack-col")

        result = await repo._attach_ephemeral_status(None, [col], _ctx())

        assert result.collections[0].status == CollectionStatus.ACTIVE
        assert result.summaries_by_collection == {
            "slack-col": [SourceConnectionSummary(short_name="slack", name="Slack")]
        }

    async def test_multiple_connections_builds_grouped_summaries(self):
        sc1 = _sc(readable_collection_id="my-col", short_name="github", name="GitHub")
        sc2 = _sc(readable_collection_id="my-col", short_name="slack", name="Slack")

        sc_repo = FakeSourceConnectionRepository()
        sc_repo.seed(sc1.id, sc1)
        sc_repo.seed(sc2.id, sc2)
        sc_repo.seed_last_jobs({sc1.id: {"status": "completed"}})
        repo = _repo({"github": False, "slack": True}, sc_repo=sc_repo)

        col = _col("my-col")

        result = await repo._attach_ephemeral_status(None, [col], _ctx())

        assert result.collections[0].status == CollectionStatus.ACTIVE
        assert len(result.summaries_by_collection["my-col"]) == 2
        short_names = {s.short_name for s in result.summaries_by_collection["my-col"]}
        assert short_names == {"github", "slack"}


# ---------------------------------------------------------------------------
# Delegating methods (get, get_by_readable_id, get_multi)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestDelegatingMethods:
    async def test_get_returns_none_when_not_found(self):
        repo = _repo()

        with patch("airweave.domains.collections.repository.crud") as mock_crud:
            mock_crud.collection.get = AsyncMock(return_value=None)

            result = await repo.get(MagicMock(), id=uuid4(), ctx=MagicMock())

        assert result is None

    async def test_get_attaches_status(self):
        repo = _repo()
        col = MagicMock()
        col.readable_id = "test"

        with patch("airweave.domains.collections.repository.crud") as mock_crud:
            mock_crud.collection.get = AsyncMock(return_value=col)

            attach = patch.object(repo, "_attach_ephemeral_status", new_callable=AsyncMock)
            with attach as mock_attach:
                mock_attach.return_value = CollectionListResult(collections=[col])

                result = await repo.get(MagicMock(), id=uuid4(), ctx=MagicMock())

        assert result is col
        mock_attach.assert_awaited_once()

    async def test_get_by_readable_id_returns_none_on_not_found(self):
        repo = _repo()

        with patch("airweave.domains.collections.repository.crud") as mock_crud:
            from airweave.core.exceptions import NotFoundException

            mock_crud.collection.get_by_readable_id = AsyncMock(
                side_effect=NotFoundException("not found")
            )

            result = await repo.get_by_readable_id(MagicMock(), readable_id="nope", ctx=MagicMock())

        assert result is None

    async def test_get_by_readable_id_attaches_status(self):
        repo = _repo()
        col = MagicMock()
        col.readable_id = "found"

        with patch("airweave.domains.collections.repository.crud") as mock_crud:
            mock_crud.collection.get_by_readable_id = AsyncMock(return_value=col)

            attach = patch.object(repo, "_attach_ephemeral_status", new_callable=AsyncMock)
            with attach as mock_attach:
                mock_attach.return_value = CollectionListResult(collections=[col])

                result = await repo.get_by_readable_id(
                    MagicMock(), readable_id="found", ctx=MagicMock()
                )

        assert result is col
        mock_attach.assert_awaited_once()

    async def test_get_multi_delegates_and_attaches_status(self):
        repo = _repo()
        cols = [MagicMock(), MagicMock()]
        expected = CollectionListResult(collections=cols)

        with patch("airweave.domains.collections.repository.crud") as mock_crud:
            mock_crud.collection.get_multi = AsyncMock(return_value=cols)

            attach = patch.object(repo, "_attach_ephemeral_status", new_callable=AsyncMock)
            with attach as mock_attach:
                mock_attach.return_value = expected

                result = await repo.get_multi(MagicMock(), ctx=MagicMock())

        assert result is expected
        mock_attach.assert_awaited_once()
