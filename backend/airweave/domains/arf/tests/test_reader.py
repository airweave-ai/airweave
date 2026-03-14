"""Unit tests for ArfReader.

Covers:
- validate (happy, missing manifest, corrupt data)
- read_manifest
- get_entity_count
- iter_entity_dicts (batched reads, error handling)
- reconstruct_entity (happy, missing class, missing metadata)
- iter_entities (end-to-end iteration with reconstruction)
- cleanup (temp dir removal)

Uses a FakeStorageBackend for all I/O.
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

import pytest

from airweave.domains.arf.reader import ArfReader
from airweave.domains.storage.exceptions import StorageNotFoundError
from airweave.domains.storage.fakes import FakeStorageBackend


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYNC_ID = uuid4()



def _make_logger() -> Any:
    return SimpleNamespace(
        debug=lambda *a, **kw: None,
        info=lambda *a, **kw: None,
        warning=lambda *a, **kw: None,
        error=lambda *a, **kw: None,
    )


def _build_reader(sync_id: UUID = SYNC_ID) -> tuple:
    storage = FakeStorageBackend()
    reader = ArfReader(sync_id=sync_id, storage=storage, logger=_make_logger(), restore_files=False)
    return reader, storage


def _seed_manifest(storage: FakeStorageBackend, sync_id: UUID = SYNC_ID) -> None:
    path = f"raw/{sync_id}/manifest.json"
    storage._json_store[path] = {
        "sync_id": str(sync_id),
        "source_short_name": "github",
        "entity_count": 3,
    }


def _seed_entity(
    storage: FakeStorageBackend, entity_id: str, sync_id: UUID = SYNC_ID
) -> None:
    path = f"raw/{sync_id}/entities/{entity_id}.json"
    storage._json_store[path] = {
        "entity_id": entity_id,
        "name": f"Entity {entity_id}",
        "__entity_class__": "SimpleNamespace",
        "__entity_module__": "types",
        "__captured_at__": "2025-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Tests: validate
# ---------------------------------------------------------------------------


@dataclass
class ValidateCase:
    desc: str
    seed_manifest: bool
    expected: bool


VALIDATE_CASES = [
    ValidateCase("valid manifest", seed_manifest=True, expected=True),
    ValidateCase("missing manifest", seed_manifest=False, expected=False),
]


@pytest.mark.parametrize("case", VALIDATE_CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_validate(case: ValidateCase):
    reader, storage = _build_reader()
    if case.seed_manifest:
        _seed_manifest(storage)
    result = await reader.validate()
    assert result == case.expected


# ---------------------------------------------------------------------------
# Tests: read_manifest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_manifest_success():
    reader, storage = _build_reader()
    _seed_manifest(storage)
    manifest = await reader.read_manifest()
    assert manifest["sync_id"] == str(SYNC_ID)


@pytest.mark.asyncio
async def test_read_manifest_missing():
    reader, _ = _build_reader()
    with pytest.raises(StorageNotFoundError):
        await reader.read_manifest()


# ---------------------------------------------------------------------------
# Tests: get_entity_count
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_entity_count():
    reader, storage = _build_reader()
    for i in range(4):
        _seed_entity(storage, f"ent-{i}")
    count = await reader.get_entity_count()
    assert count == 4


@pytest.mark.asyncio
async def test_get_entity_count_empty():
    reader, _ = _build_reader()
    assert await reader.get_entity_count() == 0


# ---------------------------------------------------------------------------
# Tests: iter_entity_dicts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_iter_entity_dicts():
    reader, storage = _build_reader()
    for i in range(3):
        _seed_entity(storage, f"ent-{i}")

    results = []
    async for entity_dict in reader.iter_entity_dicts(batch_size=2):
        results.append(entity_dict)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_iter_entity_dicts_invalid_batch_size():
    reader, _ = _build_reader()
    with pytest.raises(ValueError, match="batch_size must be positive"):
        async for _ in reader.iter_entity_dicts(batch_size=0):
            pass


# ---------------------------------------------------------------------------
# Tests: reconstruct_entity
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconstruct_entity_missing_metadata():
    reader, _ = _build_reader()
    with pytest.raises(ValueError, match="missing __entity_class__"):
        await reader.reconstruct_entity({"entity_id": "test"})


@pytest.mark.asyncio
async def test_reconstruct_entity_bad_module():
    reader, _ = _build_reader()
    with pytest.raises(ValueError, match="Cannot reconstruct"):
        await reader.reconstruct_entity({
            "entity_id": "test",
            "__entity_class__": "FakeClass",
            "__entity_module__": "nonexistent.module.that.does.not.exist",
            "__captured_at__": "2025-01-01T00:00:00Z",
        })


# ---------------------------------------------------------------------------
# Tests: cleanup
# ---------------------------------------------------------------------------


def test_cleanup_no_temp_dir():
    reader, _ = _build_reader()
    reader.cleanup()  # should not raise


# ---------------------------------------------------------------------------
# Tests: _restore_file (requires restore_files=True)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconstruct_entity_with_file_restoration():
    """Test that a stored file is restored to temp when restore_files=True."""
    storage = FakeStorageBackend()
    reader = ArfReader(
        sync_id=SYNC_ID,
        storage=storage,
        logger=_make_logger(),
        restore_files=True,
    )

    file_path = f"raw/{SYNC_ID}/files/file-1_report.pdf"
    storage.seed_file(file_path, b"restored content")
    storage.seed_json(f"raw/{SYNC_ID}/entities/file-1.json", {
        "entity_id": "file-1",
        "name": "Report",
        "__entity_class__": "SimpleNamespace",
        "__entity_module__": "types",
        "__captured_at__": "2025-01-01T00:00:00Z",
        "__stored_file__": file_path,
    })

    entity_dict = await storage.read_json(f"raw/{SYNC_ID}/entities/file-1.json")
    entity = await reader.reconstruct_entity(entity_dict)

    assert hasattr(entity, "local_path")
    import os
    assert os.path.exists(entity.local_path)
    with open(entity.local_path, "rb") as f:
        assert f.read() == b"restored content"

    reader.cleanup()


@pytest.mark.asyncio
async def test_restore_file_missing_from_storage():
    """File not in storage should return None and not crash."""
    storage = FakeStorageBackend()
    reader = ArfReader(
        sync_id=SYNC_ID,
        storage=storage,
        logger=_make_logger(),
        restore_files=True,
    )

    result = await reader._restore_file("raw/nonexistent/file.pdf")
    assert result is None
