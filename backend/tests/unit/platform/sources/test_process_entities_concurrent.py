"""Unit tests for BaseSource.process_entities_concurrent.

Validates the bounded-pool implementation: producer task + fixed worker pool
ensures asyncio task count stays O(batch_size), not O(N_items).
"""

import asyncio
from typing import Any, AsyncGenerator

import pytest

from airweave.platform.entities.stub import SmallStubEntity
from airweave.platform.sources._base import BaseSource


# ---------------------------------------------------------------------------
# Minimal concrete source for testing
# ---------------------------------------------------------------------------


class _TestSource(BaseSource):
    """Minimal BaseSource subclass to access process_entities_concurrent."""

    @classmethod
    async def create(cls, credentials=None, config=None):
        return cls()

    async def generate_entities(self):
        yield  # pragma: no cover

    async def validate(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity(value: int) -> SmallStubEntity:
    return SmallStubEntity(
        stub_id=f"test-{value}",
        title=f"Test Entity {value}",
        content=f"Content for item {value}",
        breadcrumbs=[],
    )


async def _collect(agen: AsyncGenerator) -> list:
    """Drain an async generator into a list."""
    out = []
    async for item in agen:
        out.append(item)
    return out


def _worker_single(item: Any) -> AsyncGenerator:
    """Worker that yields one entity per item."""

    async def _gen():
        yield _make_entity(item)

    return _gen()


def _worker_multi(item: Any) -> AsyncGenerator:
    """Worker that yields 3 entities per item."""

    async def _gen():
        for offset in range(3):
            yield _make_entity(item * 100 + offset)

    return _gen()


def _worker_failing(item: Any) -> AsyncGenerator:
    """Worker that raises on item == -1, otherwise yields normally."""

    async def _gen():
        if item == -1:
            raise ValueError("boom")
        yield _make_entity(item)

    return _gen()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_basic_unordered():
    """20 items, batch_size=5, all entities arrive (any order)."""
    src = _TestSource()
    items = list(range(20))
    results = await _collect(
        src.process_entities_concurrent(items, _worker_single, batch_size=5)
    )
    values = sorted(r.stub_id for r in results)
    expected = sorted(f"test-{i}" for i in range(20))
    assert values == expected


@pytest.mark.asyncio
async def test_basic_preserve_order():
    """20 items, batch_size=5, entities arrive in input order."""
    src = _TestSource()
    items = list(range(20))
    results = await _collect(
        src.process_entities_concurrent(
            items, _worker_single, batch_size=5, preserve_order=True
        )
    )
    ids = [r.stub_id for r in results]
    assert ids == [f"test-{i}" for i in range(20)]


@pytest.mark.asyncio
async def test_task_count_bounded():
    """500 items, batch_size=10 -- task count must stay bounded.

    This is the core regression test for the 33K-task explosion bug.
    """
    src = _TestSource()
    max_observed_tasks = 0

    async def _slow_worker(item):
        nonlocal max_observed_tasks
        current = len(asyncio.all_tasks())
        if current > max_observed_tasks:
            max_observed_tasks = current
        await asyncio.sleep(0.001)
        yield _make_entity(item)

    items = list(range(500))
    results = await _collect(
        src.process_entities_concurrent(items, _slow_worker, batch_size=10)
    )

    assert len(results) == 500
    # bounded pool = 10 workers + 1 producer + test task + small overhead
    # Must be WAY below 500 (the old implementation would create 500+ tasks)
    assert max_observed_tasks < 30, (
        f"Task count {max_observed_tasks} is too high -- bounded pool not working"
    )


@pytest.mark.asyncio
async def test_empty_items():
    """0 items, no crash, yields nothing."""
    src = _TestSource()
    results = await _collect(
        src.process_entities_concurrent([], _worker_single, batch_size=5)
    )
    assert results == []


@pytest.mark.asyncio
async def test_single_item():
    """1 item, batch_size=5, works correctly."""
    src = _TestSource()
    results = await _collect(
        src.process_entities_concurrent([42], _worker_single, batch_size=5)
    )
    assert len(results) == 1
    assert results[0].stub_id == "test-42"


@pytest.mark.asyncio
async def test_sync_iterable():
    """Pass a plain range as items."""
    src = _TestSource()
    results = await _collect(
        src.process_entities_concurrent(range(10), _worker_single, batch_size=3)
    )
    assert sorted(r.stub_id for r in results) == sorted(f"test-{i}" for i in range(10))


@pytest.mark.asyncio
async def test_async_iterable():
    """Pass an async generator as items."""
    src = _TestSource()

    async def _async_items():
        for i in range(10):
            yield i

    results = await _collect(
        src.process_entities_concurrent(_async_items(), _worker_single, batch_size=3)
    )
    assert sorted(r.stub_id for r in results) == sorted(f"test-{i}" for i in range(10))


@pytest.mark.asyncio
async def test_stop_on_error():
    """Worker raises, stop_on_error=True, propagates."""
    src = _TestSource()
    items = [1, 2, -1, 4, 5]
    with pytest.raises(ValueError, match="boom"):
        await _collect(
            src.process_entities_concurrent(
                items, _worker_failing, batch_size=2, stop_on_error=True
            )
        )


@pytest.mark.asyncio
async def test_error_continue():
    """Worker raises on one item, stop_on_error=False, other entities still arrive."""
    src = _TestSource()
    items = [1, 2, -1, 4, 5]
    results = await _collect(
        src.process_entities_concurrent(
            items, _worker_failing, batch_size=2, stop_on_error=False
        )
    )
    ids = sorted(r.stub_id for r in results)
    assert ids == sorted([f"test-{i}" for i in [1, 2, 4, 5]])


@pytest.mark.asyncio
async def test_worker_yields_multiple():
    """Single item, worker yields 3 entities, all arrive."""
    src = _TestSource()
    results = await _collect(
        src.process_entities_concurrent([7], _worker_multi, batch_size=2)
    )
    assert len(results) == 3
    ids = sorted(r.stub_id for r in results)
    assert ids == sorted([f"test-{v}" for v in [700, 701, 702]])


@pytest.mark.asyncio
async def test_producer_iterator_failure_still_drains():
    """If the items iterator raises mid-iteration, already-queued items still complete."""
    src = _TestSource()

    async def _exploding_items():
        for i in range(10):
            if i == 5:
                raise RuntimeError("iterator broke")
            yield i

    results = await _collect(
        src.process_entities_concurrent(
            _exploding_items(), _worker_single, batch_size=3, stop_on_error=False
        )
    )
    ids = sorted(r.stub_id for r in results)
    assert ids == sorted(f"test-{i}" for i in range(5))
