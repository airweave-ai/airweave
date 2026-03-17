"""Tests for ArfHandler — manifest lifecycle and upsert paths."""

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.domains.sync_pipeline.entity.actions import (
    EntityActionBatch,
    EntityInsertAction,
)
from airweave.domains.sync_pipeline.entity.handlers.arf import ArfHandler


@dataclass
class FakeSyncContext:
    sync: Any = field(default_factory=lambda: SimpleNamespace(id=uuid4()))
    sync_job: Any = field(default_factory=lambda: SimpleNamespace(id=uuid4()))
    organization_id: Any = field(default_factory=uuid4)
    source_connection_id: Any = field(default_factory=uuid4)
    logger: Any = field(default_factory=lambda: MagicMock())


@dataclass
class FakeRuntime:
    pass


def _make_insert():
    entity = MagicMock()
    entity.entity_id = str(uuid4())
    return EntityInsertAction(entity=entity, entity_definition_short_name="stub")


def _make_handler(arf_service=None, vector_size=768, embedding_model_name="test-embed"):
    if arf_service is None:
        arf_service = MagicMock()
        arf_service.upsert_manifest = AsyncMock()
        arf_service.write_entities = AsyncMock()
    return ArfHandler(
        arf_service=arf_service,
        vector_size=vector_size,
        embedding_model_name=embedding_model_name,
    )


class TestEnsureManifestSuccess:
    @pytest.mark.asyncio
    async def test_upsert_manifest_called_on_first_insert(self):
        """_ensure_manifest calls upsert_manifest when not yet initialized."""
        arf_service = MagicMock()
        arf_service.upsert_manifest = AsyncMock()
        arf_service.write_entities = AsyncMock()
        handler = _make_handler(arf_service=arf_service)
        ctx = FakeSyncContext()
        runtime = FakeRuntime()

        await handler._ensure_manifest(ctx, runtime)

        arf_service.upsert_manifest.assert_awaited_once_with(
            ctx,
            runtime,
            vector_size=768,
            embedding_model_name="test-embed",
        )
        assert handler._manifest_initialized is True

    @pytest.mark.asyncio
    async def test_upsert_manifest_not_called_twice(self):
        """_ensure_manifest is idempotent: second call skips upsert."""
        arf_service = MagicMock()
        arf_service.upsert_manifest = AsyncMock()
        arf_service.write_entities = AsyncMock()
        handler = _make_handler(arf_service=arf_service)
        ctx = FakeSyncContext()
        runtime = FakeRuntime()

        await handler._ensure_manifest(ctx, runtime)
        await handler._ensure_manifest(ctx, runtime)

        assert arf_service.upsert_manifest.await_count == 1


class TestEnsureManifestException:
    @pytest.mark.asyncio
    async def test_upsert_manifest_exception_is_logged_not_raised(self):
        """Exception during upsert_manifest is swallowed and logged as warning."""
        arf_service = MagicMock()
        arf_service.upsert_manifest = AsyncMock(side_effect=RuntimeError("storage down"))
        handler = _make_handler(arf_service=arf_service)
        ctx = FakeSyncContext()
        runtime = FakeRuntime()

        await handler._ensure_manifest(ctx, runtime)

        ctx.logger.warning.assert_called_once()
        assert "storage down" in ctx.logger.warning.call_args[0][0]
        assert handler._manifest_initialized is False
