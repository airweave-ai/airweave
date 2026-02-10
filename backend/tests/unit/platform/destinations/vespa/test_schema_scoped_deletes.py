"""Tests for schema-scoped Vespa deletes.

Verifies that update deletes only scan the entity's actual Vespa schema
instead of all 5 schemas, reducing delete time from 5x to 1x.
"""

import asyncio
from typing import List, Optional
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from airweave.platform.destinations.vespa.client import VespaClient
from airweave.platform.destinations.vespa.config import ALL_VESPA_SCHEMAS
from airweave.platform.destinations.vespa.types import DeleteResult
from airweave.platform.sync.handlers.destination import DestinationHandler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entity(entity_class_name: str, entity_id: str = "test-123"):
    """Create a mock entity that isinstance checks work on."""
    from airweave.platform.entities._base import (
        BaseEntity,
        CodeFileEntity,
        EmailEntity,
        FileEntity,
        WebEntity,
    )

    class_map = {
        "FileEntity": FileEntity,
        "CodeFileEntity": CodeFileEntity,
        "EmailEntity": EmailEntity,
        "WebEntity": WebEntity,
        "BaseEntity": BaseEntity,
    }

    entity = MagicMock(spec=class_map[entity_class_name])
    entity.__class__ = class_map[entity_class_name]
    entity.entity_id = entity_id
    entity.name = f"test-{entity_class_name}"
    entity.airweave_system_metadata = MagicMock()
    entity.airweave_system_metadata.entity_type = entity_class_name
    return entity


def _make_mock_sync_context():
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.sync = MagicMock()
    ctx.sync.id = uuid4()
    return ctx


# ===========================================================================
# VespaClient.delete_by_parent_ids — schema scoping
# ===========================================================================


