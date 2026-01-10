"""Tests for EntityActionResolver.

Tests the entity action resolution logic including:
- INSERT/UPDATE/DELETE/KEEP action resolution
- Sync-level vs collection-level deduplication
- Deletion entity handling
- Polymorphic entity handling
- skip_hash_comparison mode
"""

from dataclasses import dataclass
from typing import ClassVar, Optional, Type
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import (
    AirweaveSystemMetadata,
    BaseEntity,
    DeletionEntity,
    PolymorphicEntity,
)
from airweave.platform.sync.actions.entity.resolver import EntityActionResolver
from airweave.platform.sync.actions.entity.types import (
    EntityActionBatch,
    EntityDeleteAction,
    EntityInsertAction,
    EntityKeepAction,
    EntityUpdateAction,
)
from airweave.platform.sync.config import BehaviorConfig, SyncConfig
from airweave.platform.sync.exceptions import SyncFailureError


# =============================================================================
# Test Fixtures
# =============================================================================


class MockEntity(BaseEntity):
    """Simple mock entity for resolver tests."""

    mock_id: str = AirweaveField(..., description="Entity ID", is_entity_id=True)
    mock_name: str = AirweaveField(..., description="Entity name", is_name=True)


class MockEntity2(BaseEntity):
    """Another mock entity type for multi-type tests."""

    mock_id: str = AirweaveField(..., description="Entity ID", is_entity_id=True)
    mock_name: str = AirweaveField(..., description="Entity name", is_name=True)


class MockDeletionEntity(DeletionEntity):
    """Mock deletion entity."""

    deletes_entity_class: ClassVar[Optional[Type[BaseEntity]]] = MockEntity
    deletion_id: str = AirweaveField(..., description="Deletion ID", is_entity_id=True)
    deletion_name: str = AirweaveField(..., description="Deletion name", is_name=True)


class MockPolymorphicEntity(PolymorphicEntity):
    """Mock polymorphic entity for table-based entities."""

    table_name: str = "test_table"


@dataclass
class MockDbEntity:
    """Mock database entity for testing."""

    id: UUID
    entity_id: str
    entity_definition_id: UUID
    hash: str


class MockLogger:
    """Mock logger for testing."""

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass


class MockSync:
    """Mock sync object."""

    def __init__(self, sync_id: Optional[UUID] = None):
        self.id = sync_id or uuid4()


class MockSyncContext:
    """Mock sync context for testing."""

    def __init__(
        self,
        sync_id: Optional[UUID] = None,
        collection_id: Optional[UUID] = None,
        execution_config: Optional[SyncConfig] = None,
    ):
        self.sync = MockSync(sync_id)
        self.collection_id = collection_id or uuid4()
        self.execution_config = execution_config
        self.logger = MockLogger()


def create_mock_entity(ent_id: str, hash_value: str) -> MockEntity:
    """Create a MockEntity with system metadata and hash set."""
    entity = MockEntity(
        mock_id=ent_id,
        mock_name=f"Entity {ent_id}",
        breadcrumbs=[],
    )
    # Manually set entity_id since the validator copies from flagged field
    entity.entity_id = ent_id
    entity.airweave_system_metadata = AirweaveSystemMetadata(hash=hash_value)
    return entity


def create_mock_entity2(ent_id: str, hash_value: str) -> MockEntity2:
    """Create a MockEntity2 with system metadata and hash set."""
    entity = MockEntity2(
        mock_id=ent_id,
        mock_name=f"Entity {ent_id}",
        breadcrumbs=[],
    )
    # Manually set entity_id since the validator copies from flagged field
    entity.entity_id = ent_id
    entity.airweave_system_metadata = AirweaveSystemMetadata(hash=hash_value)
    return entity


def create_deletion_entity(
    ent_id: str,
    deletion_status: str = "removed",
) -> MockDeletionEntity:
    """Create a deletion entity for testing."""
    entity = MockDeletionEntity(
        deletion_id=ent_id,
        deletion_name=f"Deleted {ent_id}",
        deletion_status=deletion_status,
        breadcrumbs=[],
    )
    # Manually set entity_id since the validator copies from flagged field
    entity.entity_id = ent_id
    entity.airweave_system_metadata = AirweaveSystemMetadata()
    return entity


