"""Integration tests for entity pipeline persistence."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from airweave.platform.sync.entity_pipeline import EntityPipeline
from airweave.platform.sync.exceptions import SyncFailureError
from airweave.platform.sync.test.entities.gdrive import (
    amazon_2023_pdf,
    amazon_2024_pdf,
    pdf_file,
    text_file,
)


@pytest.fixture
def sync_context():
    """Mock sync context."""
    ctx = MagicMock()
    ctx.sync.id = uuid4()
    ctx.sync_job.id = uuid4()
    ctx.source._short_name = "google_drive"
    ctx.entity_map = {type(text_file): uuid4(), type(pdf_file): uuid4()}
    ctx.destinations = [AsyncMock()]
    ctx.logger = MagicMock()
    ctx.progress = AsyncMock()
    ctx.ctx = MagicMock()
    ctx.has_keyword_index = False  # Simplify for tests
    return ctx


@pytest.mark.asyncio
async def test_insert_creates_unique_chunks(sync_context):
    """Test INSERT: chunks have unique entity_ids and original_entity_id set."""
    pipeline = EntityPipeline()
    entities = [text_file]

    with (
        patch("airweave.crud.entity.bulk_create") as mock_create,
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        mock_get.return_value = {}  # No existing (INSERT)
        mock_create.return_value = [MagicMock(entity_id=text_file.entity_id, id=uuid4())]

        await pipeline.process(entities, sync_context)

        # Verify Qdrant insert called
        qdrant = sync_context.destinations[0]
        assert qdrant.bulk_insert.called

        chunks = qdrant.bulk_insert.call_args[0][0]

        # Verify unique chunk IDs
        chunk_ids = [c.entity_id for c in chunks]
        assert len(chunk_ids) == len(set(chunk_ids))

        # Verify all chunks have pattern and parent ref
        for chunk in chunks:
            assert "__chunk_" in chunk.entity_id
            assert chunk.airweave_system_metadata.original_entity_id == text_file.entity_id
            assert chunk.airweave_system_metadata.chunk_index is not None


@pytest.mark.asyncio
async def test_update_clears_then_inserts(sync_context):
    """Test UPDATE: Qdrant delete → insert → DB hash update."""
    pipeline = EntityPipeline()
    entity = amazon_2024_pdf
    old_hash = "old_hash"

    with (
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.crud.entity.bulk_update_hash") as mock_update,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        mock_get.return_value = {
            (entity.entity_id, sync_context.entity_map[type(entity)]): MagicMock(
                entity_id=entity.entity_id, id=uuid4(), hash=old_hash
            )
        }

        await pipeline.process([entity], sync_context)

        qdrant = sync_context.destinations[0]

        # Verify delete called
        assert qdrant.bulk_delete_by_parent_ids.called
        assert entity.entity_id in qdrant.bulk_delete_by_parent_ids.call_args[0][0]

        # Verify insert called
        assert qdrant.bulk_insert.called

        # Verify hash update called
        assert mock_update.called


@pytest.mark.asyncio
async def test_keep_skips_all(sync_context):
    """Test KEEP: hash matches → no operations."""
    pipeline = EntityPipeline()
    entity = text_file

    with (
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        # Compute hash for entity
        await pipeline.compute_hashes_for_batch([entity], sync_context)

        # Same hash in DB (KEEP)
        mock_get.return_value = {
            (entity.entity_id, sync_context.entity_map[type(entity)]): MagicMock(
                entity_id=entity.entity_id,
                id=uuid4(),
                hash=entity.airweave_system_metadata.hash,
            )
        }

        await pipeline.process([entity], sync_context)

        qdrant = sync_context.destinations[0]
        assert not qdrant.bulk_insert.called
        assert not qdrant.bulk_delete_by_parent_ids.called


@pytest.mark.asyncio
async def test_qdrant_failure_prevents_db_write(sync_context):
    """Test failure: Qdrant fails → DB not updated → retry next sync."""
    pipeline = EntityPipeline()
    entity = amazon_2023_pdf

    # Make Qdrant fail
    sync_context.destinations[0].bulk_insert.side_effect = Exception("Timeout")

    with (
        patch("airweave.crud.entity.bulk_create") as mock_create,
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        mock_get.return_value = {}

        with pytest.raises(SyncFailureError, match="Destination insert failed"):
            await pipeline.process([entity], sync_context)

        # DB not called (destination failed before DB)
        assert not mock_create.called


@pytest.mark.asyncio
async def test_deduplication_in_batch(sync_context):
    """Test same entity twice in batch → deduplicated."""
    pipeline = EntityPipeline()
    entities = [text_file, text_file]  # Duplicate

    with (
        patch("airweave.crud.entity.bulk_create") as mock_create,
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        mock_get.return_value = {}
        mock_create.return_value = [MagicMock(entity_id=text_file.entity_id, id=uuid4())]

        await pipeline.process(entities, sync_context)

        # Only one DB record created
        create_objs = mock_create.call_args[1]["objs"]
        assert len(create_objs) == 1


@pytest.mark.asyncio
async def test_delete_flow_removes_from_both(sync_context):
    """Test DELETE: Qdrant delete → DB delete."""
    from airweave.platform.entities._base import DeletionEntity

    pipeline = EntityPipeline()

    # Create deletion entity
    class TestDeletionEntity(DeletionEntity):
        pass

    # Add to entity map
    sync_context.entity_map[TestDeletionEntity] = uuid4()

    entity = TestDeletionEntity(
        entity_id="deleted_123",
        deletion_status="removed",
        breadcrumbs=[],
        name="Deleted File",
        created_at=None,
        updated_at=None,
    )

    db_id = uuid4()

    with (
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.crud.entity.bulk_remove") as mock_remove,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        mock_get.return_value = {
            (entity.entity_id, sync_context.entity_map[type(entity)]): MagicMock(
                entity_id=entity.entity_id, id=db_id
            )
        }

        # Initialize metadata for deletion entity
        from airweave.platform.entities._base import AirweaveSystemMetadata

        entity.airweave_system_metadata = AirweaveSystemMetadata()

        await pipeline.process([entity], sync_context)

        # Verify Qdrant delete
        qdrant = sync_context.destinations[0]
        assert qdrant.bulk_delete_by_parent_ids.called

        # Verify DB delete
        assert mock_remove.called
        deleted_ids = mock_remove.call_args[1]["ids"]
        assert db_id in deleted_ids


@pytest.mark.asyncio
async def test_chunk_metadata_validation(sync_context):
    """Test validation ensures chunks have required metadata."""
    pipeline = EntityPipeline()
    entities = [text_file]

    with (
        patch("airweave.crud.entity.bulk_create") as mock_create,
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        mock_get.return_value = {}
        mock_create.return_value = [MagicMock(entity_id=text_file.entity_id, id=uuid4())]

        await pipeline.process(entities, sync_context)

        # Get chunks from Qdrant call
        qdrant = sync_context.destinations[0]
        chunks = qdrant.bulk_insert.call_args[0][0]

        # Verify all required metadata present
        for chunk in chunks:
            assert chunk.airweave_system_metadata.chunk_index is not None
            assert chunk.airweave_system_metadata.original_entity_id is not None
            assert chunk.airweave_system_metadata.sync_id is not None
            assert chunk.airweave_system_metadata.vectors is not None


@pytest.mark.asyncio
async def test_batch_with_only_deletes(sync_context):
    """Test batch containing ONLY deletes (no inserts/updates)."""
    from airweave.platform.entities._base import AirweaveSystemMetadata, DeletionEntity

    pipeline = EntityPipeline()

    class TestDeletionEntity(DeletionEntity):
        pass

    sync_context.entity_map[TestDeletionEntity] = uuid4()

    entity = TestDeletionEntity(
        entity_id="only_delete",
        deletion_status="removed",
        breadcrumbs=[],
        name="Only Delete",
        created_at=None,
        updated_at=None,
    )

    entity.airweave_system_metadata = AirweaveSystemMetadata()

    db_id = uuid4()

    with (
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.crud.entity.bulk_remove") as mock_remove,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        mock_get.return_value = {
            (entity.entity_id, sync_context.entity_map[type(entity)]): MagicMock(
                entity_id=entity.entity_id, id=db_id
            )
        }

        await pipeline.process([entity], sync_context)

        # Verify deletes happened (not skipped)
        assert mock_remove.called
        assert sync_context.destinations[0].bulk_delete_by_parent_ids.called


@pytest.mark.asyncio
async def test_mixed_batch_inserts_updates_deletes(sync_context):
    """Test batch with inserts, updates, and deletes all together."""
    from airweave.platform.entities._base import AirweaveSystemMetadata, DeletionEntity

    pipeline = EntityPipeline()

    class TestDeletionEntity(DeletionEntity):
        pass

    sync_context.entity_map[TestDeletionEntity] = uuid4()

    # Create mixed batch
    insert_entity = text_file
    update_entity = amazon_2024_pdf
    delete_entity = TestDeletionEntity(
        entity_id="mixed_delete",
        deletion_status="removed",
        breadcrumbs=[],
        name="Delete",
        created_at=None,
        updated_at=None,
    )
    delete_entity.airweave_system_metadata = AirweaveSystemMetadata()

    entities = [insert_entity, update_entity, delete_entity]

    with (
        patch("airweave.crud.entity.bulk_create") as mock_create,
        patch("airweave.crud.entity.bulk_update_hash") as mock_update,
        patch("airweave.crud.entity.bulk_remove") as mock_remove,
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        # Setup: update exists, insert doesn't, delete exists
        mock_get.return_value = {
            (update_entity.entity_id, sync_context.entity_map[type(update_entity)]): MagicMock(
                entity_id=update_entity.entity_id, id=uuid4(), hash="old"
            ),
            (delete_entity.entity_id, sync_context.entity_map[type(delete_entity)]): MagicMock(
                entity_id=delete_entity.entity_id, id=uuid4()
            ),
        }
        mock_create.return_value = [MagicMock(entity_id=insert_entity.entity_id, id=uuid4())]

        await pipeline.process(entities, sync_context)

        # Verify all operations called
        assert mock_create.called  # INSERT
        assert mock_update.called  # UPDATE
        assert mock_remove.called  # DELETE

        qdrant = sync_context.destinations[0]
        assert qdrant.bulk_insert.called  # Chunks for insert + update
        assert qdrant.bulk_delete_by_parent_ids.called  # Clear update + delete


@pytest.mark.asyncio
async def test_delete_not_in_db_is_ok(sync_context):
    """Test deleting entity that was never synced (no DB record) - should not fail."""
    from airweave.platform.entities._base import AirweaveSystemMetadata, DeletionEntity

    pipeline = EntityPipeline()

    class TestDeletionEntity(DeletionEntity):
        pass

    sync_context.entity_map[TestDeletionEntity] = uuid4()

    entity = TestDeletionEntity(
        entity_id="never_synced",
        deletion_status="removed",
        breadcrumbs=[],
        name="Never Synced",
        created_at=None,
        updated_at=None,
    )
    entity.airweave_system_metadata = AirweaveSystemMetadata()

    with (
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.crud.entity.bulk_remove") as mock_remove,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        # Entity not in DB
        mock_get.return_value = {}

        # Should not fail
        await pipeline.process([entity], sync_context)

        # Qdrant delete still called (idempotent)
        assert sync_context.destinations[0].bulk_delete_by_parent_ids.called

        # DB remove NOT called (nothing to delete)
        assert not mock_remove.called


@pytest.mark.asyncio
async def test_concurrent_duplicate_across_batches(sync_context):
    """Test cross-batch duplicates handled by bulk_create upsert."""
    # Create separate pipeline instances to simulate different workers
    pipeline1 = EntityPipeline()
    pipeline2 = EntityPipeline()

    # Simulate same entity in different batches (upsert should handle)
    entity = text_file

    with (
        patch("airweave.crud.entity.bulk_create") as mock_create,
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        mock_get.return_value = {}

        # First batch inserts
        mock_create.return_value = [MagicMock(entity_id=entity.entity_id, id=uuid4())]
        await pipeline1.process([entity], sync_context)

        # Second batch tries to insert same entity (race condition from different worker)
        # bulk_create's upsert should update, not fail
        await pipeline2.process([entity], sync_context)

        # Should have been called twice (both batches)
        assert mock_create.call_count == 2


@pytest.mark.asyncio
async def test_empty_batch_handles_gracefully(sync_context):
    """Test empty batch doesn't fail."""
    pipeline = EntityPipeline()

    # Should not raise
    await pipeline.process([], sync_context)


