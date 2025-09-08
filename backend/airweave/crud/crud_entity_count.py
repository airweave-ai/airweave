"""CRUD operations for entity counts."""

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.entity_count import EntityCount
from airweave.models.entity_definition import EntityDefinition
from airweave.schemas.entity_count import (
    EntityCountCreate,
    EntityCountUpdate,
    EntityCountWithDefinition,
)


class CRUDEntityCount(CRUDBaseOrganization[EntityCount, EntityCountCreate, EntityCountUpdate]):
    """CRUD operations for entity counts."""

    pass

    async def get_counts_per_sync_and_type(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> List[EntityCountWithDefinition]:
        """Get entity counts for a sync with entity definition details.

        Args:
            db: Database session
            sync_id: ID of the sync

        Returns:
            List of EntityCountWithDefinition objects
        """
        stmt = (
            select(EntityCount, EntityDefinition)
            .join(
                EntityDefinition,
                EntityCount.entity_definition_id == EntityDefinition.id,
            )
            .where(EntityCount.sync_id == sync_id)
            .order_by(EntityDefinition.name)
        )

        result = await db.execute(stmt)
        rows = result.all()

        return [
            EntityCountWithDefinition(
                count=row.EntityCount.count,
                entity_definition_id=row.EntityCount.entity_definition_id,
                entity_definition_name=row.EntityDefinition.name,
                entity_definition_type=(
                    row.EntityDefinition.type.value
                    if hasattr(row.EntityDefinition.type, "value")
                    else row.EntityDefinition.type
                ),
                entity_definition_description=row.EntityDefinition.description,
            )
            for row in rows
        ]

    async def get_by_sync_id(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> List[EntityCount]:
        """Get all entity counts for a specific sync.

        Args:
            db: Database session
            sync_id: ID of the sync

        Returns:
            List of EntityCount objects
        """
        stmt = select(EntityCount).where(EntityCount.sync_id == sync_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_total_count_by_sync(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> int:
        """Get total entity count across all types for a sync.

        Args:
            db: Database session
            sync_id: ID of the sync

        Returns:
            Total count of all entities
        """
        from sqlalchemy import func

        stmt = select(func.sum(EntityCount.count)).where(EntityCount.sync_id == sync_id)
        result = await db.execute(stmt)
        total = result.scalar_one_or_none()
        return total or 0


entity_count = CRUDEntityCount(EntityCount, track_user=False)
