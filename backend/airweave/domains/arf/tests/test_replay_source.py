"""Unit tests for ArfReplaySource.

Covers:
- generate_entities (yields from reader)
- validate (delegates to reader)
- cleanup (delegates to reader)
- original_short_name masquerading

Uses FakeArfReader to avoid real I/O.
"""

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from uuid import uuid4

import pytest

from airweave.domains.arf.fakes.reader import FakeArfReader
from airweave.domains.arf.reader import ArfReader
from airweave.domains.arf.replay_source import ArfReplaySource
from airweave.platform.storage.exceptions import StorageNotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SYNC_ID = uuid4()


class FakeStorageBackend:
    """Minimal storage for ArfReplaySource construction."""

    async def write_json(self, path: str, data: dict) -> None:
        pass

    async def read_json(self, path: str) -> dict:
        raise StorageNotFoundError(path)

    async def write_file(self, path: str, content: bytes) -> None:
        pass

    async def read_file(self, path: str) -> bytes:
        raise StorageNotFoundError(path)

    async def exists(self, path: str) -> bool:
        return False

    async def delete(self, path: str) -> bool:
        return False

    async def list_files(self, prefix: str = "") -> list:
        return []

    async def list_dirs(self, prefix: str = "") -> list:
        return []

    async def count_files(self, prefix: str = "", pattern: str = "*") -> int:
        return 0


def _make_entity(entity_id: str) -> Any:
    return SimpleNamespace(entity_id=entity_id, name=f"Entity {entity_id}")


# ---------------------------------------------------------------------------
# Tests: construction / masquerading
# ---------------------------------------------------------------------------


@dataclass
class MasqueradeCase:
    desc: str
    original_short_name: Optional[str]
    expected_short_name: str


MASQUERADE_CASES = [
    MasqueradeCase("no original", None, "arf_replay"),
    MasqueradeCase("with original", "github", "github"),
    MasqueradeCase("with different", "notion", "notion"),
]


@pytest.mark.parametrize("case", MASQUERADE_CASES, ids=lambda c: c.desc)
def test_masquerade_short_name(case: MasqueradeCase):
    source = ArfReplaySource(
        sync_id=SYNC_ID,
        storage=FakeStorageBackend(),
        original_short_name=case.original_short_name,
    )
    assert source.short_name == case.expected_short_name


# ---------------------------------------------------------------------------
# Tests: generate_entities
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_entities_yields_from_reader():
    source = ArfReplaySource(
        sync_id=SYNC_ID,
        storage=FakeStorageBackend(),
    )
    fake_reader = FakeArfReader()
    entities = [_make_entity(f"ent-{i}") for i in range(3)]
    fake_reader.seed_entities(entities)
    source._reader = fake_reader

    results = []
    async for entity in source.generate_entities():
        results.append(entity)

    assert len(results) == 3
    assert results[0].entity_id == "ent-0"


@pytest.mark.asyncio
async def test_generate_entities_empty():
    source = ArfReplaySource(
        sync_id=SYNC_ID,
        storage=FakeStorageBackend(),
    )
    fake_reader = FakeArfReader()
    fake_reader.seed_entities([])
    source._reader = fake_reader

    results = []
    async for entity in source.generate_entities():
        results.append(entity)
    assert len(results) == 0


# ---------------------------------------------------------------------------
# Tests: validate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_delegates():
    source = ArfReplaySource(sync_id=SYNC_ID, storage=FakeStorageBackend())
    fake_reader = FakeArfReader()
    fake_reader.set_valid(True)
    source._reader = fake_reader
    assert await source.validate() is True

    fake_reader.set_valid(False)
    assert await source.validate() is False


# ---------------------------------------------------------------------------
# Tests: cleanup
# ---------------------------------------------------------------------------


def test_cleanup_delegates():
    source = ArfReplaySource(sync_id=SYNC_ID, storage=FakeStorageBackend())
    fake_reader = FakeArfReader()
    source._reader = fake_reader
    source.cleanup()
    assert ("cleanup",) in fake_reader._calls


def test_cleanup_no_reader():
    source = ArfReplaySource(sync_id=SYNC_ID, storage=FakeStorageBackend())
    source.cleanup()  # should not raise


# ---------------------------------------------------------------------------
# Tests: create factory method
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_factory():
    source = await ArfReplaySource.create(
        sync_id=SYNC_ID,
        storage=FakeStorageBackend(),
        original_short_name="confluence",
    )
    assert source.short_name == "confluence"
    assert source.sync_id == SYNC_ID
