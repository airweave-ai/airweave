"""CRUD operations for entities."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.entity import Entity
from airweave.schemas.entity import EntityCreate, EntityUpdate


class CRUDEntity(CRUDBaseOrganization[Entity, EntityCreate, EntityUpdate]):
    """CRUD operations for entities."""

    async def get_by_entity_and_sync_id(
        self,
        db: AsyncSession,
        entity_id: str,
        sync_id: UUID,
    ) -> Optional[Entity]:
        """Get a entity by entity id and sync id."""
        stmt = select(Entity).where(Entity.entity_id == entity_id, Entity.sync_id == sync_id)
        result = await db.execute(stmt)
        return result.unique().scalars().one_or_none()

    async def update_job_id(
        self,
        db: AsyncSession,
        *,
        db_obj: Entity,
        sync_job_id: UUID,
    ) -> Entity:
        """Update sync job ID only."""
        update_data = EntityUpdate(sync_job_id=sync_job_id, modified_at=datetime.now(datetime.UTC))

        # Use model_dump(exclude_unset=True) to only include fields we explicitly set
        return await super().update(
            db, db_obj=db_obj, obj_in=update_data.model_dump(exclude_unset=True)
        )

    async def get_all_outdated(
        self,
        db: AsyncSession,
        sync_id: UUID,
        sync_job_id: UUID,
    ) -> list[Entity]:
        """Get all entities that are outdated."""
        stmt = select(Entity).where(Entity.sync_id == sync_id, Entity.sync_job_id != sync_job_id)
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_by_sync_job(
        self,
        db: AsyncSession,
        sync_job_id: UUID,
    ) -> list[Entity]:
        """Get all entities for a specific sync job."""
        stmt = select(Entity).where(Entity.sync_job_id == sync_job_id)
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())

    async def anti_get_by_sync_job(
        self,
        db: AsyncSession,
        sync_job_id: UUID,
    ) -> list[Entity]:
        """Get all entities for that are not from a specific sync job."""
        stmt = select(Entity).where(Entity.sync_job_id != sync_job_id)
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())

    async def get_count_by_sync_id(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> int | None:
        """Get the count of entities for a specific sync."""
        stmt = select(func.count()).where(Entity.sync_id == sync_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


entity = CRUDEntity(Entity)
