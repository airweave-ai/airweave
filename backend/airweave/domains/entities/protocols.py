"""Protocols for the entities domain."""

from typing import Dict, List, Protocol, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

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
    """Entity read access used by the sync pipeline."""

    async def get_by_sync_id(self, db: AsyncSession, sync_id: UUID) -> List[Entity]:
        """Get all entities for a specific sync."""
        ...

    async def bulk_get_by_entity_sync_and_definition(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        entity_requests: list[Tuple[str, str]],
    ) -> Dict[Tuple[str, str], Entity]:
        """Bulk-fetch entities by (entity_id, entity_definition_short_name) for a sync."""
        ...
