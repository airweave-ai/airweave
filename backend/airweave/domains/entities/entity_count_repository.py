"""Entity count repository wrapping crud.entity_count."""

from typing import List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.schemas.entity_count import EntityCountWithDefinition


class EntityCountRepository:
    """Delegates to the crud.entity_count singleton."""

    async def get_counts_per_sync_and_type(
        self, db: AsyncSession, sync_id: UUID
    ) -> List[EntityCountWithDefinition]:
        """Get entity counts for a sync grouped by entity definition."""
        return await crud.entity_count.get_counts_per_sync_and_type(db, sync_id)
