"""Entity repository wrapping crud.entity for sync pipeline usage."""

from typing import Dict, List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.models.entity import Entity


class EntityRepository:
    """Delegates to the crud.entity singleton."""

    async def get_by_sync_id(self, db: AsyncSession, sync_id: UUID) -> List[Entity]:
        """Get all entities for a specific sync."""
        return await crud.entity.get_by_sync_id(db, sync_id)

    async def bulk_get_by_entity_sync_and_definition(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        entity_requests: list[Tuple[str, str]],
    ) -> Dict[Tuple[str, str], Entity]:
        """Bulk-fetch entities by (entity_id, definition_short_name)."""
        return await crud.entity.bulk_get_by_entity_sync_and_definition(
            db, sync_id=sync_id, entity_requests=entity_requests
        )
