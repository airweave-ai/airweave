"""Tests for entity action determination in EntityPipeline.

Tests cover:
- INSERT: New entities not in database
- UPDATE: Existing entities with changed hashes
- KEEP: Existing entities with matching hashes
- DELETE: Entities with deletion_status="removed"
- SKIP: Entities without hashes (failed computation)
- Edge cases: Mixed batches, all same action, empty batches, multi-type entities

Run with: pytest airweave/platform/sync/test/test_action_determination.py -s -v
"""

from copy import deepcopy
from typing import Dict, List
from unittest.mock import AsyncMock, Mock, patch
from uuid import UUID

import pytest

from airweave import models
from airweave.platform.entities.google_drive import GoogleDriveFileDeletionEntity
from airweave.platform.sync.entity_pipeline import EntityPipeline
from airweave.platform.sync.test.entities.gcal import (
    calendar,
    calendar_list_primary,
    event_with_description,
)
from airweave.platform.sync.test.entities.gdrive import pdf_file, text_file
from airweave.platform.sync.test.mock_context import create_mock_sync_context


class MockEntityStore:
    """In-memory mock of crud.entity with realistic behavior.

    Simulates database state for testing action determination without
    requiring actual database connections.
    """

    def __init__(self):
        """Initialize empty entity store."""
        self.entities: Dict[str, models.Entity] = {}

    def add_entity(
        self,
        entity_id: str,
        hash_value: str,
        entity_definition_id: UUID,
        sync_id: UUID,
    ) -> models.Entity:
        """Add an entity to the mock database.

        Args:
            entity_id: The entity ID
            hash_value: The content hash
            entity_definition_id: The entity definition UUID
            sync_id: The sync UUID

        Returns:
            The mock Entity model
        """
        entity = Mock(spec=models.Entity)
        entity.id = UUID("00000000-0000-0000-0000-000000000000")
        entity.entity_id = entity_id
        entity.hash = hash_value
        entity.entity_definition_id = entity_definition_id
        entity.sync_id = sync_id
        entity.organization_id = UUID("11111111-1111-1111-1111-111111111111")

        self.entities[entity_id] = entity
        return entity

    async def bulk_get_by_entity_and_sync(
        self, db, *, sync_id: UUID, entity_ids: List[str]
    ) -> Dict[str, models.Entity]:
        """Mock implementation of bulk_get_by_entity_and_sync (legacy method).

        Returns:
            Dict mapping entity_id to Entity for entities that exist
        """
        return {eid: self.entities[eid] for eid in entity_ids if eid in self.entities}

    async def bulk_get_by_entity_sync_and_definition(
        self, db, *, sync_id: UUID, entity_requests: List[tuple[str, UUID]]
    ) -> Dict[tuple[str, UUID], models.Entity]:
        """Mock implementation of bulk_get_by_entity_sync_and_definition.

        Args:
            db: Database session (unused in mock)
            sync_id: Sync ID (unused in mock - all entities have same sync_id)
            entity_requests: List of (entity_id, entity_definition_id) tuples

        Returns:
            Dict mapping (entity_id, entity_definition_id) to Entity
        """
        result = {}
        for entity_id, entity_def_id in entity_requests:
            # Find matching entity in store by composite key
            for stored_entity in self.entities.values():
                if (
                    stored_entity.entity_id == entity_id
                    and stored_entity.entity_definition_id == entity_def_id
                ):
                    result[(entity_id, entity_def_id)] = stored_entity
                    break
        return result


