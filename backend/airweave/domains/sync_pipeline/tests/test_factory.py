"""Tests for SyncFactory — DI wiring and create_orchestrator edge cases."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.sync_pipeline.factory import SyncFactory


def _build_factory(**overrides):
    """Build a SyncFactory with mock deps, accepting per-test overrides."""
    defaults = {
        "sc_repo": MagicMock(),
        "event_bus": MagicMock(),
        "usage_checker": MagicMock(),
        "dense_embedder": MagicMock(),
        "sparse_embedder": MagicMock(),
        "entity_repo": MagicMock(),
        "acl_repo": MagicMock(),
        "processor": MagicMock(),
    }
    defaults.update(overrides)
    return SyncFactory(**defaults)


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------


def test_constructor_stores_all_deps():
    """All injected deps are stored on the instance."""
    deps = {
        "sc_repo": MagicMock(),
        "event_bus": MagicMock(),
        "usage_checker": MagicMock(),
        "dense_embedder": MagicMock(),
        "sparse_embedder": MagicMock(),
        "entity_repo": MagicMock(),
        "acl_repo": MagicMock(),
        "processor": MagicMock(),
    }
    f = SyncFactory(**deps)
    assert f._sc_repo is deps["sc_repo"]
    assert f._event_bus is deps["event_bus"]
    assert f._usage_checker is deps["usage_checker"]
    assert f._dense_embedder is deps["dense_embedder"]
    assert f._sparse_embedder is deps["sparse_embedder"]
    assert f._entity_repo is deps["entity_repo"]
    assert f._acl_repo is deps["acl_repo"]
    assert f._processor is deps["processor"]


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
            "airweave.domains.sync_pipeline.factory.TrackingContextBuilder"
        ) as mock_track_builder,
        patch(
            "airweave.domains.sync_pipeline.factory.SyncFactory._build_source",
            new_callable=AsyncMock,
        ) as mock_build_source,
        patch(
            "airweave.domains.sync_pipeline.factory.SyncFactory._build_destinations",
            new_callable=AsyncMock,
        ) as mock_build_destinations,
    ):
        mock_build_source.return_value = (MagicMock(), MagicMock())
        mock_build_destinations.return_value = ([], {})
        mock_track_builder.build = AsyncMock(return_value=MagicMock())
        mock_sc_builder.build = AsyncMock(return_value=MagicMock())
        mock_disp_builder.build = MagicMock(return_value=MagicMock())

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
