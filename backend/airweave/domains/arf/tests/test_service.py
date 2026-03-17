"""Unit tests for ArfService.

Covers:
- _safe_filename (sanitization, hashing for long/complex IDs)
- _serialize_entity (class info, captured_at)
- upsert_entities (single, batch, file entity handling)
- delete_entities (existing, missing)
- get_entity_count, sync_exists, delete_sync
- get_manifest, upsert_manifest (create and update)
- cleanup_stale_entities
- get_replay_stats

Uses a FakeStorageBackend to avoid any real I/O.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from airweave.domains.arf.service import ArfService
from airweave.domains.arf.types import SyncManifest
from airweave.domains.storage.exceptions import StorageNotFoundError
from airweave.domains.storage.fakes import FakeStorageBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYNC_ID = str(uuid4())
JOB_ID = str(uuid4())
COLLECTION_ID = str(uuid4())
ORG_ID = str(uuid4())



class _TestEntity:
    """Lightweight entity stand-in for testing."""

    def __init__(self, entity_id: str, name: str) -> None:
        self.entity_id = entity_id
        self.name = name

    def model_dump(self, mode: str = "json") -> Dict[str, Any]:
        return {"entity_id": self.entity_id, "name": self.name}


class FileEntity:
    """Base class whose name triggers _is_file_entity MRO check."""


class _TestFileEntity(FileEntity):
    """File-bearing entity for testing file storage paths."""

    def __init__(self, entity_id: str, name: str, local_path: str | None = None) -> None:
        self.entity_id = entity_id
        self.name = name
        self.local_path = local_path

    def model_dump(self, mode: str = "json") -> Dict[str, Any]:
        return {"entity_id": self.entity_id, "name": self.name}


def _make_entity(entity_id: str = "ent-1", name: str = "Test Entity") -> _TestEntity:
    return _TestEntity(entity_id=entity_id, name=name)


def _make_file_entity(
    entity_id: str = "file-1", name: str = "Test File", local_path: str | None = None
) -> _TestFileEntity:
    return _TestFileEntity(entity_id=entity_id, name=name, local_path=local_path)


def _make_sync_context(sync_id: str = SYNC_ID) -> Any:
    sync = SimpleNamespace(id=sync_id)
    sync_job = SimpleNamespace(id=JOB_ID)
    collection = SimpleNamespace(
        id=COLLECTION_ID,
        readable_id="test-collection",
        organization_id=ORG_ID,
    )
    logger = SimpleNamespace(
        debug=lambda *a, **kw: None,
        info=lambda *a, **kw: None,
        warning=lambda *a, **kw: None,
    )
    return SimpleNamespace(sync=sync, sync_job=sync_job, collection=collection, logger=logger)


def _make_runtime(source_short_name: str = "github") -> Any:
    source = SimpleNamespace(short_name=source_short_name)
    dense_embedder = SimpleNamespace(dimensions=768, model_name="test-embed")
    entity_tracker = SimpleNamespace(get_all_encountered_ids_flat=lambda: set())
    return SimpleNamespace(
        source=source, dense_embedder=dense_embedder, entity_tracker=entity_tracker
    )


def _build_service() -> tuple:
    storage = FakeStorageBackend()
    svc = ArfService(storage=storage)
    return svc, storage


# ---------------------------------------------------------------------------
# Tests: _safe_filename
# ---------------------------------------------------------------------------


@dataclass
class SafeFilenameCase:
    desc: str
    value: str
    expect_contains: str


SAFE_FILENAME_CASES = [
    SafeFilenameCase("simple id", "abc-123", "abc-123"),
    SafeFilenameCase("slashes sanitized", "path/to/thing", "path_to_thing"),
    SafeFilenameCase("long id gets hash", "x" * 250, "x"),
]


@pytest.mark.parametrize("case", SAFE_FILENAME_CASES, ids=lambda c: c.desc)
def test_safe_filename(case: SafeFilenameCase):
    result = ArfService._safe_filename(case.value)
    assert case.expect_contains in result
    assert len(result) <= 200


# ---------------------------------------------------------------------------
# Tests: upsert_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_entities_stores_batch():
    svc, storage = _build_service()
    ctx = _make_sync_context()
    entities = [_make_entity(f"ent-{i}") for i in range(3)]
    count = await svc.upsert_entities(entities, ctx)
    assert count == 3


@pytest.mark.asyncio
async def test_upsert_entities_batches_across_boundary():
    """Entities exceeding _UPSERT_BATCH_SIZE are stored correctly."""
    svc, storage = _build_service()
    ctx = _make_sync_context()
    n = svc._UPSERT_BATCH_SIZE + 10
    entities = [_make_entity(f"ent-{i}") for i in range(n)]
    count = await svc.upsert_entities(entities, ctx)
    assert count == n
    assert await svc.get_entity_count(SYNC_ID) == n


@pytest.mark.asyncio
async def test_upsert_entity_overwrites():
    svc, storage = _build_service()
    ctx = _make_sync_context()
    e = _make_entity("ent-1", name="v1")
    await svc.upsert_entity(e, ctx)
    e2 = _make_entity("ent-1", name="v2")
    await svc.upsert_entity(e2, ctx)

    entity_path = svc._entity_path(SYNC_ID, "ent-1")
    stored = await storage.read_json(entity_path)
    assert stored["name"] == "v2"


# ---------------------------------------------------------------------------
# Tests: delete_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_entity_existing():
    svc, storage = _build_service()
    ctx = _make_sync_context()
    await svc.upsert_entity(_make_entity("ent-1"), ctx)
    deleted = await svc.delete_entity("ent-1", ctx)
    assert deleted is True


@pytest.mark.asyncio
async def test_delete_entity_missing():
    svc, storage = _build_service()
    ctx = _make_sync_context()
    deleted = await svc.delete_entity("nonexistent", ctx)
    assert deleted is False


@pytest.mark.asyncio
async def test_delete_entities_batch():
    svc, storage = _build_service()
    ctx = _make_sync_context()
    await svc.upsert_entities([_make_entity(f"ent-{i}") for i in range(3)], ctx)
    count = await svc.delete_entities(["ent-0", "ent-1", "ent-99"], ctx)
    assert count == 2


# ---------------------------------------------------------------------------
# Tests: get_entity_count, sync_exists, delete_sync
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_entity_count():
    svc, storage = _build_service()
    ctx = _make_sync_context()
    await svc.upsert_entities([_make_entity(f"e-{i}") for i in range(5)], ctx)
    count = await svc.get_entity_count(SYNC_ID)
    assert count == 5


@pytest.mark.asyncio
async def test_sync_exists_false():
    svc, _ = _build_service()
    assert await svc.sync_exists("nonexistent") is False


@pytest.mark.asyncio
async def test_sync_exists_with_manifest():
    svc, storage = _build_service()
    ctx = _make_sync_context()
    runtime = _make_runtime()
    await svc.upsert_manifest(ctx, runtime)
    assert await svc.sync_exists(SYNC_ID) is True


@pytest.mark.asyncio
async def test_delete_sync():
    svc, storage = _build_service()
    ctx = _make_sync_context()
    runtime = _make_runtime()
    await svc.upsert_manifest(ctx, runtime)
    deleted = await svc.delete_sync(SYNC_ID)
    assert deleted is True
    assert await svc.sync_exists(SYNC_ID) is False


# ---------------------------------------------------------------------------
# Tests: manifest management
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_manifest_creates():
    svc, _ = _build_service()
    ctx = _make_sync_context()
    runtime = _make_runtime("github")
    await svc.upsert_manifest(ctx, runtime)
    manifest = await svc.get_manifest(SYNC_ID)
    assert manifest is not None
    assert manifest.sync_id == SYNC_ID
    assert manifest.source_short_name == "github"
    assert JOB_ID in manifest.sync_jobs


@pytest.mark.asyncio
async def test_upsert_manifest_updates():
    svc, _ = _build_service()
    ctx = _make_sync_context()
    runtime = _make_runtime()
    await svc.upsert_manifest(ctx, runtime)

    new_job_id = str(uuid4())
    ctx2 = _make_sync_context()
    ctx2.sync_job = SimpleNamespace(id=new_job_id)
    await svc.upsert_manifest(ctx2, runtime)

    manifest = await svc.get_manifest(SYNC_ID)
    assert len(manifest.sync_jobs) == 2
    assert new_job_id in manifest.sync_jobs


@pytest.mark.asyncio
async def test_get_manifest_missing():
    svc, _ = _build_service()
    assert await svc.get_manifest("nonexistent") is None


# ---------------------------------------------------------------------------
# Tests: get_replay_stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_replay_stats_no_store():
    svc, _ = _build_service()
    stats = await svc.get_replay_stats("nonexistent")
    assert stats == {"exists": False}


@pytest.mark.asyncio
async def test_get_replay_stats_with_data():
    svc, _ = _build_service()
    ctx = _make_sync_context()
    runtime = _make_runtime("notion")
    await svc.upsert_manifest(ctx, runtime)
    await svc.upsert_entities([_make_entity(f"e-{i}") for i in range(3)], ctx)
    stats = await svc.get_replay_stats(SYNC_ID)
    assert stats["exists"] is True
    assert stats["source"] == "notion"
    assert stats["entity_count"] == 3


# ---------------------------------------------------------------------------
# Tests: _file_path
# ---------------------------------------------------------------------------


def test_file_path_with_filename():
    svc, _ = _build_service()
    path = svc._file_path("sync-1", "ent-1", "report.pdf")
    assert "files/" in path
    assert "report" in path
    assert path.endswith(".pdf")


def test_file_path_without_filename():
    svc, _ = _build_service()
    path = svc._file_path("sync-1", "ent-1")
    assert "files/" in path
    assert "ent-1" in path


# ---------------------------------------------------------------------------
# Tests: _is_file_entity
# ---------------------------------------------------------------------------


def test_is_file_entity_true():
    entity = _make_file_entity()
    assert ArfService._is_file_entity(entity) is True


def test_is_file_entity_false():
    entity = _make_entity()
    assert ArfService._is_file_entity(entity) is False


# ---------------------------------------------------------------------------
# Tests: file entity upsert / update / delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_file_entity_stores_file(tmp_path):
    svc, storage = _build_service()
    ctx = _make_sync_context()

    test_file = tmp_path / "report.pdf"
    test_file.write_bytes(b"PDF content here")

    entity = _make_file_entity("file-1", "Report", local_path=str(test_file))
    await svc.upsert_entity(entity, ctx)

    entity_path = svc._entity_path(SYNC_ID, "file-1")
    stored = await storage.read_json(entity_path)
    assert "__stored_file__" in stored

    file_content = await storage.read_file(stored["__stored_file__"])
    assert file_content == b"PDF content here"


@pytest.mark.asyncio
async def test_upsert_file_entity_without_local_path():
    """File entity with no local_path should store normally without __stored_file__."""
    svc, storage = _build_service()
    ctx = _make_sync_context()

    entity = _make_file_entity("file-2", "No File")
    await svc.upsert_entity(entity, ctx)

    entity_path = svc._entity_path(SYNC_ID, "file-2")
    stored = await storage.read_json(entity_path)
    assert "__stored_file__" not in stored


@pytest.mark.asyncio
async def test_upsert_file_entity_update_cleans_old_file(tmp_path):
    svc, storage = _build_service()
    ctx = _make_sync_context()

    old_file = tmp_path / "old.pdf"
    old_file.write_bytes(b"old content")
    entity = _make_file_entity("file-1", "V1", local_path=str(old_file))
    await svc.upsert_entity(entity, ctx)

    entity_path = svc._entity_path(SYNC_ID, "file-1")
    old_stored = await storage.read_json(entity_path)
    old_file_path = old_stored["__stored_file__"]

    new_file = tmp_path / "new.pdf"
    new_file.write_bytes(b"new content")
    entity2 = _make_file_entity("file-1", "V2", local_path=str(new_file))
    await svc.upsert_entity(entity2, ctx)

    assert not await storage.exists(old_file_path)

    new_stored = await storage.read_json(entity_path)
    new_content = await storage.read_file(new_stored["__stored_file__"])
    assert new_content == b"new content"


@pytest.mark.asyncio
async def test_delete_entity_with_stored_file(tmp_path):
    svc, storage = _build_service()
    ctx = _make_sync_context()

    test_file = tmp_path / "doc.txt"
    test_file.write_bytes(b"content")
    entity = _make_file_entity("file-1", "Doc", local_path=str(test_file))
    await svc.upsert_entity(entity, ctx)

    entity_path = svc._entity_path(SYNC_ID, "file-1")
    stored = await storage.read_json(entity_path)
    file_path = stored["__stored_file__"]

    deleted = await svc.delete_entity("file-1", ctx)
    assert deleted is True
    assert not await storage.exists(file_path)


# ---------------------------------------------------------------------------
# Tests: get_entity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_entity_existing():
    svc, _ = _build_service()
    ctx = _make_sync_context()
    await svc.upsert_entity(_make_entity("ent-1", "Hello"), ctx)
    result = await svc.get_entity(SYNC_ID, "ent-1")
    assert result is not None
    assert result["name"] == "Hello"


@pytest.mark.asyncio
async def test_get_entity_missing():
    svc, _ = _build_service()
    result = await svc.get_entity(SYNC_ID, "nonexistent")
    assert result is None


# ---------------------------------------------------------------------------
# Tests: iter_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_iter_entities():
    svc, _ = _build_service()
    ctx = _make_sync_context()
    await svc.upsert_entities([_make_entity(f"e-{i}") for i in range(5)], ctx)

    collected = []
    async for entity_dict in svc.iter_entities(SYNC_ID, batch_size=2):
        collected.append(entity_dict)
    assert len(collected) == 5


@pytest.mark.asyncio
async def test_iter_entities_empty():
    svc, _ = _build_service()
    collected = []
    async for entity_dict in svc.iter_entities("nonexistent"):
        collected.append(entity_dict)
    assert collected == []


# ---------------------------------------------------------------------------
# Tests: cleanup_stale_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cleanup_stale_entities_removes_unseen():
    svc, _ = _build_service()
    ctx = _make_sync_context()
    await svc.upsert_entities([_make_entity(f"e-{i}") for i in range(4)], ctx)

    seen = {"e-0", "e-2"}
    runtime = _make_runtime()
    runtime.entity_tracker = SimpleNamespace(get_all_encountered_ids_flat=lambda: seen)

    removed = await svc.cleanup_stale_entities(ctx, runtime)
    assert removed == 2


@pytest.mark.asyncio
async def test_cleanup_stale_entities_nothing_stale():
    svc, _ = _build_service()
    ctx = _make_sync_context()
    await svc.upsert_entities([_make_entity(f"e-{i}") for i in range(2)], ctx)

    seen = {"e-0", "e-1"}
    runtime = _make_runtime()
    runtime.entity_tracker = SimpleNamespace(get_all_encountered_ids_flat=lambda: seen)

    removed = await svc.cleanup_stale_entities(ctx, runtime)
    assert removed == 0


@pytest.mark.asyncio
async def test_cleanup_stale_entities_uses_filename_comparison_not_json_reads():
    """Cleanup should not read entity JSONs to determine staleness (perf)."""
    svc, storage = _build_service()
    ctx = _make_sync_context()
    await svc.upsert_entities([_make_entity(f"e-{i}") for i in range(3)], ctx)

    seen = {"e-0", "e-1", "e-2"}
    runtime = _make_runtime()
    runtime.entity_tracker = SimpleNamespace(get_all_encountered_ids_flat=lambda: seen)

    read_json_calls = []
    original_read_json = storage.read_json

    async def tracking_read_json(path):
        read_json_calls.append(path)
        return await original_read_json(path)

    storage.read_json = tracking_read_json

    removed = await svc.cleanup_stale_entities(ctx, runtime)
    assert removed == 0
    assert len(read_json_calls) == 0, (
        "cleanup_stale_entities should not read JSON when nothing is stale"
    )


# ---------------------------------------------------------------------------
# Tests: list_syncs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_syncs():
    svc, _ = _build_service()
    ctx1 = _make_sync_context("sync-aaa")
    ctx2 = _make_sync_context("sync-bbb")
    runtime = _make_runtime()
    await svc.upsert_manifest(ctx1, runtime)
    await svc.upsert_manifest(ctx2, runtime)

    syncs = await svc.list_syncs()
    assert "sync-aaa" in syncs
    assert "sync-bbb" in syncs


@pytest.mark.asyncio
async def test_list_syncs_empty():
    svc, _ = _build_service()
    syncs = await svc.list_syncs()
    assert syncs == []


# ---------------------------------------------------------------------------
# Tests: error-path / graceful degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_update_tolerates_corrupt_old_entity(tmp_path):
    """When reading the old entity during update fails, upsert still succeeds."""
    svc, storage = _build_service()
    ctx = _make_sync_context()

    test_file = tmp_path / "a.txt"
    test_file.write_bytes(b"data")
    entity = _make_file_entity("f-1", "V1", local_path=str(test_file))
    await svc.upsert_entity(entity, ctx)

    original_read_json = storage.read_json

    async def _fail_once(path):
        if "f-1" in path and not getattr(_fail_once, "called", False):
            _fail_once.called = True
            raise RuntimeError("disk error")
        return await original_read_json(path)

    storage.read_json = _fail_once

    entity2 = _make_file_entity("f-1", "V2", local_path=str(test_file))
    await svc.upsert_entity(entity2, ctx)

    entity_path = svc._entity_path(SYNC_ID, "f-1")
    storage.read_json = original_read_json
    stored = await storage.read_json(entity_path)
    assert stored["name"] == "V2"


@pytest.mark.asyncio
async def test_upsert_file_entity_tolerates_write_failure(tmp_path):
    """File storage failure is logged but entity JSON is still written."""
    svc, storage = _build_service()
    ctx = _make_sync_context()

    test_file = tmp_path / "doc.pdf"
    test_file.write_bytes(b"content")

    storage.write_file = AsyncMock(side_effect=RuntimeError("write failed"))

    entity = _make_file_entity("f-1", "Doc", local_path=str(test_file))
    await svc.upsert_entity(entity, ctx)

    entity_path = svc._entity_path(SYNC_ID, "f-1")
    stored = await storage.read_json(entity_path)
    assert "__stored_file__" not in stored


@pytest.mark.asyncio
async def test_delete_entity_tolerates_corrupt_entity_data():
    """Delete still removes entity JSON even if reading it for file cleanup fails."""
    svc, storage = _build_service()
    ctx = _make_sync_context()
    await svc.upsert_entity(_make_entity("e-1"), ctx)

    entity_path = svc._entity_path(SYNC_ID, "e-1")
    storage._json_store[entity_path] = "not-a-dict"

    original_read = storage.read_json

    async def _fail_read(path):
        if path == entity_path:
            raise RuntimeError("corrupt")
        return await original_read(path)

    storage.read_json = _fail_read
    deleted = await svc.delete_entity("e-1", ctx)
    assert deleted is True


@pytest.mark.asyncio
async def test_iter_entities_tolerates_list_failure():
    """iter_entities yields nothing when list_files raises."""
    svc, storage = _build_service()
    storage.list_files = AsyncMock(side_effect=RuntimeError("unavailable"))

    collected = []
    async for d in svc.iter_entities(SYNC_ID):
        collected.append(d)
    assert collected == []


@pytest.mark.asyncio
async def test_list_syncs_tolerates_storage_failure():
    """list_syncs returns [] when storage is unavailable."""
    svc, storage = _build_service()
    storage.list_dirs = AsyncMock(side_effect=RuntimeError("unavailable"))
    assert await svc.list_syncs() == []


@pytest.mark.asyncio
async def test_get_entity_count_tolerates_storage_failure():
    """get_entity_count returns 0 when storage raises."""
    svc, storage = _build_service()
    storage.count_files = AsyncMock(side_effect=RuntimeError("unavailable"))
    assert await svc.get_entity_count(SYNC_ID) == 0


@pytest.mark.asyncio
async def test_cleanup_stale_tolerates_list_files_failure():
    """cleanup_stale_entities returns 0 when list_files raises."""
    svc, storage = _build_service()
    storage.list_files = AsyncMock(side_effect=RuntimeError("unavailable"))

    ctx = _make_sync_context()
    runtime = _make_runtime()
    runtime.entity_tracker = SimpleNamespace(get_all_encountered_ids_flat=lambda: set())

    removed = await svc.cleanup_stale_entities(ctx, runtime)
    assert removed == 0