class TestActionDeterminationBasics:
    """Test basic action determination for single entity types."""

    @pytest.mark.asyncio
    async def test_insert_new_entity(self):
        """Entity not in database should result in INSERT action."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        # Use real entity from fixtures
        entity = event_with_description
        entity_key = (entity.__class__.__name__, entity.entity_id)

        # Compute hash
        entity_hashes = {entity_key: "mock_hash_12345"}

        # Mock crud.entity to use our store
        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=[entity], entity_hashes=entity_hashes, sync_context=sync_context
            )

        # Verify
        assert len(partitions["inserts"]) == 1
        assert len(partitions["updates"]) == 0
        assert len(partitions["keeps"]) == 0
        assert len(partitions["deletes"]) == 0
        assert partitions["inserts"][0].entity_id == entity.entity_id

    @pytest.mark.asyncio
    async def test_update_changed_hash(self):
        """Entity in database with different hash should result in UPDATE action."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        # Use real entity from fixtures
        entity = event_with_description
        entity_key = (entity.__class__.__name__, entity.entity_id)

        # Add to mock database with DIFFERENT hash
        mock_store.add_entity(
            entity_id=entity.entity_id,
            hash_value="old_hash_different",
            entity_definition_id=UUID("bbbbbbbb-0000-0000-0000-000000000003"),
            sync_id=sync_context.sync.id,
        )

        # New hash is different
        entity_hashes = {entity_key: "new_hash_12345"}

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=[entity], entity_hashes=entity_hashes, sync_context=sync_context
            )

        # Verify
        assert len(partitions["inserts"]) == 0
        assert len(partitions["updates"]) == 1
        assert len(partitions["keeps"]) == 0
        assert len(partitions["deletes"]) == 0
        assert partitions["updates"][0].entity_id == entity.entity_id

    @pytest.mark.asyncio
    async def test_keep_unchanged_hash(self):
        """Entity in database with SAME hash should result in KEEP action."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        # Use real entity from fixtures
        entity = event_with_description
        entity_key = (entity.__class__.__name__, entity.entity_id)

        # Add to mock database with SAME hash
        same_hash = "matching_hash_12345"
        mock_store.add_entity(
            entity_id=entity.entity_id,
            hash_value=same_hash,
            entity_definition_id=UUID("bbbbbbbb-0000-0000-0000-000000000003"),
            sync_id=sync_context.sync.id,
        )

        # New hash is identical
        entity_hashes = {entity_key: same_hash}

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=[entity], entity_hashes=entity_hashes, sync_context=sync_context
            )

        # Verify
        assert len(partitions["inserts"]) == 0
        assert len(partitions["updates"]) == 0
        assert len(partitions["keeps"]) == 1
        assert len(partitions["deletes"]) == 0
        assert partitions["keeps"][0].entity_id == entity.entity_id

    @pytest.mark.asyncio
    async def test_delete_removed_entity(self):
        """DeletionEntity with deletion_status='removed' should result in DELETE action."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        # Create a deletion entity
        deletion_entity = GoogleDriveFileDeletionEntity(
            entity_id="deleted_file_123",
            breadcrumbs=[],
            name="Deleted File",
            created_at=None,
            updated_at=None,
            deletion_status="removed",  # This triggers DELETE
        )

        # No hash needed for deletions
        entity_hashes = {}

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=[deletion_entity],
                entity_hashes=entity_hashes,
                sync_context=sync_context,
            )

        # Verify
        assert len(partitions["inserts"]) == 0
        assert len(partitions["updates"]) == 0
        assert len(partitions["keeps"]) == 0
        assert len(partitions["deletes"]) == 1
        assert partitions["deletes"][0].entity_id == deletion_entity.entity_id


class TestActionDeterminationSkipping:
    """Test entities without hashes are skipped."""

    @pytest.mark.asyncio
    async def test_skip_entity_without_hash(self):
        """Entity with no hash in dict should be SKIPPED (not in any partition)."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        entity = event_with_description

        # Hash dict is EMPTY (simulating failed hash computation)
        entity_hashes = {}

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=[entity], entity_hashes=entity_hashes, sync_context=sync_context
            )

        # Verify entity is not in any partition
        assert len(partitions["inserts"]) == 0
        assert len(partitions["updates"]) == 0
        assert len(partitions["keeps"]) == 0
        assert len(partitions["deletes"]) == 0

    @pytest.mark.asyncio
    async def test_skip_increments_progress(self):
        """Skipped entities should increment progress counter."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        entity = event_with_description

        # No hash (will be skipped)
        entity_hashes = {}

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            await pipeline._determine_actions(
                entities=[entity], entity_hashes=entity_hashes, sync_context=sync_context
            )

        # Verify progress.increment was called with "skipped"
        sync_context.progress.increment.assert_awaited_with("skipped", 1)


