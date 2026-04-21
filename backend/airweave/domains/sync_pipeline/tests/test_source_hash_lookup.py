"""Tests for SourceHashLookup — prefetch, cache hit, miss, empty."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_lookup(sync_id=None):
    return SourceHashLookup(
        sync_id=sync_id or uuid4(),
        logger=MagicMock(),
    )


def _mock_db_with_rows(rows):
    """Build an AsyncSession mock whose execute() returns the given rows."""
    result = MagicMock()
    result.__iter__ = lambda self: iter(rows)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


# ---------------------------------------------------------------------------
# Prefetch
# ---------------------------------------------------------------------------


class TestPrefetch:
    @pytest.mark.asyncio
    async def test_prefetch_populates_cache(self):
        lookup = _make_lookup()
        rows = [
            SimpleNamespace(entity_id="e-1", source_hash="sha256:aaa"),
            SimpleNamespace(entity_id="e-2", source_hash="sha1:bbb"),
        ]
        db = _mock_db_with_rows(rows)

        await lookup.prefetch(db)

        assert lookup._prefetched is True
        assert len(lookup._cache) == 2

    @pytest.mark.asyncio
    async def test_prefetch_empty_table(self):
        lookup = _make_lookup()
        db = _mock_db_with_rows([])

        await lookup.prefetch(db)

        assert lookup._prefetched is True
        assert len(lookup._cache) == 0

    @pytest.mark.asyncio
    async def test_prefetch_logs_warning_for_large_cache(self):
        logger = MagicMock()
        lookup = SourceHashLookup(sync_id=uuid4(), logger=logger)

        rows = [
            SimpleNamespace(entity_id=f"e-{i}", source_hash=f"sha256:{i}")
            for i in range(600_000)
        ]
        db = _mock_db_with_rows(rows)

        await lookup.prefetch(db)

        logger.warning.assert_called_once()
        assert "600000" in logger.warning.call_args[0][0]


# ---------------------------------------------------------------------------
# is_unchanged
# ---------------------------------------------------------------------------


class TestIsUnchanged:
    @pytest.mark.asyncio
    async def test_cache_hit_returns_true(self):
        lookup = _make_lookup()
        rows = [SimpleNamespace(entity_id="e-1", source_hash="sha256:aaa")]
        db = _mock_db_with_rows(rows)
        await lookup.prefetch(db)

        assert lookup.is_unchanged("e-1", "sha256:aaa") is True

    @pytest.mark.asyncio
    async def test_cache_miss_returns_false(self):
        lookup = _make_lookup()
        rows = [SimpleNamespace(entity_id="e-1", source_hash="sha256:aaa")]
        db = _mock_db_with_rows(rows)
        await lookup.prefetch(db)

        assert lookup.is_unchanged("e-999", "sha256:aaa") is False

    @pytest.mark.asyncio
    async def test_hash_mismatch_returns_false(self):
        lookup = _make_lookup()
        rows = [SimpleNamespace(entity_id="e-1", source_hash="sha256:aaa")]
        db = _mock_db_with_rows(rows)
        await lookup.prefetch(db)

        assert lookup.is_unchanged("e-1", "sha256:bbb") is False

    def test_not_prefetched_returns_false(self):
        lookup = _make_lookup()
        assert lookup.is_unchanged("e-1", "sha256:aaa") is False

    @pytest.mark.asyncio
    async def test_empty_source_hash_returns_false(self):
        lookup = _make_lookup()
        rows = [SimpleNamespace(entity_id="e-1", source_hash="sha256:aaa")]
        db = _mock_db_with_rows(rows)
        await lookup.prefetch(db)

        assert lookup.is_unchanged("e-1", "") is False

    @pytest.mark.asyncio
    async def test_empty_cache_returns_false(self):
        lookup = _make_lookup()
        db = _mock_db_with_rows([])
        await lookup.prefetch(db)

        assert lookup.is_unchanged("e-1", "sha256:aaa") is False
