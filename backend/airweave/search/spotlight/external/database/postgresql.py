"""PostgreSQL database integration for spotlight search."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.models.entity_count import EntityCount as EntityCountModel
from airweave.models.entity_definition import EntityDefinition as EntityDefinitionModel
from airweave.schemas.collection import Collection
from airweave.schemas.entity_count import EntityCount
from airweave.schemas.entity_definition import EntityDefinition
from airweave.schemas.source import Source
from airweave.schemas.source_connection import SourceConnection


class PostgreSQLSpotlightDatabase:
    """PostgreSQL implementation of SpotlightDatabaseInterface."""

    def __init__(self, session: AsyncSession, ctx: ApiContext):
        """Initialize with session and context.

        Args:
            session: SQLAlchemy async session
            ctx: API context for organization/user scoping
        """
        self._session = session
        self._ctx = ctx

    @classmethod
    async def create(cls, ctx: ApiContext) -> "PostgreSQLSpotlightDatabase":
        """Create instance with its own database connection.

        Uses get_db_context pattern for proper session management.
        """
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

    async def get_collection_by_readable_id(self, readable_id: str) -> Collection:
        """Get collection by readable_id."""
        collection = await crud.collection.get_by_readable_id(
            self._session,
            readable_id=readable_id,
            ctx=self._ctx,
        )
        if not collection:
            raise ValueError(f"Collection not found: {readable_id}")
        return Collection.model_validate(collection)

    async def get_source_connections_in_collection(
        self, collection: Collection
    ) -> list[SourceConnection]:
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
        return [SourceConnection.model_validate(sc) for sc in source_connections]

    async def get_source_by_short_name(self, short_name: str) -> Source:
        """Get source definition by short_name."""
        source = await crud.source.get_by_short_name(
            self._session,
            short_name=short_name,
        )
        if not source:
            raise ValueError(f"Source not found: {short_name}")
        return Source.model_validate(source)

    async def get_entity_definitions_of_source(self, source: Source) -> list[EntityDefinition]:
        """Get entity definitions for a source."""
        if not source.output_entity_definition_ids:
            raise ValueError(f"Source '{source.short_name}' has no output entity definition IDs")

        result = await self._session.execute(
            select(EntityDefinitionModel).where(
                EntityDefinitionModel.id.in_(source.output_entity_definition_ids)
            )
        )
        models = result.scalars().all()

        if not models:
            raise ValueError(
                f"No entity definitions found for source '{source.short_name}' "
                f"(expected IDs: {source.output_entity_definition_ids})"
            )

        return [EntityDefinition.model_validate(m) for m in models]

    async def get_entity_type_count_of_source_connection(
        self, source_connection: SourceConnection, entity_definition: EntityDefinition
    ) -> EntityCount:
        """Get entity count for a source connection and entity definition."""
        if not source_connection.sync_id:
            # No sync yet, return zero count
            return EntityCount(
                id=UUID("00000000-0000-0000-0000-000000000000"),
                sync_id=UUID("00000000-0000-0000-0000-000000000000"),
                entity_definition_id=entity_definition.id,
                count=0,
            )

        result = await self._session.execute(
            select(EntityCountModel).where(
                EntityCountModel.sync_id == source_connection.sync_id,
                EntityCountModel.entity_definition_id == entity_definition.id,
            )
        )
        model = result.scalar_one_or_none()

        if model:
            return EntityCount.model_validate(model)

        # Return zero count if not found
        return EntityCount(
            id=UUID("00000000-0000-0000-0000-000000000000"),
            sync_id=source_connection.sync_id,
            entity_definition_id=entity_definition.id,
            count=0,
        )