class TestVespaClientSchemaScoping:
    """Test that delete_by_parent_ids respects the schemas parameter."""

    @pytest.fixture
    def client(self):
        mock_app = MagicMock()
        c = VespaClient(app=mock_app)
        c.delete_by_selection = AsyncMock(
            return_value=DeleteResult(deleted_count=0, schema="test")
        )
        return c

    @pytest.fixture
    def collection_id(self):
        return UUID("12345678-1234-1234-1234-123456789abc")

    @pytest.mark.asyncio
    async def test_no_schemas_scans_all_five(self, client, collection_id):
        """When schemas=None, all 5 schemas are scanned (backward compat)."""
        await client.delete_by_parent_ids(["entity-1"], collection_id)

        assert client.delete_by_selection.call_count == len(ALL_VESPA_SCHEMAS)
        called_schemas = [
            call.args[0] for call in client.delete_by_selection.call_args_list
        ]
        assert set(called_schemas) == set(ALL_VESPA_SCHEMAS)

    @pytest.mark.asyncio
    async def test_single_schema_scans_only_one(self, client, collection_id):
        """When schemas=['file_entity'], only file_entity is scanned."""
        await client.delete_by_parent_ids(
            ["entity-1"], collection_id, schemas=["file_entity"]
        )

        assert client.delete_by_selection.call_count == 1
        assert client.delete_by_selection.call_args_list[0].args[0] == "file_entity"

    @pytest.mark.asyncio
    async def test_two_schemas_scans_only_two(self, client, collection_id):
        """When schemas=['file_entity', 'base_entity'], only those two are scanned."""
        await client.delete_by_parent_ids(
            ["entity-1"], collection_id, schemas=["file_entity", "base_entity"]
        )

        assert client.delete_by_selection.call_count == 2
        called_schemas = {
            call.args[0] for call in client.delete_by_selection.call_args_list
        }
        assert called_schemas == {"file_entity", "base_entity"}

    @pytest.mark.asyncio
    async def test_empty_parent_ids_skips_all(self, client, collection_id):
        """Empty parent_ids should return immediately without any deletes."""
        result = await client.delete_by_parent_ids([], collection_id)

        assert result == []
        client.delete_by_selection.assert_not_called()

    @pytest.mark.asyncio
    async def test_selection_expression_uses_correct_schema(self, client, collection_id):
        """The selection expression should reference the correct schema name."""
        await client.delete_by_parent_ids(
            ["doc-abc"], collection_id, schemas=["email_entity"]
        )

        selection_arg = client.delete_by_selection.call_args_list[0].args[1]
        assert "email_entity.airweave_system_metadata_original_entity_id=='doc-abc'" in selection_arg
        assert f"email_entity.airweave_system_metadata_collection_id=='{collection_id}'" in selection_arg

    @pytest.mark.asyncio
    async def test_multiple_parent_ids_in_selection(self, client, collection_id):
        """Multiple parent IDs should be OR'd in the selection expression."""
        await client.delete_by_parent_ids(
            ["doc-1", "doc-2", "doc-3"], collection_id, schemas=["file_entity"]
        )

        selection_arg = client.delete_by_selection.call_args_list[0].args[1]
        assert "doc-1" in selection_arg
        assert "doc-2" in selection_arg
        assert "doc-3" in selection_arg
        assert " or " in selection_arg

    @pytest.mark.asyncio
    async def test_batching_with_schema_scoping(self, client, collection_id):
        """Large parent_id lists should be batched, each batch using scoped schemas."""
        parent_ids = [f"doc-{i}" for i in range(75)]

        await client.delete_by_parent_ids(
            parent_ids, collection_id, batch_size=50, schemas=["web_entity"]
        )

        # 75 IDs / 50 batch size = 2 batches, each scanning 1 schema = 2 calls
        assert client.delete_by_selection.call_count == 2
        for call in client.delete_by_selection.call_args_list:
            assert call.args[0] == "web_entity"

    @pytest.mark.asyncio
    async def test_batching_without_scoping_scans_all(self, client, collection_id):
        """Without schema scoping, batching scans all schemas per batch."""
        parent_ids = [f"doc-{i}" for i in range(75)]

        await client.delete_by_parent_ids(parent_ids, collection_id, batch_size=50)

        # 2 batches * 5 schemas = 10 calls
        assert client.delete_by_selection.call_count == 10


# ===========================================================================
# VespaDestination.bulk_delete_by_parent_ids — entity-to-schema mapping
# ===========================================================================


class TestVespaDestinationSchemaMapping:
    """Test that VespaDestination derives the correct schema from entity type."""

    @pytest.mark.asyncio
    async def test_file_entity_maps_to_file_entity_schema(self):
        """FileEntity should only delete from file_entity schema."""
        from airweave.platform.destinations.vespa.destination import VespaDestination
        from airweave.platform.destinations.vespa.transformer import EntityTransformer

        with patch(
            "airweave.platform.destinations.vespa.destination.VespaClient.connect",
            new_callable=AsyncMock,
        ) as mock_connect, patch(
            "airweave.platform.destinations.vespa.destination.QueryBuilder"
        ):
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            mock_client.delete_by_parent_ids = AsyncMock()

            dest = await VespaDestination.create(
                collection_id=UUID("12345678-1234-1234-1234-123456789abc")
            )
            # Replace with real transformer so _get_vespa_schema works
            dest._transformer = EntityTransformer(logger=MagicMock())

            entity = _make_entity("FileEntity", "file-1")

            await dest.bulk_delete_by_parent_ids(
                ["file-1"], uuid4(), entities=[entity]
            )

            mock_client.delete_by_parent_ids.assert_called_once()
            call_kwargs = mock_client.delete_by_parent_ids.call_args
            schemas = call_kwargs.kwargs.get("schemas")
            assert schemas == ["file_entity"]

    @pytest.mark.asyncio
    async def test_no_entities_scans_all_schemas(self):
        """Without entities, should scan all schemas (backward compat)."""
        with patch(
            "airweave.platform.destinations.vespa.destination.VespaClient.connect",
            new_callable=AsyncMock,
        ) as mock_connect, patch(
            "airweave.platform.destinations.vespa.destination.EntityTransformer"
        ), patch(
            "airweave.platform.destinations.vespa.destination.QueryBuilder"
        ):
            mock_client = AsyncMock()
            mock_connect.return_value = mock_client
            mock_client.delete_by_parent_ids = AsyncMock()

            dest = await (
                __import__(
                    "airweave.platform.destinations.vespa.destination",
                    fromlist=["VespaDestination"],
                )
            ).VespaDestination.create(collection_id=UUID("12345678-1234-1234-1234-123456789abc"))

            await dest.bulk_delete_by_parent_ids(["entity-1"], uuid4())

            call_kwargs = mock_client.delete_by_parent_ids.call_args
            schemas = call_kwargs.kwargs.get("schemas") or call_kwargs[1].get("schemas") if call_kwargs[1] else None
            assert schemas is None