def create_polymorphic_entity(ent_id: str, hash_value: str) -> MockPolymorphicEntity:
    """Create a polymorphic entity for testing."""
    entity = MockPolymorphicEntity(
        table_name="test_table",
        entity_id=ent_id,
        name=f"PolyEntity {ent_id}",
        breadcrumbs=[],
    )
    entity.airweave_system_metadata = AirweaveSystemMetadata(hash=hash_value)
    return entity


# =============================================================================
# Test Classes
# =============================================================================


class TestEntityActionResolverInit:
    """Test EntityActionResolver initialization."""

    def test_init_with_entity_map(self):
        """Test resolver initializes with entity map."""
        entity_map = {MockEntity: uuid4(), MockEntity2: uuid4()}
        resolver = EntityActionResolver(entity_map)
        assert resolver.entity_map == entity_map

    def test_init_with_empty_map(self):
        """Test resolver can initialize with empty map."""
        resolver = EntityActionResolver({})
        assert resolver.entity_map == {}


class TestResolveEntityDefinitionId:
    """Test resolve_entity_definition_id method."""

    def test_resolves_regular_entity(self):
        """Test resolution of a regular entity."""
        entity_def_id = uuid4()
        entity_map = {MockEntity: entity_def_id}
        resolver = EntityActionResolver(entity_map)

        entity = create_mock_entity("test-1", "hash1")
        result = resolver.resolve_entity_definition_id(entity)

        assert result == entity_def_id

    def test_resolves_deletion_entity_to_target_class(self):
        """Test deletion entity resolves to its target class definition."""
        target_def_id = uuid4()
        entity_map = {MockEntity: target_def_id}
        resolver = EntityActionResolver(entity_map)

        deletion = create_deletion_entity("del-1", "removed")
        result = resolver.resolve_entity_definition_id(deletion)

        assert result == target_def_id

    def test_resolves_polymorphic_entity_to_reserved_id(self):
        """Test polymorphic entity resolves to reserved table entity ID."""
        from airweave.core.constants.reserved_ids import RESERVED_TABLE_ENTITY_ID

        resolver = EntityActionResolver({})

        entity = create_polymorphic_entity("poly-1", "hash1")
        result = resolver.resolve_entity_definition_id(entity)

        assert result == RESERVED_TABLE_ENTITY_ID

    def test_returns_none_for_unknown_entity(self):
        """Test returns None for entity not in map."""
        resolver = EntityActionResolver({MockEntity2: uuid4()})

        entity = create_mock_entity("test-1", "hash1")
        result = resolver.resolve_entity_definition_id(entity)

        assert result is None


class TestSeparateDeletions:
    """Test _separate_deletions method."""

    def test_separates_deletions_from_non_deletions(self):
        """Test separation of deletion entities."""
        entity_map = {MockEntity: uuid4()}
        resolver = EntityActionResolver(entity_map)

        regular = create_mock_entity("reg-1", "hash1")
        deletion = create_deletion_entity("del-1", "removed")

        delete_entities, non_delete_entities = resolver._separate_deletions(
            [regular, deletion]
        )

        assert len(delete_entities) == 1
        assert len(non_delete_entities) == 1
        assert deletion in delete_entities
        assert regular in non_delete_entities

    def test_active_deletion_entity_goes_to_non_delete(self):
        """Test deletion entity with active status goes to non-delete."""
        entity_map = {MockEntity: uuid4()}
        resolver = EntityActionResolver(entity_map)

        # Active deletion entity (not removed)
        active_deletion = create_deletion_entity("active-1", "active")
        active_deletion.airweave_system_metadata = AirweaveSystemMetadata(hash="hash1")

        delete_entities, non_delete_entities = resolver._separate_deletions(
            [active_deletion]
        )

        assert len(delete_entities) == 0
        assert len(non_delete_entities) == 1

    def test_empty_list_returns_empty(self):
        """Test empty input returns empty lists."""
        resolver = EntityActionResolver({})
        delete_entities, non_delete_entities = resolver._separate_deletions([])

        assert delete_entities == []
        assert non_delete_entities == []