@pytest.mark.asyncio
async def test_all_keeps_early_exit(sync_context):
    """Test batch with only KEEP entities exits early."""
    pipeline = EntityPipeline()
    entity = text_file

    with (
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.crud.entity.bulk_create") as mock_create,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        # Compute hash
        await pipeline.compute_hashes_for_batch([entity], sync_context)

        # Same hash (KEEP)
        mock_get.return_value = {
            (entity.entity_id, sync_context.entity_map[type(entity)]): MagicMock(
                entity_id=entity.entity_id, id=uuid4(), hash=entity.airweave_system_metadata.hash
            )
        }

        await pipeline.process([entity], sync_context)

        # No DB/Qdrant operations
        assert not mock_create.called
        assert not sync_context.destinations[0].bulk_insert.called

        # Progress updated
        assert sync_context.progress.increment.called


@pytest.mark.asyncio
async def test_destination_failure_on_update_clear(sync_context):
    """Test failure during update clear phase (before insert)."""
    pipeline = EntityPipeline()
    entity = amazon_2024_pdf

    # Make delete fail
    sync_context.destinations[0].bulk_delete_by_parent_ids.side_effect = Exception("Delete failed")

    with (
        patch("airweave.crud.entity.bulk_get_by_entity_sync_and_definition") as mock_get,
        patch("airweave.crud.entity.bulk_update_hash") as mock_update,
        patch("airweave.platform.sync.entity_pipeline.get_db_context"),
    ):
        mock_get.return_value = {
            (entity.entity_id, sync_context.entity_map[type(entity)]): MagicMock(
                entity_id=entity.entity_id, id=uuid4(), hash="old"
            )
        }

        with pytest.raises(SyncFailureError, match="Destination clear failed"):
            await pipeline.process([entity], sync_context)

        # Hash not updated (failure before commit point)
        assert not mock_update.called