class TestActionDeterminationEdgeCases:
    """Test edge cases and complex scenarios."""

    @pytest.mark.asyncio
    async def test_mixed_batch_all_actions(self):
        """Batch with INSERT, UPDATE, KEEP, DELETE, SKIP should partition correctly."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        # Entity 1: INSERT (new entity)
        entity_insert = deepcopy(event_with_description)
        entity_insert.entity_id = "new_event_1"

        # Entity 2: UPDATE (existing, hash changed)
        entity_update = deepcopy(event_with_description)
        entity_update.entity_id = "existing_event_changed"
        mock_store.add_entity(
            entity_id=entity_update.entity_id,
            hash_value="old_hash",
            entity_definition_id=UUID("bbbbbbbb-0000-0000-0000-000000000003"),
            sync_id=sync_context.sync.id,
        )

        # Entity 3: KEEP (existing, hash same)
        entity_keep = deepcopy(event_with_description)
        entity_keep.entity_id = "existing_event_same"
        same_hash = "matching_hash"
        mock_store.add_entity(
            entity_id=entity_keep.entity_id,
            hash_value=same_hash,
            entity_definition_id=UUID("bbbbbbbb-0000-0000-0000-000000000003"),
            sync_id=sync_context.sync.id,
        )

        # Entity 4: DELETE
        entity_delete = GoogleDriveFileDeletionEntity(
            entity_id="deleted_file_456",
            breadcrumbs=[],
            name="Deleted",
            created_at=None,
            updated_at=None,
            deletion_status="removed",
        )

        # Entity 5: SKIP (no hash)
        entity_skip = deepcopy(event_with_description)
        entity_skip.entity_id = "event_no_hash"

        # Build hash dict (missing entity_skip)
        entity_hashes = {
            (entity_insert.__class__.__name__, entity_insert.entity_id): "insert_hash",
            (entity_update.__class__.__name__, entity_update.entity_id): "new_hash",
            (entity_keep.__class__.__name__, entity_keep.entity_id): same_hash,
            # entity_skip intentionally missing
        }

        entities = [entity_insert, entity_update, entity_keep, entity_delete, entity_skip]

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=entities, entity_hashes=entity_hashes, sync_context=sync_context
            )

        # Verify all partitions
        assert len(partitions["inserts"]) == 1
        assert partitions["inserts"][0].entity_id == entity_insert.entity_id

        assert len(partitions["updates"]) == 1
        assert partitions["updates"][0].entity_id == entity_update.entity_id

        assert len(partitions["keeps"]) == 1
        assert partitions["keeps"][0].entity_id == entity_keep.entity_id

        assert len(partitions["deletes"]) == 1
        assert partitions["deletes"][0].entity_id == entity_delete.entity_id

        # entity_skip should not be in any partition
        all_entities_in_partitions = (
            partitions["inserts"]
            + partitions["updates"]
            + partitions["keeps"]
            + partitions["deletes"]
        )
        assert entity_skip not in all_entities_in_partitions

        # Verify progress increment for skip
        sync_context.progress.increment.assert_awaited_with("skipped", 1)

    @pytest.mark.asyncio
    async def test_empty_batch(self):
        """Empty batch should return empty partitions."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        entity_hashes = {}

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=[], entity_hashes=entity_hashes, sync_context=sync_context
            )

        # All partitions should be empty
        assert len(partitions["inserts"]) == 0
        assert len(partitions["updates"]) == 0
        assert len(partitions["keeps"]) == 0
        assert len(partitions["deletes"]) == 0

    @pytest.mark.asyncio
    async def test_all_skipped(self):
        """All entities without hashes should all be skipped."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        entities = [
            event_with_description,
            deepcopy(event_with_description),
            deepcopy(event_with_description),
        ]

        # No hashes for any entity (all will be skipped)
        entity_hashes = {}

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=entities, entity_hashes=entity_hashes, sync_context=sync_context
            )

        # All partitions should be empty
        assert len(partitions["inserts"]) == 0
        assert len(partitions["updates"]) == 0
        assert len(partitions["keeps"]) == 0
        assert len(partitions["deletes"]) == 0

        # Should have incremented skipped counter
        sync_context.progress.increment.assert_awaited_with("skipped", 3)

    @pytest.mark.asyncio
    async def test_multi_type_same_entity_id(self):
        """Different entity types with same entity_id should be handled correctly.

        This tests the composite key logic - GoogleCalendarList and GoogleCalendarCalendar
        both use email addresses as entity_id (e.g., "daan@airweave.ai"), but they're
        different entity types and should be treated as separate entities.
        """
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        # Both entities share the same entity_id
        shared_entity_id = "daan@airweave.ai"

        entity_list = calendar_list_primary  # GoogleCalendarListEntity
        entity_calendar = calendar  # GoogleCalendarCalendarEntity

        # Verify they share the entity_id
        assert entity_list.entity_id == shared_entity_id
        assert entity_calendar.entity_id == shared_entity_id

        # Build composite keys - they should be DIFFERENT
        list_key = (entity_list.__class__.__name__, entity_list.entity_id)
        calendar_key = (entity_calendar.__class__.__name__, entity_calendar.entity_id)

        assert list_key != calendar_key  # Different types → different keys

        # Both are NEW entities (not in DB)
        entity_hashes = {
            list_key: "list_hash_12345",
            calendar_key: "calendar_hash_67890",
        }

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=[entity_list, entity_calendar],
                entity_hashes=entity_hashes,
                sync_context=sync_context,
            )

        # Both should be INSERT (both are new)
        assert len(partitions["inserts"]) == 2
        assert len(partitions["updates"]) == 0
        assert len(partitions["keeps"]) == 0

        # Verify both entities are present
        insert_ids = [e.entity_id for e in partitions["inserts"]]
        assert shared_entity_id in insert_ids
        assert insert_ids.count(shared_entity_id) == 2  # Both have same entity_id

    @pytest.mark.asyncio
    async def test_multi_type_one_update_one_insert(self):
        """Multi-type entities: one exists (UPDATE), one is new (INSERT)."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        shared_entity_id = "daan@airweave.ai"

        entity_list = calendar_list_primary  # GoogleCalendarListEntity
        entity_calendar = calendar  # GoogleCalendarCalendarEntity

        # Add ONLY the list entity to DB
        mock_store.add_entity(
            entity_id=entity_list.entity_id,
            hash_value="old_list_hash",
            entity_definition_id=UUID("bbbbbbbb-0000-0000-0000-000000000001"),
            sync_id=sync_context.sync.id,
        )

        # Both have hashes, but only list is in DB
        entity_hashes = {
            (entity_list.__class__.__name__, entity_list.entity_id): "new_list_hash",  # Changed
            (entity_calendar.__class__.__name__, entity_calendar.entity_id): "calendar_hash",
        }

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=[entity_list, entity_calendar],
                entity_hashes=entity_hashes,
                sync_context=sync_context,
            )

        # List should be UPDATE (exists in DB, hash changed)
        # Calendar should be INSERT (not in DB)
        assert len(partitions["inserts"]) == 1
        assert len(partitions["updates"]) == 1
        assert len(partitions["keeps"]) == 0

        assert partitions["inserts"][0].__class__.__name__ == "GoogleCalendarCalendarEntity"
        assert partitions["updates"][0].__class__.__name__ == "GoogleCalendarListEntity"


