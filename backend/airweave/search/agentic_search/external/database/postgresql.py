"""PostgreSQL database integration for agentic search."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.models.entity_count import EntityCount as EntityCountModel
from airweave.models.entity_definition import EntityDefinition as EntityDefinitionModel
from airweave.search.agentic_search.schemas import (
    AgenticSearchCollection,
    AgenticSearchEntityCount,
    AgenticSearchEntityDefinition,
    AgenticSearchSource,
    AgenticSearchSourceConnection,
)


class PostgreSQLAgenticSearchDatabase:
    """PostgreSQL implementation of AgenticSearchDatabaseInterface.

    Maps from SQLAlchemy models to agentic_search-specific schemas.
    """

    def __init__(self, session: AsyncSession, ctx: ApiContext):
        """Initialize with session and context.

        Args:
            session: SQLAlchemy async session
            ctx: API context for organization/user scoping
        """
        self._session = session
        self._ctx = ctx

    @classmethod
    async def create(cls, ctx: ApiContext) -> "PostgreSQLAgenticSearchDatabase":
        """Create instance with its own database connection."""
        from airweave.db.session import AsyncSessionLocal

        # Create session - caller is responsible for calling close()
        session = AsyncSessionLocal()
        return cls(session, ctx)

    async def close(self) -> None:
        """Close the database session."""
        try:
            await self._session.close()
        except Exception:
            # Connection may have been closed by server due to idle timeout
            pass

    async def get_collection_by_readable_id(self, readable_id: str) -> AgenticSearchCollection:
        """Get collection by readable_id."""
        collection = await crud.collection.get_by_readable_id(
            self._session,
            readable_id=readable_id,
            ctx=self._ctx,
        )
        if not collection:
            raise ValueError(f"Collection not found: {readable_id}")
        if collection.vector_size is None:
            raise ValueError(
                f"Collection '{readable_id}' has no vector_size set. "
                "This should be configured at collection creation time."
            )
        return AgenticSearchCollection(
            id=collection.id,
            readable_id=collection.readable_id,
            vector_size=collection.vector_size,
        )

    async def get_source_connections_in_collection(
        self, collection: AgenticSearchCollection
    ) -> list[AgenticSearchSourceConnection]:
        """Get source connections in a collection."""
        source_connections = await crud.source_connection.get_for_collection(
            self._session,
            readable_collection_id=collection.readable_id,
            ctx=self._ctx,
        )
        if not source_connections:
            raise ValueError(
                f"No source connections found for collection: {collection.readable_id}"
            )
        return [
            AgenticSearchSourceConnection(
                short_name=sc.short_name,
                sync_id=sc.sync_id,
            )
            for sc in source_connections
        ]

    async def get_source_by_short_name(self, short_name: str) -> AgenticSearchSource:
        """Get source definition by short_name."""
        source = await crud.source.get_by_short_name(
            self._session,
            short_name=short_name,
        )
        if not source:
            raise ValueError(f"Source not found: {short_name}")
        return AgenticSearchSource(
            short_name=source.short_name,
            output_entity_definitions=source.output_entity_definitions or [],
        )

    async def get_entity_definitions_of_source(
        self, source: AgenticSearchSource
    ) -> list[AgenticSearchEntityDefinition]:
        """Get entity definitions for a source."""
        if not source.output_entity_definitions:
            raise ValueError(f"Source '{source.short_name}' has no output entity definitions")

        result = await self._session.execute(
            select(EntityDefinitionModel).where(
                EntityDefinitionModel.name.in_(source.output_entity_definitions)
            )
        )
        models = result.scalars().all()

        if not models:
            raise ValueError(
                f"No entity definitions found for source '{source.short_name}' "
                f"(expected names: {source.output_entity_definitions})"
            )

        return [
            AgenticSearchEntityDefinition(
                id=m.id,
                name=m.name,
                entity_schema=m.entity_schema or {},
            )
            for m in models
        ]

    async def get_entity_type_count_of_source_connection(
        self,
        source_connection: AgenticSearchSourceConnection,
        entity_definition: AgenticSearchEntityDefinition,
    ) -> AgenticSearchEntityCount:
        """Get entity count for a source connection and entity definition."""
        if not source_connection.sync_id:
            # No sync yet, return zero count
            return AgenticSearchEntityCount(count=0)

        result = await self._session.execute(
            select(EntityCountModel).where(
                EntityCountModel.sync_id == source_connection.sync_id,
                EntityCountModel.entity_definition_id == entity_definition.id,
            )
        )
        model = result.scalar_one_or_none()

        if model:
            return AgenticSearchEntityCount(count=model.count)

        # Return zero count if not found
        return AgenticSearchEntityCount(count=0)

    async def get_collection_vector_size(self, readable_id: str) -> int:
        """Get vector size for a collection.

        Args:
            readable_id: The collection's readable identifier.

        Returns:
            The vector size (embedding dimension) for the collection.

        Raises:
            ValueError: If collection not found or has no vector_size.
        """
        collection = await crud.collection.get_by_readable_id(
            self._session,
            readable_id=readable_id,
            ctx=self._ctx,
        )
        if not collection:
            raise ValueError(f"Collection not found: {readable_id}")
        if collection.vector_size is None:
            raise ValueError(
                f"Collection '{readable_id}' has no vector_size set. "
                "This should be configured at collection creation time."
            )
        return collection.vector_size
