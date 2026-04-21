"""Tests for entity_hasher — stateless hash primitives."""

import hashlib
import json
import os
import tempfile

import pytest

from airweave.domains.sync_pipeline.pipeline.entity_hasher import (
    compute_dict_hash,
    compute_entity_hash,
    exclude_volatile_fields,
    populate_derived_fields,
    stable_serialize,
)
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
    return _StubEntity(stub_id=entity_id, stub_name="test", breadcrumbs=[])


def _file_entity(entity_id="f-1", content=b"hello world"):
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
    return e, tmp.name


# ---------------------------------------------------------------------------
# populate_derived_fields
# ---------------------------------------------------------------------------


class TestPopulateDerivedFields:
    def test_copies_flagged_entity_id(self):
        e = _entity("abc")
        assert e.entity_id is None
        populate_derived_fields(e)
        assert e.entity_id == "abc"

    def test_copies_flagged_name(self):
        e = _entity()
        assert e.name is None
        populate_derived_fields(e)
        assert e.name == "test"

    def test_idempotent(self):
        e = _entity()
        e.entity_id = "already-set"
        populate_derived_fields(e)
        assert e.entity_id == "already-set"


# ---------------------------------------------------------------------------
# compute_entity_hash matches HashComputer
# ---------------------------------------------------------------------------


class TestComputeEntityHash:
    @pytest.mark.asyncio
    async def test_matches_hash_computer_for_base_entity(self):
        e = _entity("e-1")
        populate_derived_fields(e)
        e.airweave_system_metadata = AirweaveSystemMetadata()

        hc_hash = await HashComputer().compute_for_entity(e)
        eh_hash = compute_entity_hash(e)

        assert hc_hash == eh_hash

    @pytest.mark.asyncio
    async def test_matches_hash_computer_for_file_entity(self):
        content = b"deterministic"
        e, path = _file_entity("f-1", content=content)
        populate_derived_fields(e)
        e.airweave_system_metadata = AirweaveSystemMetadata()

        try:
            hc_hash = await HashComputer().compute_for_entity(e)
            content_hash = e.airweave_system_metadata._computed_content_hash

            # Reset for clean comparison
            e2, path2 = _file_entity("f-1", content=content)
            eh_hash = compute_entity_hash(e2, content_hash=content_hash)

            assert hc_hash == eh_hash
        finally:
            os.unlink(path)
            if os.path.exists(path2):
                os.unlink(path2)

    def test_different_metadata_produces_different_hash(self):
        e1 = _entity("e-1")
        e2 = _entity("e-2")
        assert compute_entity_hash(e1) != compute_entity_hash(e2)

    def test_source_hash_excluded(self):
        content = b"same"
        e1, p1 = _file_entity("f-1", content=content)
        e2, p2 = _file_entity("f-1", content=content)
        e1.source_hash = None
        e2.source_hash = "sha256:different"

        try:
            ch = hashlib.sha256(content).hexdigest()
            h1 = compute_entity_hash(e1, content_hash=ch)
            h2 = compute_entity_hash(e2, content_hash=ch)
            assert h1 == h2
        finally:
            os.unlink(p1)
            os.unlink(p2)


# ---------------------------------------------------------------------------
# stable_serialize / compute_dict_hash
# ---------------------------------------------------------------------------


class TestStableSerialize:
    def test_sorts_dict_keys(self):
        assert stable_serialize({"b": 1, "a": 2}) == {"a": 2, "b": 1}

    def test_handles_nested(self):
        result = stable_serialize({"a": [{"z": 1, "a": 2}]})
        assert result == {"a": [{"a": 2, "z": 1}]}

    def test_converts_unknown_types(self):
        from uuid import uuid4

        uid = uuid4()
        assert stable_serialize(uid) == str(uid)


class TestComputeDictHash:
    def test_deterministic(self):
        d = {"a": 1, "b": [2, 3]}
        assert compute_dict_hash(d) == compute_dict_hash(d)

    def test_order_independent(self):
        assert compute_dict_hash({"a": 1, "b": 2}) == compute_dict_hash({"b": 2, "a": 1})