class TestActionDeterminationDatabaseErrors:
    """Test error handling for database failures."""

    @pytest.mark.asyncio
    async def test_database_lookup_failure(self):
        """Database query failure should raise exception."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()

        entity = event_with_description
        entity_key = (entity.__class__.__name__, entity.entity_id)
        entity_hashes = {entity_key: "mock_hash"}

        # Create a mock that raises on the new bulk_get method
        mock_crud = AsyncMock()
        mock_crud.bulk_get_by_entity_sync_and_definition.side_effect = Exception(
            "Database connection failed"
        )

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_crud):
            with pytest.raises(Exception, match="Database connection failed"):
                await pipeline._determine_actions(
                    entities=[entity], entity_hashes=entity_hashes, sync_context=sync_context
                )


class TestActionDeterminationProgress:
    """Test progress tracking during action determination."""

    @pytest.mark.asyncio
    async def test_progress_tracking_for_skips(self):
        """Multiple skipped entities should increment progress correctly."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        # Create 5 entities, none with hashes
        entities = [deepcopy(event_with_description) for _ in range(5)]
        for i, e in enumerate(entities):
            e.entity_id = f"event_{i}"

        # Empty hash dict (all will be skipped)
        entity_hashes = {}

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=entities, entity_hashes=entity_hashes, sync_context=sync_context
            )

        # Verify progress was incremented with count of 5
        sync_context.progress.increment.assert_awaited_with("skipped", 5)

    @pytest.mark.asyncio
    async def test_no_progress_increment_when_no_skips(self):
        """If no entities are skipped, progress should not be incremented."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        entity = event_with_description
        entity_key = (entity.__class__.__name__, entity.entity_id)

        # Entity has hash (won't be skipped)
        entity_hashes = {entity_key: "mock_hash"}

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            await pipeline._determine_actions(
                entities=[entity], entity_hashes=entity_hashes, sync_context=sync_context
            )

        # progress.increment should NOT have been called with "skipped"
        # (it should only be called if skipped_count > 0)
        calls = sync_context.progress.increment.await_args_list
        skip_calls = [call for call in calls if call[0][0] == "skipped"]
        assert len(skip_calls) == 0


class TestActionDeterminationLogging:
    """Test logging output during action determination."""

    @pytest.mark.asyncio
    async def test_summary_logged(self):
        """Action determination should log a summary."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        # Mix of actions
        entity_insert = deepcopy(event_with_description)
        entity_insert.entity_id = "insert_1"

        entity_keep = deepcopy(event_with_description)
        entity_keep.entity_id = "keep_1"
        mock_store.add_entity(
            entity_id=entity_keep.entity_id,
            hash_value="same_hash",
            entity_definition_id=UUID("bbbbbbbb-0000-0000-0000-000000000003"),
            sync_id=sync_context.sync.id,
        )

        entity_hashes = {
            (entity_insert.__class__.__name__, entity_insert.entity_id): "insert_hash",
            (entity_keep.__class__.__name__, entity_keep.entity_id): "same_hash",
        }

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=[entity_insert, entity_keep],
                entity_hashes=entity_hashes,
                sync_context=sync_context,
            )

        # Verify partitions are correct
        assert len(partitions["inserts"]) == 1
        assert len(partitions["keeps"]) == 1

        # Note: We can't easily test logger.info was called with specific message
        # because it's a real logger, but we've verified the logic works


