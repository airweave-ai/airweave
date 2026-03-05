"""Database interface for agentic search."""

from typing import Protocol

from airweave.search.agentic_search.schemas import (
    AgenticSearchCollection,
    AgenticSearchEntityCount,
    AgenticSearchEntityDefinition,
    AgenticSearchSource,
    AgenticSearchSourceConnection,
)


class AgenticSearchDatabaseInterface(Protocol):
    """Database interface for agentic search.

    This protocol defines the database operations required by the agentic_search
    search agent. Implement this interface for your specific database backend.

    Returns agentic_search-specific schemas with only the fields agentic_search needs.
    The adapter is responsible for mapping from the underlying data store.
    """

    async def close(self) -> None:
        """Close the database connection."""
        ...

    async def get_collection_by_readable_id(self, readable_id: str) -> AgenticSearchCollection:
        """Get collection by readable_id."""
        ...

    async def get_source_connections_in_collection(
        self, collection: AgenticSearchCollection
    ) -> list[AgenticSearchSourceConnection]:
        """Get source connections in a collection."""
        ...

    async def get_source_by_short_name(self, short_name: str) -> AgenticSearchSource:
        """Get source definition by short_name."""
        ...

    async def get_entity_definitions_of_source(
        self, source: AgenticSearchSource
    ) -> list[AgenticSearchEntityDefinition]:
        """Get entity definitions for a source (from output_entity_definitions)."""
        ...

    async def get_entity_type_count_of_source_connection(
        self,
        source_connection: AgenticSearchSourceConnection,
        entity_definition: AgenticSearchEntityDefinition,
    ) -> AgenticSearchEntityCount:
        """Get entity count for a source connection and entity definition."""
        ...
