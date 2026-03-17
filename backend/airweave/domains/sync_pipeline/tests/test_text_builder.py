"""Tests for TextualRepresentationBuilder — error handling in _convert_sub_batch."""

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.domains.sync_pipeline.exceptions import EntityProcessingError, SyncFailureError
from airweave.domains.sync_pipeline.pipeline.text_builder import (
    TextualRepresentationBuilder,
)


@dataclass
class FakeSyncContext:
    source_short_name: str = "test_source"
    logger: Any = field(default_factory=lambda: MagicMock())


@dataclass
class FakeRuntime:
    entity_tracker: Any = field(default_factory=lambda: AsyncMock())


def _make_entity(entity_id="e1"):
    return SimpleNamespace(
        entity_id=entity_id,
        textual_representation="# Metadata\n\n**Source**: test",
    )


class FakeConverter:
    BATCH_SIZE = 10

    def __init__(self, side_effect=None, results=None):
        self._side_effect = side_effect
        self._results = results or {}

    async def convert_batch(self, keys):
        if self._side_effect:
            raise self._side_effect
        return self._results


class TestConvertSubBatch:
    """Tests for _convert_sub_batch error handling."""

    @pytest.mark.asyncio
    async def test_sync_failure_error_propagates(self):
        """SyncFailureError from converter propagates (kills sync)."""
        builder = TextualRepresentationBuilder(converter_registry=MagicMock())
        converter = FakeConverter(side_effect=SyncFailureError("infra down"))
        ctx = FakeSyncContext()
        entity = _make_entity()

        with pytest.raises(SyncFailureError, match="infra down"):
            await builder._convert_sub_batch(converter, [(entity, "/path")], ctx)

    @pytest.mark.asyncio
    async def test_entity_processing_error_skips_sub_batch(self):
        """EntityProcessingError from converter → sub-batch entities returned as failures."""
        builder = TextualRepresentationBuilder(converter_registry=MagicMock())
        converter = FakeConverter(side_effect=EntityProcessingError("bad format"))
        ctx = FakeSyncContext()
        entity = _make_entity()

        failures = await builder._convert_sub_batch(converter, [(entity, "/path")], ctx)

        assert failures == [entity]
        ctx.logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_generic_exception_marks_failed_but_continues(self):
        """Unexpected exception → sub-batch entities returned as failures, error logged."""
        builder = TextualRepresentationBuilder(converter_registry=MagicMock())
        converter = FakeConverter(side_effect=RuntimeError("unexpected"))
        ctx = FakeSyncContext()
        entity = _make_entity()

        failures = await builder._convert_sub_batch(converter, [(entity, "/path")], ctx)

        assert failures == [entity]
        ctx.logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_successful_conversion_appends_content(self):
        """Successful conversion appends content to textual_representation."""
        builder = TextualRepresentationBuilder(converter_registry=MagicMock())
        converter = FakeConverter(results={"/path": "Hello world content"})
        ctx = FakeSyncContext()
        entity = _make_entity()

        failures = await builder._convert_sub_batch(converter, [(entity, "/path")], ctx)

        assert failures == []
        assert "Hello world content" in entity.textual_representation

    @pytest.mark.asyncio
    async def test_no_content_returns_entity_as_failure(self):
        """Conversion returning None for a key → entity listed as failure."""
        builder = TextualRepresentationBuilder(converter_registry=MagicMock())
        converter = FakeConverter(results={"/path": None})
        ctx = FakeSyncContext()
        entity = _make_entity()

        failures = await builder._convert_sub_batch(converter, [(entity, "/path")], ctx)

        assert failures == [entity]


class TestGetConverterAndKey:
    """Tests for _get_converter_and_key dispatch and guards."""

    def test_raises_when_registry_is_none(self):
        from airweave.platform.entities._base import WebEntity

        builder = TextualRepresentationBuilder(converter_registry=None)
        entity = MagicMock(spec=WebEntity)
        entity.entity_id = "e1"
        with pytest.raises(EntityProcessingError, match="registry"):
            builder._get_converter_and_key(entity)

    def test_web_entity_returns_web_converter(self):
        from airweave.platform.entities._base import WebEntity

        fake_web_converter = MagicMock()
        registry = MagicMock()
        registry.for_web.return_value = fake_web_converter
        builder = TextualRepresentationBuilder(converter_registry=registry)

        entity = MagicMock(spec=WebEntity)
        entity.entity_id = "e1"
        entity.crawl_url = "https://example.com"

        converter, key = builder._get_converter_and_key(entity)

        assert converter is fake_web_converter
        assert key == "https://example.com"

    def test_file_entity_unsupported_extension_raises(self):
        from airweave.platform.entities._base import FileEntity

        registry = MagicMock()
        builder = TextualRepresentationBuilder(converter_registry=registry)

        entity = MagicMock(spec=FileEntity)
        entity.entity_id = "e1"
        entity.local_path = "/tmp/some_file.xyz_unsupported"

        with pytest.raises(EntityProcessingError, match="Unsupported"):
            builder._get_converter_and_key(entity)

    def test_file_entity_no_converter_for_extension_raises(self):
        from airweave.platform.entities._base import FileEntity
        from airweave.domains.sync_pipeline.file_types import SUPPORTED_FILE_EXTENSIONS

        supported_ext = next(iter(SUPPORTED_FILE_EXTENSIONS))
        registry = MagicMock()
        registry.for_extension.return_value = None
        builder = TextualRepresentationBuilder(converter_registry=registry)

        entity = MagicMock(spec=FileEntity)
        entity.entity_id = "e1"
        entity.local_path = f"/tmp/myfile{supported_ext}"

        with pytest.raises(EntityProcessingError, match="Unsupported"):
            builder._get_converter_and_key(entity)


class TestHandleConversionFailures:
    """Tests for _handle_conversion_failures removal and tracking."""

    @pytest.mark.asyncio
    async def test_no_failures_is_noop(self):
        builder = TextualRepresentationBuilder()
        ctx = FakeSyncContext()
        runtime = FakeRuntime()
        entities = [_make_entity("e1")]

        await builder._handle_conversion_failures(entities, [], ctx, runtime)

        assert len(entities) == 1
        runtime.entity_tracker.record_skipped.assert_not_called()

    @pytest.mark.asyncio
    async def test_failures_removed_and_tracked(self):
        builder = TextualRepresentationBuilder()
        ctx = FakeSyncContext()
        runtime = FakeRuntime()
        e1 = _make_entity("e1")
        e2 = _make_entity("e2")
        entities = [e1, e2]

        await builder._handle_conversion_failures(entities, [e2], ctx, runtime)

        assert entities == [e1]
        runtime.entity_tracker.record_skipped.assert_called_once_with(1)
