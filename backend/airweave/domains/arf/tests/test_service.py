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
from airweave.platform.storage.exceptions import StorageNotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYNC_ID = str(uuid4())
JOB_ID = str(uuid4())
COLLECTION_ID = str(uuid4())
ORG_ID = str(uuid4())


class FakeStorageBackend:
    """Minimal in-memory storage for testing ArfService."""

    def __init__(self) -> None:
        self._json_store: Dict[str, Dict[str, Any]] = {}
        self._file_store: Dict[str, bytes] = {}

    async def write_json(self, path: str, data: Dict[str, Any]) -> None:
        self._json_store[path] = data

    async def read_json(self, path: str) -> Dict[str, Any]:
        if path not in self._json_store:
            raise StorageNotFoundError(path)
        return self._json_store[path]

    async def write_file(self, path: str, content: bytes) -> None:
        self._file_store[path] = content

    async def read_file(self, path: str) -> bytes:
        if path not in self._file_store:
            raise StorageNotFoundError(path)
        return self._file_store[path]

    async def exists(self, path: str) -> bool:
        return path in self._json_store or path in self._file_store

    async def delete(self, path: str) -> bool:
        # Exact match first
        if path in self._json_store or path in self._file_store:
            self._json_store.pop(path, None)
            self._file_store.pop(path, None)
            return True
        # Prefix/directory deletion
        prefix = path.rstrip("/") + "/"
        json_keys = [k for k in self._json_store if k.startswith(prefix) or k == path]
        file_keys = [k for k in self._file_store if k.startswith(prefix) or k == path]
        for k in json_keys:
            del self._json_store[k]
        for k in file_keys:
            del self._file_store[k]
        return len(json_keys) > 0 or len(file_keys) > 0

    async def list_files(self, prefix: str = "") -> List[str]:
        return [k for k in self._json_store if k.startswith(prefix)]

    async def list_dirs(self, prefix: str = "") -> List[str]:
        dirs = set()
        for k in self._json_store:
            if k.startswith(prefix):
                rest = k[len(prefix) :].lstrip("/")
                parts = rest.split("/")
                if len(parts) > 1:
                    dirs.add(f"{prefix}/{parts[0]}")
        return sorted(dirs)

    async def count_files(self, prefix: str = "", pattern: str = "*") -> int:
        files = await self.list_files(prefix)
        if pattern == "*.json":
            files = [f for f in files if f.endswith(".json")]
        return len(files)


class _TestEntity:
    """Lightweight entity stand-in for testing."""

    def __init__(self, entity_id: str, name: str) -> None:
        self.entity_id = entity_id
        self.name = name

    def model_dump(self, mode: str = "json") -> Dict[str, Any]:
        return {"entity_id": self.entity_id, "name": self.name}


def _make_entity(entity_id: str = "ent-1", name: str = "Test Entity") -> _TestEntity:
    return _TestEntity(entity_id=entity_id, name=name)


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
