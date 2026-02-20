"""Service for source connections."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.domains.auth_provider.protocols import AuthProviderRegistryProtocol
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.source_connections.protocols import (
    ResponseBuilderProtocol,
    SourceConnectionRepositoryProtocol,
    SourceConnectionServiceProtocol,
)
from airweave.domains.sources.protocols import SourceRegistryProtocol
from airweave.models.source_connection import SourceConnection
from airweave.schemas.source_connection import (
    SourceConnectionListItem,
)


class SourceConnectionService(SourceConnectionServiceProtocol):
    """Service for source connections."""

    def __init__(
        self,
        # Repositories
        sc_repo: SourceConnectionRepositoryProtocol,
        # To be implemented
        collection_repo: CollectionRepositoryProtocol,
        connection_repo: ConnectionRepositoryProtocol,
        # Registries
        source_registry: SourceRegistryProtocol,
        auth_provider_registry: AuthProviderRegistryProtocol,
        # Helpers
        response_builder: ResponseBuilderProtocol,
    ):
        self.sc_repo = sc_repo
        self.collection_repo = collection_repo
        self.connection_repo = connection_repo
        self.source_registry = source_registry
        self.auth_provider_registry = auth_provider_registry
        self.response_builder = response_builder

    async def get(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> SourceConnection:
        """Get a source connection by ID."""
        source_connection = await self.sc_repo.get(db, id=id, ctx=ctx)
        if not source_connection:
            raise NotFoundException("Source connection not found")

        return await self.response_builder.build_response(db, source_connection, ctx)

    async def list(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        readable_collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnectionListItem]:
        """List source connections with complete stats."""
        connections_with_stats = await self.sc_repo.get_multi_with_stats(
            db, ctx=ctx, collection_id=readable_collection_id, skip=skip, limit=limit
        )

        result = []
        for stats in connections_with_stats:
            last_job = stats.last_job
            last_job_status = last_job.status if last_job else None

            result.append(
                SourceConnectionListItem(
                    id=stats.id,
                    name=stats.name,
                    short_name=stats.short_name,
                    readable_collection_id=stats.readable_collection_id,
                    created_at=stats.created_at,
                    modified_at=stats.modified_at,
                    is_authenticated=stats.is_authenticated,
                    authentication_method=stats.authentication_method,
                    entity_count=stats.entity_count,
                    federated_search=stats.federated_search,
                    is_active=stats.is_active,
                    last_job_status=last_job_status,
                )
            )

        return result
