"""PostgreSQL database integration for agentic search."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext

# [code blue] todo: inject source_registry via Inject() instead of container access
from airweave.core import container as container_mod
from airweave.models.entity_count import EntityCount as EntityCountModel
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
        assert container_mod.container is not None  # [code blue]
        collection = await container_mod.container.collection_repo.get_by_readable_id(
            self._session,
            readable_id=readable_id,
            ctx=self._ctx,
        )
        if not collection:
            raise ValueError(f"Collection not found: {readable_id}")
        return AgenticSearchCollection(
            id=collection.id,
            readable_id=collection.readable_id,
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
        assert container_mod.container is not None
        source_registry = container_mod.container.source_registry
        try:
            entry = source_registry.get(short_name)
        except KeyError:
            raise ValueError(f"Source not found: {short_name}")
        return AgenticSearchSource(
            short_name=entry.short_name,
            output_entity_definitions=entry.output_entity_definitions or [],
        )

    async def get_entity_definitions_of_source(
        self, source: AgenticSearchSource
    ) -> list[AgenticSearchEntityDefinition]:
        """Get entity definitions for a source from the in-memory registry."""
        # [code blue] todo: remove container import
        from airweave.core.container import container as app_container

        assert app_container is not None
        entries = app_container.entity_definition_registry.list_for_source(source.short_name)

        if not entries:
            raise ValueError(f"No entity definitions found for source '{source.short_name}'")

        return [
            AgenticSearchEntityDefinition(
                short_name=entry.short_name,
                name=entry.name,
                entity_schema=entry.entity_schema or {},
            )
            for entry in entries
        ]

    async def get_entity_type_count_of_source_connection(
        self,
        source_connection: AgenticSearchSourceConnection,
        entity_definition: AgenticSearchEntityDefinition,
    ) -> AgenticSearchEntityCount:
        """Get entity count for a source connection and entity definition."""
        if not source_connection.sync_id:
            return AgenticSearchEntityCount(count=0)

        result = await self._session.execute(
            select(EntityCountModel).where(
                EntityCountModel.sync_id == source_connection.sync_id,
                EntityCountModel.entity_definition_short_name == entity_definition.short_name,
            )
        )
        model = result.scalar_one_or_none()

        if model:
            return AgenticSearchEntityCount(count=model.count)

        return AgenticSearchEntityCount(count=0)
