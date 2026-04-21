"""Tests for SourceHashLookup — prefetch, is_unchanged, should_skip_download."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.domains.sync_pipeline.pipeline.entity_hasher import compute_entity_hash
from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup
from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import FileEntity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubFileEntity(FileEntity):
    stub_id: str = AirweaveField(..., is_entity_id=True)
    stub_name: str = AirweaveField(..., is_name=True)


def _make_lookup(sync_id=None):
    return SourceHashLookup(
        sync_id=sync_id or uuid4(),
        logger=MagicMock(),
    )


def _mock_db_with_rows(rows):
    result = MagicMock()
    result.__iter__ = lambda self: iter(rows)
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


def _db_row(entity_id, source_hash, content_hash="ch_abc", composite_hash="comp_abc"):
    return SimpleNamespace(
        entity_id=entity_id,
        source_hash=source_hash,
        content_hash=content_hash,
        hash=composite_hash,
    )


def _file_entity(entity_id="f-1", source_hash=None):
    e = _StubFileEntity(
        stub_id=entity_id,
        stub_name="test.txt",
        breadcrumbs=[],
        url="https://example.com/f",
        size=100,
        file_type="text",
        source_hash=source_hash,
    )
    return e


# ---------------------------------------------------------------------------
# Prefetch
# ---------------------------------------------------------------------------


class TestPrefetch:
    @pytest.mark.asyncio
    async def test_prefetch_populates_cache(self):
        lookup = _make_lookup()
        rows = [
            _db_row("e-1", "sha256:aaa"),
            _db_row("e-2", "sha1:bbb"),
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
            _db_row(f"e-{i}", f"sha256:{i}")
            for i in range(600_000)
        ]
        db = _mock_db_with_rows(rows)

        await lookup.prefetch(db)

        logger.warning.assert_called_once()
        assert "600000" in logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_prefetch_stores_all_hash_fields(self):
        lookup = _make_lookup()
        rows = [_db_row("e-1", "sha256:aaa", "content_abc", "composite_xyz")]
        db = _mock_db_with_rows(rows)
        await lookup.prefetch(db)

        stored = lookup._cache["e-1"]
        assert stored.source_hash == "sha256:aaa"
        assert stored.content_hash == "content_abc"
        assert stored.composite_hash == "composite_xyz"


# ---------------------------------------------------------------------------
# is_unchanged (pipeline content_hash reuse)
# ---------------------------------------------------------------------------


class TestIsUnchanged:
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        lookup = _make_lookup()
        db = _mock_db_with_rows([_db_row("e-1", "sha256:aaa")])
        await lookup.prefetch(db)
        assert lookup.is_unchanged("e-1", "sha256:aaa") is True

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        lookup = _make_lookup()
        db = _mock_db_with_rows([_db_row("e-1", "sha256:aaa")])
        await lookup.prefetch(db)
        assert lookup.is_unchanged("e-999", "sha256:aaa") is False

    @pytest.mark.asyncio
    async def test_hash_mismatch(self):
        lookup = _make_lookup()
        db = _mock_db_with_rows([_db_row("e-1", "sha256:aaa")])
        await lookup.prefetch(db)
        assert lookup.is_unchanged("e-1", "sha256:bbb") is False

    def test_not_prefetched(self):
        lookup = _make_lookup()
        assert lookup.is_unchanged("e-1", "sha256:aaa") is False


# ---------------------------------------------------------------------------
# should_skip_download (trial composite)
# ---------------------------------------------------------------------------


class TestShouldSkipDownload:
    @pytest.mark.asyncio
    async def test_skip_when_content_and_metadata_unchanged(self):
        """Both source_hash and trial composite match → skip."""
        entity = _file_entity("f-1", source_hash="sha256:aaa")
        content_hash = "stored_content_hash"

        # Compute the "stored" composite as the pipeline would
        composite = compute_entity_hash(entity, content_hash=content_hash)

        lookup = _make_lookup()
        db = _mock_db_with_rows([
            _db_row("f-1", "sha256:aaa", content_hash, composite),
        ])
        await lookup.prefetch(db)

        assert lookup.should_skip_download(entity) is True

    @pytest.mark.asyncio
    async def test_no_skip_when_metadata_changed(self):
        """source_hash matches but entity metadata differs → don't skip."""
        old_entity = _file_entity("f-1", source_hash="sha256:aaa")
        content_hash = "stored_content_hash"
        old_composite = compute_entity_hash(old_entity, content_hash=content_hash)

        # New entity has different metadata (name changed)
        new_entity = _StubFileEntity(
            stub_id="f-1",
            stub_name="renamed.txt",
            breadcrumbs=[],
            url="https://example.com/f",
            size=100,
            file_type="text",
            source_hash="sha256:aaa",
        )

        lookup = _make_lookup()
        db = _mock_db_with_rows([
            _db_row("f-1", "sha256:aaa", content_hash, old_composite),
        ])
        await lookup.prefetch(db)

        assert lookup.should_skip_download(new_entity) is False

    @pytest.mark.asyncio
    async def test_no_skip_when_content_changed(self):
        """source_hash differs → content changed → don't skip."""
        entity = _file_entity("f-1", source_hash="sha256:bbb")

        lookup = _make_lookup()
        db = _mock_db_with_rows([
            _db_row("f-1", "sha256:aaa", "ch", "comp"),
        ])
        await lookup.prefetch(db)

        assert lookup.should_skip_download(entity) is False

    @pytest.mark.asyncio
    async def test_no_skip_when_not_in_cache(self):
        """First sync — entity not in cache → don't skip."""
        entity = _file_entity("f-new", source_hash="sha256:aaa")

        lookup = _make_lookup()
        db = _mock_db_with_rows([])
        await lookup.prefetch(db)

        assert lookup.should_skip_download(entity) is False

    def test_no_skip_when_not_prefetched(self):
        lookup = _make_lookup()
        entity = _file_entity("f-1", source_hash="sha256:aaa")
        assert lookup.should_skip_download(entity) is False

    @pytest.mark.asyncio
    async def test_no_skip_when_no_stored_content_hash(self):
        """Stored entity has no content_hash → can't compute trial → don't skip."""
        entity = _file_entity("f-1", source_hash="sha256:aaa")

        lookup = _make_lookup()
        db = _mock_db_with_rows([
            _db_row("f-1", "sha256:aaa", content_hash=None, composite_hash="comp"),
        ])
        await lookup.prefetch(db)

        assert lookup.should_skip_download(entity) is False

    @pytest.mark.asyncio
    async def test_no_skip_when_no_source_hash_on_entity(self):
        entity = _file_entity("f-1", source_hash=None)

        lookup = _make_lookup()
        db = _mock_db_with_rows([_db_row("f-1", "sha256:aaa")])
        await lookup.prefetch(db)

        assert lookup.should_skip_download(entity) is False

    @pytest.mark.asyncio
    async def test_skip_works_with_unpopulated_entity_id(self):
        """Regression: entity_id is None at source time (derived fields
        not yet populated). should_skip_download must call
        populate_derived_fields internally so the lookup succeeds."""
        entity = _file_entity("f-1", source_hash="sha256:aaa")
        # Verify entity_id is truly unpopulated (as it would be at source time)
        assert entity.entity_id is None

        content_hash = "stored_content_hash"
        # Compute the expected composite via compute_entity_hash (which
        # populates derived fields as a side effect on a COPY-like path).
        # We need the composite for the DB row, so use a separate entity.
        ref_entity = _file_entity("f-1", source_hash="sha256:aaa")
        composite = compute_entity_hash(ref_entity, content_hash=content_hash)

        lookup = _make_lookup()
        db = _mock_db_with_rows([
            _db_row("f-1", "sha256:aaa", content_hash, composite),
        ])
        await lookup.prefetch(db)

        # The entity under test still has entity_id=None — should_skip_download
        # must populate it internally.
        assert lookup.should_skip_download(entity) is True
        # Confirm entity_id was populated as a side effect
        assert entity.entity_id == "f-1"
