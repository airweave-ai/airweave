"""Tests for SyncFactory — DI wiring and create_orchestrator edge cases."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.sync_pipeline.factory import SourceBuildResult, SyncFactory


def _build_factory(**overrides):
    """Build a SyncFactory with mock deps, accepting per-test overrides."""
    defaults = {
        # Repositories
        "sc_repo": MagicMock(),
        "entity_repo": MagicMock(),
        "entity_count_repo": MagicMock(),
        "acl_repo": MagicMock(),
        "selection_repo": MagicMock(),
        # Registries
        "entity_definition_registry": MagicMock(),
        "source_registry": MagicMock(),
        # Services
        "source_lifecycle_service": MagicMock(),
        "sync_cursor_service": MagicMock(),
        "processor": MagicMock(),
        "arf_service": MagicMock(),
        # Infrastructure
        "event_bus": MagicMock(),
        "usage_checker": MagicMock(),
        "usage_ledger": MagicMock(),
        "storage_backend": MagicMock(),
        "state_machine": MagicMock(),
    }
    defaults.update(overrides)
    return SyncFactory(**defaults)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_constructor_stores_all_deps():
    """All injected deps are stored on the instance."""
    deps = {
        # Repositories
        "sc_repo": MagicMock(),
        "entity_repo": MagicMock(),
        "entity_count_repo": MagicMock(),
        "acl_repo": MagicMock(),
        "selection_repo": MagicMock(),
        # Registries
        "entity_definition_registry": MagicMock(),
        "source_registry": MagicMock(),
        # Services
        "source_lifecycle_service": MagicMock(),
        "sync_cursor_service": MagicMock(),
        "processor": MagicMock(),
        "arf_service": MagicMock(),
        # Infrastructure
        "event_bus": MagicMock(),
        "usage_checker": MagicMock(),
        "usage_ledger": MagicMock(),
        "storage_backend": MagicMock(),
        "state_machine": MagicMock(),
    }
    f = SyncFactory(**deps)
    assert f._sc_repo is deps["sc_repo"]
    assert f._entity_repo is deps["entity_repo"]
    assert f._entity_count_repo is deps["entity_count_repo"]
    assert f._acl_repo is deps["acl_repo"]
    assert f._selection_repo is deps["selection_repo"]
    assert f._entity_definition_registry is deps["entity_definition_registry"]
    assert f._source_registry is deps["source_registry"]
    assert f._source_lifecycle_service is deps["source_lifecycle_service"]
    assert f._sync_cursor_service is deps["sync_cursor_service"]
    assert f._processor is deps["processor"]
    assert f._arf_service is deps["arf_service"]
    assert f._event_bus is deps["event_bus"]
    assert f._usage_checker is deps["usage_checker"]
    assert f._usage_ledger is deps["usage_ledger"]
    assert f._storage_backend is deps["storage_backend"]


# ---------------------------------------------------------------------------
# create_orchestrator — sc_repo returns None → NotFoundException
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_orchestrator_raises_when_source_connection_missing():
    """NotFoundException when sc_repo.get_by_sync_id returns None."""
    from airweave.core.exceptions import NotFoundException

    sc_repo = MagicMock()
    sc_repo.get_by_sync_id = AsyncMock(return_value=None)

    factory = _build_factory(sc_repo=sc_repo)

    sync = MagicMock()
    sync.id = uuid4()
    sync.sync_config = None
    sync_job = MagicMock()
    sync_job.sync_config = None
    collection = MagicMock()
    collection.sync_config = None
    connection = MagicMock()
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = uuid4()
    db = AsyncMock()

    with pytest.raises(NotFoundException, match="Source connection record not found"):
        await factory.create_orchestrator(
            db=db,
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,
            ctx=ctx,
        )


# ---------------------------------------------------------------------------
# create_orchestrator — happy path wires entity_repo into resolver/pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_orchestrator_passes_entity_repo_to_pipeline():
    """entity_repo is forwarded to EntityActionResolver and EntityPipeline."""
    entity_repo = MagicMock()
    sc_repo = MagicMock()
    sc = MagicMock()
    sc.id = uuid4()
    sc_repo.get_by_sync_id = AsyncMock(return_value=sc)

    factory = _build_factory(sc_repo=sc_repo, entity_repo=entity_repo)

    sync = MagicMock()
    sync.id = uuid4()
    sync.sync_config = None
    sync_job = MagicMock()
    sync_job.id = uuid4()
    sync_job.sync_config = None
    collection = MagicMock()
    collection.sync_config = None
    collection.readable_id = uuid4()
    connection = MagicMock()
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = uuid4()
    db = AsyncMock()

    with (
        patch("airweave.domains.sync_pipeline.factory.SyncContextBuilder") as mock_sc_builder,
        patch(
            "airweave.domains.sync_pipeline.factory.EntityDispatcherBuilder"
        ) as mock_disp_builder,
        patch(
            "airweave.domains.sync_pipeline.factory.SyncFactory._build_source",
            new_callable=AsyncMock,
        ) as mock_build_source,
        patch(
            "airweave.domains.sync_pipeline.factory.SyncFactory._build_destinations",
            new_callable=AsyncMock,
        ) as mock_build_destinations,
        patch(
            "airweave.domains.sync_pipeline.factory.SyncFactory._build_entity_tracker",
            new_callable=AsyncMock,
        ) as mock_build_tracker,
    ):
        mock_source = MagicMock()
        mock_source.generate_entities = MagicMock(return_value=AsyncMock())
        mock_build_source.return_value = SourceBuildResult(
            source=mock_source, cursor=MagicMock(), files=MagicMock(), node_selections=[]
        )
        mock_build_destinations.return_value = []
        mock_build_tracker.return_value = MagicMock()
        mock_sc_builder.build = AsyncMock(return_value=MagicMock())
        mock_disp_builder_instance = MagicMock()
        mock_disp_builder_instance.build = MagicMock(return_value=MagicMock())
        mock_disp_builder.return_value = mock_disp_builder_instance

        orchestrator = await factory.create_orchestrator(
            db=db,
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            connection=connection,
            ctx=ctx,
        )

        assert orchestrator is not None
        assert orchestrator.entity_pipeline._entity_repo is entity_repo
        assert orchestrator.entity_pipeline._resolver._entity_repo is entity_repo


# ---------------------------------------------------------------------------
# Private method tests
# ---------------------------------------------------------------------------


def _make_ctx(org_id=None):
    ctx = MagicMock()
    ctx.organization = MagicMock()
    ctx.organization.id = org_id or uuid4()
    return ctx


def _make_sync(sync_id=None):
    s = MagicMock()
    s.id = sync_id or uuid4()
    return s


def _make_sync_job(job_id=None):
    j = MagicMock()
    j.id = job_id or uuid4()
    return j


class TestBuildSource:
    @pytest.mark.asyncio
    async def test_returns_source_cursor_files_selections(self):
        sc = MagicMock()
        sc.id = uuid4()
        sc.short_name = "github"
        sc.config_fields = {}
        mock_source = MagicMock()
        mock_lifecycle = MagicMock()
        mock_lifecycle.create = AsyncMock(return_value=mock_source)

        factory = _build_factory(source_lifecycle_service=mock_lifecycle)
        db = AsyncMock()
        sync = _make_sync()
        sync_job = _make_sync_job()
        ctx = _make_ctx()

        with (
            patch(
                "airweave.domains.sync_pipeline.factory.SyncFactory._validate_not_completed_snapshot"
            ),
            patch(
                "airweave.domains.sync_pipeline.factory.SyncFactory._create_cursor",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "airweave.domains.sync_pipeline.factory.SyncFactory._load_node_selections",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch("airweave.domains.sync_pipeline.factory.FileService"),
        ):
            result = await factory._build_source(
                db=db,
                sync=sync,
                sync_job=sync_job,
                ctx=ctx,
                logger=MagicMock(),
                source_connection=sc,
                force_full_sync=False,
                execution_config=None,
            )

        assert result.source is mock_source
        assert result.cursor is not None
        assert result.files is not None
        assert result.node_selections == []

    @pytest.mark.asyncio
    async def test_returns_node_selections_when_present(self):
        sc = MagicMock()
        sc.id = uuid4()
        sc.short_name = "github"
        sc.config_fields = {}
        mock_source = MagicMock()
        mock_lifecycle = MagicMock()
        mock_lifecycle.create = AsyncMock(return_value=mock_source)
        fake_selection = MagicMock()

        factory = _build_factory(source_lifecycle_service=mock_lifecycle)
        db = AsyncMock()
        sync = _make_sync()
        sync_job = _make_sync_job()
        ctx = _make_ctx()

        with (
            patch(
                "airweave.domains.sync_pipeline.factory.SyncFactory._validate_not_completed_snapshot"
            ),
            patch(
                "airweave.domains.sync_pipeline.factory.SyncFactory._create_cursor",
                new_callable=AsyncMock,
                return_value=MagicMock(),
            ),
            patch(
                "airweave.domains.sync_pipeline.factory.SyncFactory._load_node_selections",
                new_callable=AsyncMock,
                return_value=[fake_selection],
            ),
            patch("airweave.domains.sync_pipeline.factory.FileService"),
        ):
            result = await factory._build_source(
                db=db,
                sync=sync,
                sync_job=sync_job,
                ctx=ctx,
                logger=MagicMock(),
                source_connection=sc,
                force_full_sync=False,
                execution_config=None,
            )

        assert result.node_selections == [fake_selection]


class TestBuildArfReplaySource:
    @pytest.mark.asyncio
    async def test_raises_not_found_when_no_arf_data(self):
        from airweave.core.exceptions import NotFoundException

        mock_source = AsyncMock()
        mock_source.validate = AsyncMock(
            side_effect=NotFoundException(
                "ARF data not found for sync. "
                "Cannot replay - ensure ARF capture was enabled for previous syncs."
            )
        )

        factory = _build_factory()
        db = AsyncMock()
        sync = _make_sync()
        ctx = _make_ctx()

        with (
            patch(
                "airweave.domains.sync_pipeline.factory.crud.source_connection.get_by_sync_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "airweave.domains.arf.replay_source.ArfReplaySource.create",
                new_callable=AsyncMock,
                return_value=mock_source,
            ),
        ):
            with pytest.raises(NotFoundException, match="ARF data not found"):
                await factory._build_arf_replay_source(
                    db=db, sync=sync, ctx=ctx, logger=MagicMock()
                )

    @pytest.mark.asyncio
    async def test_success_returns_source_build_result(self):
        mock_source = AsyncMock()
        mock_source.validate = AsyncMock(return_value=True)

        factory = _build_factory()
        db = AsyncMock()
        sync = _make_sync()
        ctx = _make_ctx()

        with (
            patch(
                "airweave.domains.sync_pipeline.factory.crud.source_connection.get_by_sync_id",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "airweave.domains.arf.replay_source.ArfReplaySource.create",
                new_callable=AsyncMock,
                return_value=mock_source,
            ),
        ):
            result = await factory._build_arf_replay_source(
                db=db, sync=sync, ctx=ctx, logger=MagicMock()
            )

        assert result.source is mock_source
        assert result.cursor.sync_id == sync.id
        assert result.files is None
        assert result.node_selections is None


class TestValidateNotCompletedSnapshot:
    def test_passes_for_snapshot_short_name(self):
        """short_name == 'snapshot' → guard skipped entirely."""
        sc = SimpleNamespace(short_name="snapshot", config_fields={}, name="my-snap")
        SyncFactory._validate_not_completed_snapshot(sc)  # should not raise

    def test_passes_for_normal_source_with_invalid_snapshot_config(self):
        """Normal source with config that fails SnapshotConfig parsing → no exception."""
        sc = SimpleNamespace(short_name="github", config_fields={"not": "snapshot"}, name="gh")
        SyncFactory._validate_not_completed_snapshot(sc)  # should not raise (ValidationError caught)

    def test_raises_for_restored_snapshot_source(self):
        """Source with non-snapshot short_name but valid SnapshotConfig fields → SyncFailureError."""
        from airweave.domains.sync_pipeline.exceptions import SyncFailureError

        sc = SimpleNamespace(short_name="github", config_fields={}, name="restored-snap")
        with patch(
            "airweave.platform.configs.config.SnapshotConfig.__init__",
            return_value=None,
        ):
            with pytest.raises(SyncFailureError, match="Cannot re-sync a completed snapshot"):
                SyncFactory._validate_not_completed_snapshot(sc)


class TestCreateCursor:
    @pytest.mark.asyncio
    async def test_returns_none_when_source_has_no_cursor(self):
        mock_entry = MagicMock()
        mock_entry.supports_cursor = False
        mock_registry = MagicMock()
        mock_registry.get = MagicMock(return_value=mock_entry)

        factory = _build_factory(source_registry=mock_registry)
        db = AsyncMock()
        sync = _make_sync()
        ctx = _make_ctx()
        source_class = MagicMock()
        source_class.short_name = "test_source"

        cursor = await factory._create_cursor(
            db=db,
            sync=sync,
            source_class=source_class,
            ctx=ctx,
            logger=MagicMock(),
            force_full_sync=False,
            execution_config=None,
        )

        assert cursor is None

    @pytest.mark.asyncio
    async def test_skips_cursor_load_when_force_full_sync(self):
        mock_entry = MagicMock()
        mock_entry.supports_cursor = True
        mock_registry = MagicMock()
        mock_registry.get = MagicMock(return_value=mock_entry)
        mock_cursor_service = MagicMock()
        mock_cursor_service.get_cursor_data = AsyncMock()

        factory = _build_factory(
            source_registry=mock_registry,
            sync_cursor_service=mock_cursor_service,
        )
        db = AsyncMock()
        sync = _make_sync()
        ctx = _make_ctx()
        source_class = MagicMock()
        source_class.short_name = "test_source"
        source_class.cursor_class = MagicMock()
        source_class.cursor_class.__name__ = "TestCursor"

        cursor = await factory._create_cursor(
            db=db,
            sync=sync,
            source_class=source_class,
            ctx=ctx,
            logger=MagicMock(),
            force_full_sync=True,
            execution_config=None,
        )

        mock_cursor_service.get_cursor_data.assert_not_awaited()
        assert cursor is not None

    @pytest.mark.asyncio
    async def test_loads_cursor_from_service_when_incremental(self):
        mock_entry = MagicMock()
        mock_entry.supports_cursor = True
        mock_registry = MagicMock()
        mock_registry.get = MagicMock(return_value=mock_entry)
        mock_data = {"key": "value"}
        mock_cursor_service = MagicMock()
        mock_cursor_service.get_cursor_data = AsyncMock(return_value=mock_data)

        factory = _build_factory(
            source_registry=mock_registry,
            sync_cursor_service=mock_cursor_service,
        )
        db = AsyncMock()
        sync = _make_sync()
        ctx = _make_ctx()
        source_class = MagicMock()
        source_class.short_name = "test_source"
        source_class.cursor_class = None  # None → raw dict storage in SyncCursor

        cursor = await factory._create_cursor(
            db=db,
            sync=sync,
            source_class=source_class,
            ctx=ctx,
            logger=MagicMock(),
            force_full_sync=False,
            execution_config=None,
        )

        assert cursor.cursor_data == mock_data
        assert cursor.loaded_from_db is True


class TestBuildEntityTracker:
    @pytest.mark.asyncio
    async def test_returns_tracker_with_initial_counts(self):
        db = AsyncMock()
        sync = _make_sync()
        sync_job = _make_sync_job()
        ctx = _make_ctx()
        count_row = SimpleNamespace(
            entity_definition_short_name="github_pr",
            entity_definition_name="GithubPr",
            entity_definition_type="standard",
            entity_definition_description="A GitHub pull request",
            count=5,
        )

        entity_count_repo = MagicMock()
        entity_count_repo.get_counts_per_sync_and_type = AsyncMock(return_value=[count_row])
        factory = _build_factory(entity_count_repo=entity_count_repo)

        tracker = await factory._build_entity_tracker(
            db=db, sync=sync, sync_job=sync_job, ctx=ctx
        )

        assert tracker is not None
        assert tracker.job_id == sync_job.id

    @pytest.mark.asyncio
    async def test_returns_tracker_with_empty_counts(self):
        db = AsyncMock()
        sync = _make_sync()
        sync_job = _make_sync_job()
        ctx = _make_ctx()

        entity_count_repo = MagicMock()
        entity_count_repo.get_counts_per_sync_and_type = AsyncMock(return_value={})
        factory = _build_factory(entity_count_repo=entity_count_repo)

        tracker = await factory._build_entity_tracker(
            db=db, sync=sync, sync_job=sync_job, ctx=ctx
        )

        assert tracker is not None


class TestLoadNodeSelections:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_rows(self):
        selection_repo = MagicMock()
        selection_repo.get_by_source_connection = AsyncMock(return_value=[])
        factory = _build_factory(selection_repo=selection_repo)
        ctx = _make_ctx()
        db = AsyncMock()

        result = await factory._load_node_selections(db, uuid4(), ctx)

        assert result == []

    @pytest.mark.asyncio
    async def test_converts_rows_to_node_selection_data(self):
        row = SimpleNamespace(
            source_node_id="node-1",
            node_type="file",
            node_title="My File",
            node_metadata={"extra": "info"},
        )
        selection_repo = MagicMock()
        selection_repo.get_by_source_connection = AsyncMock(return_value=[row])
        factory = _build_factory(selection_repo=selection_repo)
        ctx = _make_ctx()
        db = AsyncMock()

        result = await factory._load_node_selections(db, uuid4(), ctx)

        assert len(result) == 1
        assert result[0].source_node_id == "node-1"
        assert result[0].node_type == "file"