class TestBuildEntityRequests:
    """Test _build_entity_requests method."""

    def test_builds_requests_for_entities(self):
        """Test building entity requests."""
        def_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)
        ctx = MockSyncContext()

        entity = create_mock_entity("test-1", "hash1")
        requests = resolver._build_entity_requests([entity], ctx)

        assert len(requests) == 1
        assert requests[0] == ("test-1", def_id)

    def test_raises_for_unknown_entity_type(self):
        """Test raises SyncFailureError for unknown entity type."""
        resolver = EntityActionResolver({})
        ctx = MockSyncContext()

        entity = create_mock_entity("test-1", "hash1")

        with pytest.raises(SyncFailureError, match="not in entity_map"):
            resolver._build_entity_requests([entity], ctx)


class TestResolveNonDeleteAction:
    """Test _resolve_non_delete_action method."""

    def test_returns_insert_for_new_entity(self):
        """Test INSERT action for entity not in database."""
        def_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)
        ctx = MockSyncContext()

        entity = create_mock_entity("test-1", "hash1")
        existing_map = {}  # Empty - entity doesn't exist

        action = resolver._resolve_non_delete_action(entity, existing_map, ctx)

        assert isinstance(action, EntityInsertAction)
        assert action.entity == entity
        assert action.entity_definition_id == def_id

    def test_returns_update_for_changed_hash(self):
        """Test UPDATE action when hash has changed."""
        def_id = uuid4()
        db_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)
        ctx = MockSyncContext()

        entity = create_mock_entity("test-1", "new_hash")
        existing_map = {
            ("test-1", def_id): MockDbEntity(
                id=db_id,
                entity_id="test-1",
                entity_definition_id=def_id,
                hash="old_hash",
            )
        }

        action = resolver._resolve_non_delete_action(entity, existing_map, ctx)

        assert isinstance(action, EntityUpdateAction)
        assert action.entity == entity
        assert action.db_id == db_id

    def test_returns_keep_for_unchanged_hash(self):
        """Test KEEP action when hash is unchanged."""
        def_id = uuid4()
        db_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)
        ctx = MockSyncContext()

        entity = create_mock_entity("test-1", "same_hash")
        existing_map = {
            ("test-1", def_id): MockDbEntity(
                id=db_id,
                entity_id="test-1",
                entity_definition_id=def_id,
                hash="same_hash",
            )
        }

        action = resolver._resolve_non_delete_action(entity, existing_map, ctx)

        assert isinstance(action, EntityKeepAction)
        assert action.entity == entity

    def test_raises_for_missing_hash(self):
        """Test raises SyncFailureError when entity has no hash."""
        def_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)
        ctx = MockSyncContext()

        entity = MockEntity(mock_id="test-1", mock_name="Test", breadcrumbs=[])
        entity.entity_id = "test-1"
        entity.airweave_system_metadata = None  # No metadata

        with pytest.raises(SyncFailureError, match="has no hash"):
            resolver._resolve_non_delete_action(entity, {}, ctx)


class TestCreateDeleteAction:
    """Test _create_delete_action method."""

    def test_creates_delete_with_db_id_when_exists(self):
        """Test delete action includes db_id when entity exists."""
        def_id = uuid4()
        db_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)
        ctx = MockSyncContext()

        deletion = create_deletion_entity("test-1", "removed")
        existing_map = {
            ("test-1", def_id): MockDbEntity(
                id=db_id,
                entity_id="test-1",
                entity_definition_id=def_id,
                hash="hash1",
            )
        }

        action = resolver._create_delete_action(deletion, existing_map, ctx)

        assert isinstance(action, EntityDeleteAction)
        assert action.entity == deletion
        assert action.db_id == db_id

    def test_creates_delete_without_db_id_when_not_exists(self):
        """Test delete action has None db_id when entity never synced."""
        def_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)
        ctx = MockSyncContext()

        deletion = create_deletion_entity("test-1", "removed")
        existing_map = {}  # Entity never existed

        action = resolver._create_delete_action(deletion, existing_map, ctx)

        assert isinstance(action, EntityDeleteAction)
        assert action.db_id is None


