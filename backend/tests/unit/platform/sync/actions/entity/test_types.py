"""Tests for entity action types.

Tests the action type dataclasses and EntityActionBatch.
"""

from unittest.mock import MagicMock
from uuid import uuid4

from airweave.platform.sync.actions.entity.types import (
    EntityActionBatch,
    EntityDeleteAction,
    EntityInsertAction,
    EntityKeepAction,
    EntityUpdateAction,
)


# =============================================================================
# Test Fixtures
# =============================================================================


class MockEntity:
    """Mock entity for testing."""

    def __init__(self, entity_id: str = "test-entity"):
        self.entity_id = entity_id

    @property
    def __class__(self):
        """Return a mock class with __name__."""
        return type("MockEntity", (), {"__name__": "MockEntity"})


# =============================================================================
# Test Classes
# =============================================================================


class TestEntityInsertAction:
    """Test EntityInsertAction dataclass."""

    def test_defaults(self):
        """Test default values for EntityInsertAction."""
        entity = MockEntity("test-1")
        action = EntityInsertAction(
            entity=entity,
            entity_definition_id=uuid4(),
        )

        assert action.entity == entity
        assert action.chunk_entities == []
        assert action.skip_content_handlers is False

    def test_skip_content_handlers_true(self):
        """Test skip_content_handlers can be set to True."""
        entity = MockEntity("test-1")
        action = EntityInsertAction(
            entity=entity,
            entity_definition_id=uuid4(),
            skip_content_handlers=True,
        )

        assert action.skip_content_handlers is True

    def test_entity_id_property(self):
        """Test entity_id property returns entity's id."""
        entity = MockEntity("my-entity-id")
        action = EntityInsertAction(
            entity=entity,
            entity_definition_id=uuid4(),
        )

        assert action.entity_id == "my-entity-id"

    def test_entity_type_property(self):
        """Test entity_type property returns class name."""
        entity = MockEntity("test-1")
        action = EntityInsertAction(
            entity=entity,
            entity_definition_id=uuid4(),
        )

        assert action.entity_type == "MockEntity"

    def test_with_chunk_entities(self):
        """Test EntityInsertAction with chunk entities."""
        entity = MockEntity("parent")
        chunks = [MockEntity("chunk-1"), MockEntity("chunk-2")]
        action = EntityInsertAction(
            entity=entity,
            entity_definition_id=uuid4(),
            chunk_entities=chunks,
        )

        assert len(action.chunk_entities) == 2


class TestEntityUpdateAction:
    """Test EntityUpdateAction dataclass."""

    def test_requires_db_id(self):
        """Test EntityUpdateAction requires db_id."""
        entity = MockEntity("test-1")
        db_id = uuid4()
        action = EntityUpdateAction(
            entity=entity,
            entity_definition_id=uuid4(),
            db_id=db_id,
        )

        assert action.db_id == db_id

    def test_entity_id_property(self):
        """Test entity_id property."""
        entity = MockEntity("update-entity")
        action = EntityUpdateAction(
            entity=entity,
            entity_definition_id=uuid4(),
            db_id=uuid4(),
        )

        assert action.entity_id == "update-entity"


class TestEntityDeleteAction:
    """Test EntityDeleteAction dataclass."""

    def test_db_id_optional(self):
        """Test EntityDeleteAction db_id is optional."""
        entity = MockEntity("test-1")
        action = EntityDeleteAction(
            entity=entity,
            entity_definition_id=uuid4(),
        )

        assert action.db_id is None

    def test_with_db_id(self):
        """Test EntityDeleteAction with db_id."""
        entity = MockEntity("test-1")
        db_id = uuid4()
        action = EntityDeleteAction(
            entity=entity,
            entity_definition_id=uuid4(),
            db_id=db_id,
        )

        assert action.db_id == db_id


