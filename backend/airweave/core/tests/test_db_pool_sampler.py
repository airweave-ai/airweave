"""Unit tests for the DB pool sampler."""

import asyncio

import pytest

from airweave.adapters.metrics import FakeDbPoolMetrics
from airweave.core.db_pool_sampler import DbPoolSampler

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakePool:
    """Minimal stand-in for a SQLAlchemy pool."""

    def __init__(
        self,
        size: int = 20,
        checkedout: int = 5,
        checkedin: int = 15,
        overflow: int = 0,
    ) -> None:
        self._size = size
        self._checkedout = checkedout
        self._checkedin = checkedin
        self._overflow = overflow

    def size(self) -> int:
        return self._size

    def checkedout(self) -> int:
        return self._checkedout

    def checkedin(self) -> int:
        return self._checkedin

    def overflow(self) -> int:
        return self._overflow


class BrokenPool:
    """Pool that raises on every read."""

    def size(self) -> int:
        raise RuntimeError("pool gone")

    def checkedout(self) -> int:
        raise RuntimeError("pool gone")

    def checkedin(self) -> int:
        raise RuntimeError("pool gone")

    def overflow(self) -> int:
        raise RuntimeError("pool gone")


# ---------------------------------------------------------------------------
# DbPoolSampler
# ---------------------------------------------------------------------------


class TestDbPoolSampler:
    """Tests for the background pool sampler."""

    @pytest.mark.asyncio
    async def test_samples_pool_after_one_tick(self):
        """After one sampling tick the fake metrics should reflect pool state."""
        pool = FakePool(size=20, checkedout=3, checkedin=17, overflow=1)
        fake = FakeDbPoolMetrics()
        sampler = DbPoolSampler(pool, fake, interval=0.01)

        await sampler.start()
        # Give the loop enough time for at least one tick.
        await asyncio.sleep(0.05)
        await sampler.stop()

        assert fake.pool_size == 20
        assert fake.checked_out == 3
        assert fake.checked_in == 17
        assert fake.overflow == 1
        assert fake.update_count >= 1

    @pytest.mark.asyncio
    async def test_stop_cancels_cleanly(self):
        """stop() should cancel the task without raising."""
        pool = FakePool()
        fake = FakeDbPoolMetrics()
        sampler = DbPoolSampler(pool, fake, interval=0.01)

        await sampler.start()
        await sampler.stop()

        assert sampler._task is None

    @pytest.mark.asyncio
    async def test_stop_is_safe_when_not_started(self):
        """stop() before start() should not raise."""
        pool = FakePool()
        fake = FakeDbPoolMetrics()
        sampler = DbPoolSampler(pool, fake)

        await sampler.stop()  # no-op

    @pytest.mark.asyncio
    async def test_pool_error_does_not_crash_loop(self):
        """A transient pool error should be swallowed; the loop continues."""
        broken = BrokenPool()
        fake = FakeDbPoolMetrics()
        sampler = DbPoolSampler(broken, fake, interval=0.01)

        await sampler.start()
        await asyncio.sleep(0.05)
        await sampler.stop()

        # Metrics were never successfully updated.
        assert fake.update_count == 0