class TestForceAllInserts:
    """Test _force_all_inserts method."""

    def test_forces_all_as_inserts(self):
        """Test all non-deletion entities become inserts."""
        def_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)
        ctx = MockSyncContext()

        entity1 = create_mock_entity("test-1", "hash1")
        entity2 = create_mock_entity("test-2", "hash2")

        batch = resolver._force_all_inserts([entity1, entity2], ctx)

        assert len(batch.inserts) == 2
        assert len(batch.updates) == 0
        assert len(batch.keeps) == 0
        assert len(batch.deletes) == 0

    def test_keeps_deletions_as_deletes(self):
        """Test deletion entities remain as deletes."""
        def_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)
        ctx = MockSyncContext()

        entity = create_mock_entity("test-1", "hash1")
        deletion = create_deletion_entity("del-1", "removed")

        batch = resolver._force_all_inserts([entity, deletion], ctx)

        assert len(batch.inserts) == 1
        assert len(batch.deletes) == 1


class TestCreateActions:
    """Test _create_actions method."""

    def test_creates_batch_with_all_action_types(self):
        """Test creating a batch with inserts, updates, keeps, and deletes."""
        def_id = uuid4()
        db_id_update = uuid4()
        db_id_keep = uuid4()
        db_id_delete = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)
        ctx = MockSyncContext()

        # New entity -> INSERT
        new_entity = create_mock_entity("new-1", "hash_new")
        # Updated entity -> UPDATE
        updated_entity = create_mock_entity("updated-1", "hash_updated")
        # Unchanged entity -> KEEP
        unchanged_entity = create_mock_entity("unchanged-1", "hash_same")
        # Deleted entity -> DELETE
        deleted_entity = create_deletion_entity("deleted-1", "removed")

        existing_map = {
            ("updated-1", def_id): MockDbEntity(
                id=db_id_update,
                entity_id="updated-1",
                entity_definition_id=def_id,
                hash="hash_old",
            ),
            ("unchanged-1", def_id): MockDbEntity(
                id=db_id_keep,
                entity_id="unchanged-1",
                entity_definition_id=def_id,
                hash="hash_same",
            ),
            ("deleted-1", def_id): MockDbEntity(
                id=db_id_delete,
                entity_id="deleted-1",
                entity_definition_id=def_id,
                hash="hash_deleted",
            ),
        }

        batch = resolver._create_actions(
            non_delete_entities=[new_entity, updated_entity, unchanged_entity],
            delete_entities=[deleted_entity],
            existing_map=existing_map,
            sync_context=ctx,
        )

        assert len(batch.inserts) == 1
        assert len(batch.updates) == 1
        assert len(batch.keeps) == 1
        assert len(batch.deletes) == 1


class TestFetchExistingEntities:
    """Test _fetch_existing_entities method."""

    @pytest.mark.asyncio
    async def test_uses_sync_level_dedup_by_default(self):
        """Test uses sync-level dedup when collection dedup not enabled."""
        def_id = uuid4()
        sync_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)
        ctx = MockSyncContext(sync_id=sync_id, execution_config=None)

        mock_result = {}

        with patch("airweave.platform.sync.actions.entity.resolver.get_db_context") as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session

            with patch("airweave.platform.sync.actions.entity.resolver.crud") as mock_crud:
                mock_crud.entity.bulk_get_by_entity_sync_and_definition = AsyncMock(
                    return_value=mock_result
                )

                result = await resolver._fetch_existing_entities(
                    [("test-1", def_id)], ctx
                )

                mock_crud.entity.bulk_get_by_entity_sync_and_definition.assert_called_once()
                assert result == mock_result

    @pytest.mark.asyncio
    async def test_uses_collection_level_dedup_when_enabled(self):
        """Test uses collection-level dedup when config flag is enabled."""
        def_id = uuid4()
        collection_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)

        config = SyncConfig(behavior=BehaviorConfig(dedupe_by_collection=True))
        ctx = MockSyncContext(collection_id=collection_id, execution_config=config)

        mock_result = {}

        with patch("airweave.platform.sync.actions.entity.resolver.get_db_context") as mock_db:
            mock_session = AsyncMock()
            mock_db.return_value.__aenter__.return_value = mock_session

            with patch("airweave.platform.sync.actions.entity.resolver.crud") as mock_crud:
                mock_crud.entity.bulk_get_by_entity_collection_and_definition = AsyncMock(
                    return_value=mock_result
                )

                result = await resolver._fetch_existing_entities(
                    [("test-1", def_id)], ctx
                )

                mock_crud.entity.bulk_get_by_entity_collection_and_definition.assert_called_once()
                assert result == mock_result

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_requests(self):
        """Test returns empty dict for empty entity requests."""
        resolver = EntityActionResolver({})
        ctx = MockSyncContext()

        result = await resolver._fetch_existing_entities([], ctx)

        assert result == {}


