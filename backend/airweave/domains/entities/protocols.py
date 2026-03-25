"""Protocols for the entities domain."""

from datetime import datetime
from typing import Dict, List, Optional, Protocol, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.context import BaseContext
from airweave.core.protocols.registry import RegistryProtocol
from airweave.domains.entities.types import EntityDefinitionEntry
from airweave.models.entity import Entity
from airweave.schemas.entity_count import EntityCountWithDefinition


class EntityDefinitionRegistryProtocol(RegistryProtocol[EntityDefinitionEntry], Protocol):
    """Entity definition registry protocol."""

    def list_for_source(self, source_short_name: str) -> list[EntityDefinitionEntry]:
        """List all entity definitions for a given source."""
        ...


class EntityCountRepositoryProtocol(Protocol):
    """Read-only access to entity count records."""

    async def get_counts_per_sync_and_type(
        self, db: AsyncSession, sync_id: UUID
    ) -> List[EntityCountWithDefinition]:
        """Get entity counts for a sync grouped by entity definition."""
        ...


class EntityRepositoryProtocol(Protocol):
    """Entity data access used by the sync pipeline."""

    async def get_by_sync_id(self, db: AsyncSession, sync_id: UUID) -> List[Entity]:
        """Get all entities for a sync."""
        ...

    async def bulk_get_by_entity_sync_and_definition(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        entity_requests: list[Tuple[str, str]],
    ) -> Dict[Tuple[str, str], Entity]:
        """Bulk-fetch entities by (entity_id, definition) pairs."""
        ...

    async def bulk_create(
        self,
        db: AsyncSession,
        *,
        objs: list,
        ctx: BaseContext,
    ) -> List[Entity]:
        """Bulk-insert entity rows."""
        ...

    async def bulk_update_hash(
        self,
        db: AsyncSession,
        *,
        rows: List[Tuple[UUID, str]],
    ) -> None:
        """Bulk-update content hashes."""
        ...

    async def bulk_remove(
        self,
        db: AsyncSession,
        *,
        ids: List[UUID],
        ctx: BaseContext,
    ) -> List[Entity]:
        """Soft-delete entities by ID."""
        ...

    async def bulk_get_by_entity_and_sync(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        entity_ids: List[str],
    ) -> Dict[str, Entity]:
        """Bulk-fetch entities by entity_id within a sync."""
        ...

    async def get_latest_entity_time_for_job(
        self,
        db: AsyncSession,
        sync_job_id: UUID,
    ) -> Optional[datetime]:
        """Get the most recent entity created_at timestamp for a sync job."""
        ...