# ===========================================================================
# DestinationHandler — entities flow through to destination
# ===========================================================================


class TestDestinationHandlerPassesEntities:
    """Test that DestinationHandler passes entities to bulk_delete_by_parent_ids."""

    @pytest.mark.asyncio
    async def test_handle_batch_updates_pass_entities(self):
        """handle_batch with updates should pass entities to _do_delete_by_ids."""
        from airweave.platform.sync.actions.entity.types import (
            EntityActionBatch,
            EntityUpdateAction,
        )

        dest = MagicMock()
        dest.__class__.__name__ = "VespaDestination"
        dest.soft_fail = False
        dest.processing_requirement = MagicMock()
        dest.bulk_delete_by_parent_ids = AsyncMock()
        dest.bulk_insert = AsyncMock()

        handler = DestinationHandler([dest])
        ctx = _make_mock_sync_context()

        entity = _make_entity("FileEntity", "file-1")
        update_action = MagicMock(spec=EntityUpdateAction)
        update_action.entity_id = "file-1"
        update_action.entity = entity

        batch = EntityActionBatch(updates=[update_action])

        # Mock _do_process_and_insert to avoid needing real processor
        handler._do_process_and_insert = AsyncMock()

        await handler.handle_batch(batch, ctx)

        # Verify bulk_delete_by_parent_ids was called with entities
        dest.bulk_delete_by_parent_ids.assert_called_once()
        call_kwargs = dest.bulk_delete_by_parent_ids.call_args
        assert call_kwargs.kwargs.get("entities") is not None
        assert len(call_kwargs.kwargs["entities"]) == 1
        assert call_kwargs.kwargs["entities"][0] is entity

    @pytest.mark.asyncio
    async def test_handle_deletes_do_not_pass_entities(self):
        """handle_deletes should NOT pass entities (no schema info needed for full deletes)."""
        from airweave.platform.sync.actions.entity.types import (
            EntityActionBatch,
            EntityDeleteAction,
        )

        dest = MagicMock()
        dest.__class__.__name__ = "VespaDestination"
        dest.soft_fail = False
        dest.processing_requirement = MagicMock()
        dest.bulk_delete_by_parent_ids = AsyncMock()

        handler = DestinationHandler([dest])
        ctx = _make_mock_sync_context()

        entity = _make_entity("FileEntity", "file-1")
        delete_action = MagicMock(spec=EntityDeleteAction)
        delete_action.entity_id = "file-1"
        delete_action.entity = entity

        await handler.handle_deletes([delete_action], ctx)

        # Verify entities=None for regular deletes (not update deletes)
        dest.bulk_delete_by_parent_ids.assert_called_once()
        call_kwargs = dest.bulk_delete_by_parent_ids.call_args
        entities_arg = call_kwargs.kwargs.get("entities")
        assert entities_arg is None

    @pytest.mark.asyncio
    async def test_orphan_cleanup_does_not_pass_entities(self):
        """Orphan cleanup should NOT pass entities (IDs only, type unknown)."""
        dest = MagicMock()
        dest.__class__.__name__ = "VespaDestination"
        dest.soft_fail = False
        dest.processing_requirement = MagicMock()
        dest.bulk_delete_by_parent_ids = AsyncMock()

        handler = DestinationHandler([dest])
        ctx = _make_mock_sync_context()

        await handler.handle_orphan_cleanup(["orphan-1", "orphan-2"], ctx)

        dest.bulk_delete_by_parent_ids.assert_called_once()
        call_kwargs = dest.bulk_delete_by_parent_ids.call_args
        entities_arg = call_kwargs.kwargs.get("entities")
        assert entities_arg is None


