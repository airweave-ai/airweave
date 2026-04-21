"""Tests for HashComputer — source_hash exclusion and content_hash reuse."""

import hashlib
import json
import os
import tempfile

import pytest

from airweave.domains.sync_pipeline.pipeline.hash_computer import HashComputer
from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import (
    AirweaveSystemMetadata,
    BaseEntity,
    FileEntity,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _StubEntity(BaseEntity):
    stub_id: str = AirweaveField(..., is_entity_id=True)
    stub_name: str = AirweaveField(..., is_name=True)


class _StubFileEntity(FileEntity):
    stub_id: str = AirweaveField(..., is_entity_id=True)
    stub_name: str = AirweaveField(..., is_name=True)


def _entity(entity_id="e-1"):
    e = _StubEntity(stub_id=entity_id, stub_name="test", breadcrumbs=[])
    e.entity_id = entity_id
    e.airweave_system_metadata = AirweaveSystemMetadata()
    return e


def _file_entity(entity_id="f-1", content=b"hello world", source_hash=None):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt")
    tmp.write(content)
    tmp.close()
    e = _StubFileEntity(
        stub_id=entity_id,
        stub_name="test.txt",
        breadcrumbs=[],
        url="https://example.com/test.txt",
        size=len(content),
        file_type="text",
        local_path=tmp.name,
    )
    e.entity_id = entity_id
    e.source_hash = source_hash
    e.airweave_system_metadata = AirweaveSystemMetadata()
    return e, tmp.name


# ---------------------------------------------------------------------------
# source_hash excluded from composite hash (unhashable flag)
# ---------------------------------------------------------------------------


class TestSourceHashExcluded:
    @pytest.mark.asyncio
    async def test_source_hash_does_not_affect_composite_hash(self):
        """Two file entities identical except for source_hash produce the same hash."""
        hc = HashComputer()

        content = b"same content"
        e1, p1 = _file_entity("f-1", content=content, source_hash=None)
        e2, p2 = _file_entity("f-1", content=content, source_hash="sha256:abc123")

        try:
            h1 = await hc.compute_for_entity(e1)
            h2 = await hc.compute_for_entity(e2)
            assert h1 == h2
        finally:
            os.unlink(p1)
            os.unlink(p2)

    @pytest.mark.asyncio
    async def test_different_data_produces_different_hash(self):
        """Sanity check: different entity data produces different hashes."""
        hc = HashComputer()

        e1 = _entity("e-1")
        e2 = _entity("e-2")

        h1 = await hc.compute_for_entity(e1)
        h2 = await hc.compute_for_entity(e2)

        assert h1 != h2


# ---------------------------------------------------------------------------
# content_hash reuse
# ---------------------------------------------------------------------------


class TestContentHashReuse:
    @pytest.mark.asyncio
    async def test_reuse_produces_same_hash_as_fresh(self):
        """Passing stored_content_hash produces the same composite hash as
        computing from the file."""
        hc = HashComputer()

        content = b"deterministic content for hashing"
        e_fresh, path = _file_entity("f-1", content=content)

        try:
            # Compute fresh (reads the file)
            fresh_hash = await hc.compute_for_entity(e_fresh)
            computed_content_hash = e_fresh.airweave_system_metadata._computed_content_hash

            # Compute with reuse (skips file read)
            e_reuse, path2 = _file_entity("f-1", content=content)
            # Remove local_path to prove it doesn't read the file
            e_reuse.local_path = None
            reuse_hash = await hc.compute_for_entity(
                e_reuse, stored_content_hash=computed_content_hash
            )

            assert fresh_hash == reuse_hash
        finally:
            os.unlink(path)
            if os.path.exists(path2):
                os.unlink(path2)

    @pytest.mark.asyncio
    async def test_reuse_stores_content_hash_on_metadata(self):
        """When stored_content_hash is provided, it's stored on
        airweave_system_metadata._computed_content_hash."""
        hc = HashComputer()

        e, path = _file_entity("f-1")
        try:
            stored = "abc123deadbeef"
            await hc.compute_for_entity(e, stored_content_hash=stored)

            assert e.airweave_system_metadata._computed_content_hash == stored
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_fresh_computation_stores_content_hash(self):
        """Fresh file hash computation stores _computed_content_hash."""
        hc = HashComputer()

        content = b"test content"
        e, path = _file_entity("f-1", content=content)

        try:
            await hc.compute_for_entity(e)

            expected = hashlib.sha256(content).hexdigest()
            assert e.airweave_system_metadata._computed_content_hash == expected
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_file_entity_without_local_path_and_no_stored_hash_raises(self):
        """FileEntity with no local_path and no stored_content_hash raises."""
        from airweave.domains.sync_pipeline.exceptions import EntityProcessingError

        hc = HashComputer()
        e, path = _file_entity("f-1")
        os.unlink(path)
        e.local_path = None

        with pytest.raises(EntityProcessingError, match="missing local_path"):
            await hc.compute_for_entity(e)


# ---------------------------------------------------------------------------
# Batch with stored_data
# ---------------------------------------------------------------------------


class TestBatchStoredData:
    @pytest.mark.asyncio
    async def test_batch_uses_stored_data(self):
        """compute_for_batch passes stored_data through to individual entities."""
        hc = HashComputer()

        content = b"batch test content"
        e, path = _file_entity("f-1", content=content, source_hash="sha256:aaa")

        try:
            # First compute to get the content_hash
            await hc.compute_for_entity(e)
            content_hash = e.airweave_system_metadata._computed_content_hash

            # Now test batch with stored_data
            e2, path2 = _file_entity("f-1", content=content, source_hash="sha256:aaa")
            e2.local_path = None  # prove it doesn't read the file

            from unittest.mock import MagicMock

            sync_ctx = MagicMock()
            sync_ctx.logger = MagicMock()
            runtime = MagicMock()
            runtime.entity_tracker = MagicMock()
            runtime.entity_tracker.record_skipped = MagicMock(
                side_effect=lambda *a, **kw: None
            )

            stored_data = {"f-1": content_hash}
            await hc.compute_for_batch(
                [e2], sync_ctx, runtime, stored_data=stored_data
            )

            assert e2.airweave_system_metadata.hash is not None
            assert e2.airweave_system_metadata._computed_content_hash == content_hash
        finally:
            os.unlink(path)
            if os.path.exists(path2):
                os.unlink(path2)
