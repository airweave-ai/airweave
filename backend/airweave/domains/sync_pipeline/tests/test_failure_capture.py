"""Tests for sync failure artifact capture."""

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from airweave.domains.storage.fakes.backend import FakeStorageBackend
from airweave.domains.sync_pipeline.failure_capture import SyncFailureCapture


def _make_sync_context():
    ctx = MagicMock()
    ctx.sync = MagicMock(id=uuid4())
    ctx.sync_job = MagicMock(id=uuid4())
    ctx.collection = MagicMock(id=uuid4())
    ctx.source_connection_id = uuid4()
    ctx.source_short_name = "teams"
    ctx.organization_id = uuid4()
    return ctx


def _make_entity():
    entity = MagicMock()
    entity.entity_id = "message/with:unsafe"
    entity.textual_representation = "hello\x1bworld"
    entity.airweave_system_metadata = MagicMock()
    entity.airweave_system_metadata.original_entity_id = "message-1"
    entity.airweave_system_metadata.chunk_index = 3
    entity.model_dump.return_value = {
        "entity_id": "message/with:unsafe",
        "access_token": "should-not-leak",
        "nested": {"client_secret": "also-redacted", "safe": "kept"},
    }
    return entity


@pytest.mark.asyncio
async def test_capture_entity_failure_redacts_and_cleans_snapshot():
    """Entity artifacts redact credentials and replace control characters."""
    storage = FakeStorageBackend()
    capture = SyncFailureCapture(storage=storage)
    ctx = _make_sync_context()
    entity = _make_entity()

    path = await capture.capture_entity_failure(
        entity=entity,
        stage="dense_embedding",
        error=ValueError("bad token\x1b"),
        sync_context=ctx,
    )

    artifact = await storage.read_json(path)
    assert artifact["stage"] == "dense_embedding"
    assert artifact["error"]["message"] == "bad token\\uFFFD"
    assert artifact["entity"]["textual_representation"]["preview"] == "hello\\uFFFDworld"
    assert artifact["entity"]["fields"]["access_token"] == "[REDACTED]"
    assert artifact["entity"]["fields"]["nested"]["client_secret"] == "[REDACTED]"
    assert artifact["entity"]["fields"]["nested"]["safe"] == "kept"


@pytest.mark.asyncio
async def test_capture_entity_failure_redacts_inline_secret_error_messages():
    """Error strings are redacted too, not only structured entity fields."""
    storage = FakeStorageBackend()
    capture = SyncFailureCapture(storage=storage)
    ctx = _make_sync_context()

    path = await capture.capture_entity_failure(
        entity=_make_entity(),
        stage="dense_embedding",
        error=ValueError("request failed access_token=abc123 Authorization: Bearer sk-live"),
        sync_context=ctx,
    )

    artifact = await storage.read_json(path)
    assert artifact["error"]["message"] == (
        "request failed access_token=[REDACTED] Authorization=[REDACTED]"
    )


@pytest.mark.asyncio
async def test_capture_batch_failure_lists_entity_refs():
    """Batch artifacts include bounded entity refs and destination metadata."""
    storage = FakeStorageBackend()
    capture = SyncFailureCapture(storage=storage)
    ctx = _make_sync_context()
    entities = [_make_entity(), _make_entity()]

    path = await capture.capture_batch_failure(
        entities=entities,
        stage="insert_VespaDestination",
        error=RuntimeError("vespa rejected payload"),
        sync_context=ctx,
        extra={"destination": "VespaDestination"},
    )

    artifact = await storage.read_json(path)
    assert artifact["batch"]["entity_count"] == 2
    assert artifact["batch"]["entities"][0]["entity_id"] == "message/with:unsafe"
    assert artifact["extra"]["destination"] == "VespaDestination"
