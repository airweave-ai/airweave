"""Database interface for spotlight search."""

from typing import Protocol

from airweave.schemas.collection import Collection
from airweave.schemas.entity_count import EntityCount
from airweave.schemas.entity_definition import EntityDefinition
from airweave.schemas.source import Source
from airweave.schemas.source_connection import SourceConnection


class SpotlightDatabaseInterface(Protocol):
    """Database interface for spotlight search.

    This protocol defines the database operations required by the spotlight
    search agent. Implement this interface for your specific database backend.

    Each method returns an existing schema - the transformation into spotlight-specific
    schemas (like SpotlightCollectionMetadata) is done by the builder functions.
    """

    async def get_collection_by_readable_id(self, readable_id: str) -> Collection:
        """Get collection by readable_id."""
        ...

    async def get_source_connections_in_collection(
        self, collection: Collection
    ) -> list[SourceConnection]:
        """Get source connections in a collection."""
        ...

    async def get_source_by_short_name(self, short_name: str) -> Source:
        """Get source definition by short_name."""
        ...

    async def get_entity_definitions_of_source(self, source: Source) -> list[EntityDefinition]:
        """Get entity definitions for a source (from output_entity_definition_ids)."""
        ...

    async def get_entity_type_count_of_source_connection(
        self, source_connection: SourceConnection, entity_definition: EntityDefinition
    ) -> EntityCount:
        """Get entity count for a source connection and entity definition."""
        ...