class TestEntityKeepAction:
    """Test EntityKeepAction dataclass."""

    def test_basic_creation(self):
        """Test basic EntityKeepAction creation."""
        entity = MockEntity("keep-entity")
        def_id = uuid4()
        action = EntityKeepAction(
            entity=entity,
            entity_definition_id=def_id,
        )

        assert action.entity == entity
        assert action.entity_definition_id == def_id


class TestEntityActionBatch:
    """Test EntityActionBatch container."""

    def test_empty_batch(self):
        """Test empty batch defaults."""
        batch = EntityActionBatch()

        assert batch.inserts == []
        assert batch.updates == []
        assert batch.deletes == []
        assert batch.keeps == []
        assert batch.existing_map == {}

    def test_has_mutations_with_inserts(self):
        """Test has_mutations returns True with inserts."""
        batch = EntityActionBatch(
            inserts=[MagicMock()],
        )
        assert batch.has_mutations is True

    def test_has_mutations_with_updates(self):
        """Test has_mutations returns True with updates."""
        batch = EntityActionBatch(
            updates=[MagicMock()],
        )
        assert batch.has_mutations is True

    def test_has_mutations_with_deletes(self):
        """Test has_mutations returns True with deletes."""
        batch = EntityActionBatch(
            deletes=[MagicMock()],
        )
        assert batch.has_mutations is True

    def test_has_mutations_false_with_keeps_only(self):
        """Test has_mutations returns False with only keeps."""
        batch = EntityActionBatch(
            keeps=[MagicMock()],
        )
        assert batch.has_mutations is False

    def test_mutation_count(self):
        """Test mutation_count calculation."""
        batch = EntityActionBatch(
            inserts=[MagicMock(), MagicMock()],  # 2
            updates=[MagicMock()],  # 1
            deletes=[MagicMock(), MagicMock(), MagicMock()],  # 3
            keeps=[MagicMock()],  # not counted
        )
        assert batch.mutation_count == 6

    def test_total_count(self):
        """Test total_count includes keeps."""
        batch = EntityActionBatch(
            inserts=[MagicMock()],  # 1
            updates=[MagicMock()],  # 1
            deletes=[MagicMock()],  # 1
            keeps=[MagicMock(), MagicMock()],  # 2
        )
        assert batch.total_count == 5

    def test_summary_with_all_types(self):
        """Test summary includes all action types."""
        batch = EntityActionBatch(
            inserts=[MagicMock(), MagicMock()],
            updates=[MagicMock()],
            deletes=[MagicMock()],
            keeps=[MagicMock()],
        )
        summary = batch.summary()

        assert "2 inserts" in summary
        assert "1 updates" in summary
        assert "1 deletes" in summary
        assert "1 keeps" in summary

    def test_summary_empty(self):
        """Test summary for empty batch."""
        batch = EntityActionBatch()
        assert batch.summary() == "empty"

    def test_summary_excludes_zero_counts(self):
        """Test summary excludes action types with zero count."""
        batch = EntityActionBatch(
            inserts=[MagicMock()],
        )
        summary = batch.summary()

        assert "1 inserts" in summary
        assert "updates" not in summary
        assert "deletes" not in summary
        assert "keeps" not in summary

    def test_get_entities_to_process(self):
        """Test get_entities_to_process returns INSERT and UPDATE entities."""
        entity1 = MockEntity("insert-1")
        entity2 = MockEntity("update-1")
        entity3 = MockEntity("keep-1")

        batch = EntityActionBatch(
            inserts=[EntityInsertAction(entity=entity1, entity_definition_id=uuid4())],
            updates=[EntityUpdateAction(entity=entity2, entity_definition_id=uuid4(), db_id=uuid4())],
            keeps=[EntityKeepAction(entity=entity3, entity_definition_id=uuid4())],
        )

        entities = batch.get_entities_to_process()

        assert len(entities) == 2
        assert entity1 in entities
        assert entity2 in entities
        assert entity3 not in entities