# ===========================================================================
# Performance verification: schema count
# ===========================================================================


class TestSchemaCountReduction:
    """Verify the 5x -> 1x reduction claim."""

    def test_all_vespa_schemas_has_five_entries(self):
        """Sanity check: ALL_VESPA_SCHEMAS has exactly 5 schemas."""
        assert len(ALL_VESPA_SCHEMAS) == 5
        assert "base_entity" in ALL_VESPA_SCHEMAS
        assert "file_entity" in ALL_VESPA_SCHEMAS
        assert "code_file_entity" in ALL_VESPA_SCHEMAS
        assert "email_entity" in ALL_VESPA_SCHEMAS
        assert "web_entity" in ALL_VESPA_SCHEMAS

    def test_entity_type_maps_to_exactly_one_schema(self):
        """Each entity type should map to exactly one schema."""
        from airweave.platform.destinations.vespa.transformer import EntityTransformer

        transformer = EntityTransformer(logger=MagicMock())

        for entity_class in ["FileEntity", "CodeFileEntity", "EmailEntity", "WebEntity", "BaseEntity"]:
            entity = _make_entity(entity_class)
            schema = transformer._get_vespa_schema(entity)
            assert schema in ALL_VESPA_SCHEMAS
            assert isinstance(schema, str)

    def test_file_entity_maps_to_file_entity(self):
        from airweave.platform.destinations.vespa.transformer import EntityTransformer

        transformer = EntityTransformer(logger=MagicMock())
        assert transformer._get_vespa_schema(_make_entity("FileEntity")) == "file_entity"

    def test_code_file_entity_maps_to_code_file_entity(self):
        from airweave.platform.destinations.vespa.transformer import EntityTransformer

        transformer = EntityTransformer(logger=MagicMock())
        assert transformer._get_vespa_schema(_make_entity("CodeFileEntity")) == "code_file_entity"

    def test_email_entity_maps_to_email_entity(self):
        from airweave.platform.destinations.vespa.transformer import EntityTransformer

        transformer = EntityTransformer(logger=MagicMock())
        assert transformer._get_vespa_schema(_make_entity("EmailEntity")) == "email_entity"

    def test_web_entity_maps_to_web_entity(self):
        from airweave.platform.destinations.vespa.transformer import EntityTransformer

        transformer = EntityTransformer(logger=MagicMock())
        assert transformer._get_vespa_schema(_make_entity("WebEntity")) == "web_entity"

    def test_base_entity_maps_to_base_entity(self):
        from airweave.platform.destinations.vespa.transformer import EntityTransformer

        transformer = EntityTransformer(logger=MagicMock())
        assert transformer._get_vespa_schema(_make_entity("BaseEntity")) == "base_entity"

    def test_mixed_entity_batch_deduplicates_schemas(self):
        """A batch with 3 FileEntities should produce only 1 schema, not 3."""
        from airweave.platform.destinations.vespa.transformer import EntityTransformer

        transformer = EntityTransformer(logger=MagicMock())

        entities = [
            _make_entity("FileEntity", f"file-{i}") for i in range(3)
        ]
        schemas = list({transformer._get_vespa_schema(e) for e in entities})
        assert schemas == ["file_entity"]
