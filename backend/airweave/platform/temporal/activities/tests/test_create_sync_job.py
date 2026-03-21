"""Tests for CreateSyncJobActivity."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from airweave.adapters.event_bus.fake import FakeEventBus
from airweave.core.exceptions import NotFoundException
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.connections.fakes.repository import FakeConnectionRepository
from airweave.domains.source_connections.fakes.repository import FakeSourceConnectionRepository
from airweave.domains.syncs.fakes.sync_job_repository import FakeSyncJobRepository
from airweave.domains.syncs.fakes.sync_repository import FakeSyncRepository
from airweave.platform.temporal.activities.create_sync_job import CreateSyncJobActivity

from .conftest import ORG_ID, SYNC_ID, make_ctx_dict

MODULE = "airweave.platform.temporal.activities.create_sync_job"


@asynccontextmanager
async def _fake_db():
    yield AsyncMock()


def _make_sync_model():
    model = MagicMock()
    model.id = UUID(SYNC_ID)
    model.name = "test-sync"
    model.organization_id = UUID(ORG_ID)
    return model


@pytest.fixture
def event_bus():
    return FakeEventBus()


@pytest.fixture
def sync_repo():
    repo = FakeSyncRepository()
    repo.seed_model(UUID(SYNC_ID), _make_sync_model())
    return repo


@pytest.fixture
def sync_job_repo():
    return FakeSyncJobRepository()


@pytest.fixture
def sc_repo():
    return FakeSourceConnectionRepository()


@pytest.fixture
def conn_repo():
    return FakeConnectionRepository()


@pytest.fixture
def collection_repo():
    return FakeCollectionRepository()


@pytest.fixture
def activity(event_bus, sync_repo, sync_job_repo, sc_repo, conn_repo, collection_repo):
    return CreateSyncJobActivity(
        event_bus=event_bus,
        sync_repo=sync_repo,
        sync_job_repo=sync_job_repo,
        sc_repo=sc_repo,
        conn_repo=conn_repo,
        collection_repo=collection_repo,
    )


@pytest.mark.unit
async def test_creates_sync_job(activity, sync_job_repo):
    with patch(f"{MODULE}.get_db_context", _fake_db):
        result = await activity.run(
            sync_id=SYNC_ID,
            ctx_dict=make_ctx_dict(),
        )

    assert "id" in result
    assert result.get("_orphaned") is None
    assert result.get("_skipped") is None

    create_calls = [c for c in sync_job_repo._calls if c[0] == "create"]
    assert len(create_calls) == 1


@pytest.mark.unit
async def test_returns_orphaned_when_sync_missing(activity, sync_repo):
    sync_repo._models.clear()

    async def raise_not_found(*args, **kwargs):
        raise NotFoundException("Sync not found")

    sync_repo.get_without_connections = raise_not_found

    with patch(f"{MODULE}.get_db_context", _fake_db):
        result = await activity.run(
            sync_id=SYNC_ID,
            ctx_dict=make_ctx_dict(),
        )

    assert result["_orphaned"] is True
    assert result["sync_id"] == SYNC_ID


@pytest.mark.unit
async def test_skips_when_job_already_running(activity, sync_job_repo):
    running_job = MagicMock()
    running_job.sync_id = UUID(SYNC_ID)
    running_job.organization_id = UUID(ORG_ID)
    running_job.status = "RUNNING"
    sync_job_repo.seed_jobs_for_sync(UUID(SYNC_ID), [running_job])

    with patch(f"{MODULE}.get_db_context", _fake_db):
        result = await activity.run(
            sync_id=SYNC_ID,
            ctx_dict=make_ctx_dict(),
        )

    assert result["_skipped"] is True
    assert "Already has" in result["reason"]