class TestResolve:
    """Test the main resolve method."""

    @pytest.mark.asyncio
    async def test_resolve_with_skip_hash_comparison(self):
        """Test resolve forces all inserts when skip_hash_comparison is enabled."""
        def_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)

        config = SyncConfig(behavior=BehaviorConfig(skip_hash_comparison=True))
        ctx = MockSyncContext(execution_config=config)

        entity = create_mock_entity("test-1", "hash1")

        batch = await resolver.resolve([entity], ctx)

        assert len(batch.inserts) == 1
        assert len(batch.updates) == 0
        assert len(batch.keeps) == 0

    @pytest.mark.asyncio
    async def test_resolve_full_flow(self):
        """Test full resolve flow with database lookup."""
        def_id = uuid4()
        db_id = uuid4()
        entity_map = {MockEntity: def_id}
        resolver = EntityActionResolver(entity_map)
        ctx = MockSyncContext(execution_config=None)

        # Create entities
        new_entity = create_mock_entity("new-1", "hash_new")
        existing_entity = create_mock_entity("existing-1", "same_hash")

        # Mock database lookup
        mock_existing_map = {
            ("existing-1", def_id): MockDbEntity(
                id=db_id,
                entity_id="existing-1",
                entity_definition_id=def_id,
                hash="same_hash",  # Same hash = KEEP
            )
        }

        with patch.object(
            resolver,
            "_fetch_existing_entities",
            new=AsyncMock(return_value=mock_existing_map),
        ):
            batch = await resolver.resolve([new_entity, existing_entity], ctx)

        assert len(batch.inserts) == 1  # new_entity
        assert len(batch.keeps) == 1  # existing_entity (same hash)
        assert len(batch.updates) == 0
        assert len(batch.deletes) == 0


class TestEntityActionBatch:
    """Test EntityActionBatch helper methods."""

    def test_has_mutations_true(self):
        """Test has_mutations returns True when mutations exist."""
        batch = EntityActionBatch(
            inserts=[MagicMock()],
            updates=[],
            deletes=[],
            keeps=[],
        )
        assert batch.has_mutations is True

    def test_has_mutations_false(self):
        """Test has_mutations returns False for keeps only."""
        batch = EntityActionBatch(
            inserts=[],
            updates=[],
            deletes=[],
            keeps=[MagicMock()],
        )
        assert batch.has_mutations is False

    def test_mutation_count(self):
        """Test mutation_count calculation."""
        batch = EntityActionBatch(
            inserts=[MagicMock(), MagicMock()],
            updates=[MagicMock()],
            deletes=[MagicMock()],
            keeps=[MagicMock(), MagicMock(), MagicMock()],
        )
        assert batch.mutation_count == 4

    def test_total_count(self):
        """Test total_count includes keeps."""
        batch = EntityActionBatch(
            inserts=[MagicMock()],
            updates=[MagicMock()],
            deletes=[MagicMock()],
            keeps=[MagicMock(), MagicMock()],
        )
        assert batch.total_count == 5

    def test_summary(self):
        """Test summary string generation."""
        batch = EntityActionBatch(
            inserts=[MagicMock(), MagicMock()],
            updates=[MagicMock()],
            deletes=[],
            keeps=[MagicMock()],
        )
        summary = batch.summary()
        assert "2 inserts" in summary
        assert "1 updates" in summary
        assert "1 keeps" in summary
        assert "deletes" not in summary

    def test_summary_empty(self):
        """Test summary for empty batch."""
        batch = EntityActionBatch()
        assert batch.summary() == "empty"