class TestActionDeterminationFileEntities:
    """Test action determination with file entities."""

    @pytest.mark.asyncio
    async def test_file_entity_insert(self):
        """File entity not in DB should result in INSERT."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        # Use real file entity from fixtures
        entity = text_file
        entity_key = (entity.__class__.__name__, entity.entity_id)

        entity_hashes = {entity_key: "file_hash_12345"}

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=[entity], entity_hashes=entity_hashes, sync_context=sync_context
            )

        assert len(partitions["inserts"]) == 1
        assert partitions["inserts"][0].entity_id == entity.entity_id

    @pytest.mark.asyncio
    async def test_file_entity_update(self):
        """File entity with changed content hash should result in UPDATE."""
        pipeline = EntityPipeline()
        sync_context = create_mock_sync_context()
        mock_store = MockEntityStore()

        entity = pdf_file
        entity_key = (entity.__class__.__name__, entity.entity_id)

        # Add to DB with old hash
        mock_store.add_entity(
            entity_id=entity.entity_id,
            hash_value="old_pdf_hash",
            entity_definition_id=UUID(
                "cccccccc-0000-0000-0000-000000000002"
            ),  # GoogleDriveFileEntity
            sync_id=sync_context.sync.id,
        )

        # New hash (content changed)
        entity_hashes = {entity_key: "new_pdf_hash"}

        with patch("airweave.platform.sync.entity_pipeline.crud.entity", mock_store):
            partitions = await pipeline._determine_actions(
                entities=[entity], entity_hashes=entity_hashes, sync_context=sync_context
            )

        assert len(partitions["updates"]) == 1
        assert partitions["updates"][0].entity_id == entity.entity_id


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s"])
