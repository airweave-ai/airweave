"""Tests for CollectionMetadataBuilder."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from airweave.domains.search.builders.collection_metadata import CollectionMetadataBuilder
from airweave.domains.search.types.metadata import CollectionMetadata
from airweave.schemas.entity_count import EntityCountWithDefinition


def _make_collection(readable_id: str = "test-collection"):
    """Create a mock collection."""
    collection = MagicMock()
    collection.id = uuid4()
    collection.readable_id = readable_id
    return collection


def _make_source_connection(short_name: str = "slack", sync_id=None):
    """Create a mock source connection."""
    sc = MagicMock()
    sc.short_name = short_name
    sc.sync_id = sync_id or uuid4()
    return sc


def _make_entity_definition_entry(short_name: str, name: str, schema: dict | None = None):
    """Create a mock entity definition entry."""
    entry = MagicMock()
    entry.short_name = short_name
    entry.name = name
    entry.entity_schema = schema or {
        "properties": {
            "title": {"description": "The title", "type": "string"},
            "body": {"description": "The body text", "type": "string"},
        }
    }
    return entry


def _make_entity_count(short_name: str, count: int) -> EntityCountWithDefinition:
    """Create an entity count."""
    return EntityCountWithDefinition(
        count=count,
        entity_definition_short_name=short_name,
        entity_definition_name=short_name,
        entity_definition_type="base_entity",
        modified_at=datetime(2024, 1, 1),
    )


@pytest.fixture
def builder():
    """Create a CollectionMetadataBuilder with fake dependencies."""
    collection_repo = AsyncMock()
    sc_repo = AsyncMock()
    source_registry = MagicMock()
    entity_definition_registry = MagicMock()
    entity_count_repo = AsyncMock()

    return CollectionMetadataBuilder(
        collection_repo=collection_repo,
        sc_repo=sc_repo,
        source_registry=source_registry,
        entity_definition_registry=entity_definition_registry,
        entity_count_repo=entity_count_repo,
    )


class TestCollectionMetadataBuilder:
    """Tests for CollectionMetadataBuilder."""

    @pytest.mark.asyncio
    async def test_build_basic(self, builder: CollectionMetadataBuilder) -> None:
        """Build collection metadata with one source and one entity type."""
        collection = _make_collection()
        sc = _make_source_connection("slack")
        entity_def = _make_entity_definition_entry("SlackMessageEntity", "SlackMessageEntity")
        entity_count = _make_entity_count("SlackMessageEntity", 42)

        builder._collection_repo.get_by_readable_id.return_value = collection
        builder._sc_repo.get_by_collection_ids.return_value = [sc]
        builder._entity_definition_registry.list_for_source.return_value = [entity_def]
        builder._entity_count_repo.get_counts_per_sync_and_type.return_value = [entity_count]

        db = AsyncMock()
        ctx = MagicMock()
        ctx.organization_id = uuid4()

        result = await builder.build(db, ctx, "test-collection")

        assert isinstance(result, CollectionMetadata)
        assert result.collection_readable_id == "test-collection"
        assert len(result.sources) == 1
        assert result.sources[0].short_name == "slack"
        assert len(result.sources[0].entity_types) == 1
        assert result.sources[0].entity_types[0].name == "SlackMessageEntity"
        assert result.sources[0].entity_types[0].count == 42
        assert "title" in result.sources[0].entity_types[0].fields

    @pytest.mark.asyncio
    async def test_build_collection_not_found(self, builder: CollectionMetadataBuilder) -> None:
        """Raises ValueError when collection is not found."""
        builder._collection_repo.get_by_readable_id.return_value = None

        db = AsyncMock()
        ctx = MagicMock()
        ctx.organization_id = uuid4()

        with pytest.raises(ValueError, match="Collection not found"):
            await builder.build(db, ctx, "nonexistent")

    @pytest.mark.asyncio
    async def test_build_no_source_connections(self, builder: CollectionMetadataBuilder) -> None:
        """Returns empty sources when collection has no source connections."""
        collection = _make_collection()
        builder._collection_repo.get_by_readable_id.return_value = collection
        builder._sc_repo.get_by_collection_ids.return_value = []

        db = AsyncMock()
        ctx = MagicMock()
        ctx.organization_id = uuid4()

        result = await builder.build(db, ctx, "test-collection")

        assert result.sources == []

    @pytest.mark.asyncio
    async def test_build_zero_count_entity_type(self, builder: CollectionMetadataBuilder) -> None:
        """Entity types with zero count are included (metadata still shows them)."""
        collection = _make_collection()
        sc = _make_source_connection("slack")
        entity_def = _make_entity_definition_entry("SlackMessageEntity", "SlackMessageEntity")

        builder._collection_repo.get_by_readable_id.return_value = collection
        builder._sc_repo.get_by_collection_ids.return_value = [sc]
        builder._entity_definition_registry.list_for_source.return_value = [entity_def]
        # No counts for this entity type
        builder._entity_count_repo.get_counts_per_sync_and_type.return_value = []

        db = AsyncMock()
        ctx = MagicMock()
        ctx.organization_id = uuid4()

        result = await builder.build(db, ctx, "test-collection")

        assert result.sources[0].entity_types[0].count == 0

    @pytest.mark.asyncio
    async def test_extract_fields_empty_schema(self, builder: CollectionMetadataBuilder) -> None:
        """Empty schema returns empty fields dict."""
        result = builder._extract_fields({})
        assert result == {}

    @pytest.mark.asyncio
    async def test_extract_fields_with_properties(
        self, builder: CollectionMetadataBuilder
    ) -> None:
        """Extracts field names and descriptions from properties."""
        schema = {
            "properties": {
                "name": {"description": "The name", "type": "string"},
                "count": {"description": "The count", "type": "integer"},
            }
        }
        result = builder._extract_fields(schema)
        assert result == {"name": "The name", "count": "The count"}

    def test_get_source_description_known(self, builder: CollectionMetadataBuilder) -> None:
        """Known sources return their description."""
        desc = builder._get_source_description("slack")
        assert "communication" in desc.lower()

    def test_get_source_description_unknown(self, builder: CollectionMetadataBuilder) -> None:
        """Unknown sources raise ValueError."""
        with pytest.raises(ValueError, match="No description found"):
            builder._get_source_description("unknown_source_xyz")
