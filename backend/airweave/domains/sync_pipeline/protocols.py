"""Protocols for the sync pipeline domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sync.actions.entity.types import EntityActionBatch

if TYPE_CHECKING:
    from airweave.core.context import BaseContext
    from airweave.platform.contexts import SyncContext
    from airweave.platform.contexts.runtime import SyncRuntime
    from airweave.platform.sync.config import SyncConfig
    from airweave.platform.sync.orchestrator import SyncOrchestrator


class ChunkEmbedProcessorProtocol(Protocol):
    """Chunks text and computes dense/sparse embeddings."""

    async def process(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
        runtime: SyncRuntime,
    ) -> List[BaseEntity]:
        """Chunk text and compute embeddings for entities."""
        ...


class EntityActionResolverProtocol(Protocol):
    """Resolves entities to INSERT/UPDATE/DELETE/KEEP actions."""

    async def resolve(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
    ) -> EntityActionBatch:
        """Compare entity hashes and determine needed actions."""
        ...

    def resolve_entity_definition_short_name(self, entity: BaseEntity) -> Optional[str]:
        """Return the short name for an entity's definition, if mapped."""
        ...


class EntityActionDispatcherProtocol(Protocol):
    """Dispatches resolved entity actions to handlers."""

    async def dispatch(
        self,
        batch: EntityActionBatch,
        sync_context: SyncContext,
        runtime: SyncRuntime,
    ) -> None:
        """Execute a batch of entity actions against all handlers."""
        ...

    async def dispatch_orphan_cleanup(
        self,
        orphan_entity_ids: List[str],
        sync_context: SyncContext,
    ) -> None:
        """Delete orphaned entities from all handlers."""
        ...


class EntityPipelineProtocol(Protocol):
    """Orchestrates entity processing through sync stages."""

    async def process(
        self,
        entities: List[BaseEntity],
        sync_context: SyncContext,
        runtime: SyncRuntime,
    ) -> None:
        """Process a batch of entities through the full pipeline."""
        ...

    async def cleanup_orphaned_entities(
        self, sync_context: SyncContext, runtime: SyncRuntime
    ) -> None:
        """Remove entities no longer present in the source."""
        ...

    async def cleanup_temp_files(self, sync_context: SyncContext, runtime: SyncRuntime) -> None:
        """Clean up temporary files created during the sync."""
        ...


class SyncFactoryProtocol(Protocol):
    """Builds a SyncOrchestrator for a given sync run."""

    async def create_orchestrator(
        self,
        db: AsyncSession,
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        collection: schemas.CollectionRecord,
        connection: schemas.Connection,
        ctx: BaseContext,
        force_full_sync: bool = False,
        execution_config: Optional[SyncConfig] = None,
    ) -> SyncOrchestrator:
        """Create and return a fully-wired SyncOrchestrator."""
        ...
