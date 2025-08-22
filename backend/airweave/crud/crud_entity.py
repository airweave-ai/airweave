"""CRUD operations for entities."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.exceptions import NotFoundException
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.entity import Entity
from airweave.schemas.entity import EntityCreate, EntityUpdate


class CRUDEntity(CRUDBaseOrganization[Entity, EntityCreate, EntityUpdate]):
    """CRUD operations for entities."""

    def __init__(self):
        """Initialize the CRUD object.

        Initialize with track_user=False since Entity model doesn't have user tracking fields.
        """
        super().__init__(Entity, track_user=False)

    async def get_by_entity_and_sync_id(
        self,
        db: AsyncSession,
        entity_id: str,
        sync_id: UUID,
    ) -> Optional[Entity]:
        """Get a entity by entity id and sync id."""
        stmt = select(Entity).where(Entity.entity_id == entity_id, Entity.sync_id == sync_id)
        result = await db.execute(stmt)
        db_obj = result.unique().scalars().one_or_none()
        if not db_obj:
            raise NotFoundException(
                f"Entity with entity ID {entity_id} and sync ID {sync_id} not found"
            )
        return db_obj

    async def get_by_entity_and_sync_id_many(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        entity_ids: list[str],
    ) -> dict[str, Entity]:
        """Get many entities by (entity_id, sync_id) in a single query.

        Returns a mapping of entity_id -> Entity. Missing ids are simply absent.
        """
        if not entity_ids:
            return {}
        stmt = select(Entity).where(
            Entity.sync_id == sync_id,
            Entity.entity_id.in_(entity_ids),
        )
        result = await db.execute(stmt)
        rows = list(result.unique().scalars().all())
        return {row.entity_id: row for row in rows}

    async def bulk_create(
        self,
        db: AsyncSession,
        *,
        objs: list[EntityCreate],
    ) -> list[Entity]:
        """Create many Entity rows in a single transaction.

        Uses ORM add_all + flush so primary keys are populated on return.
        Caller controls commit via the session context.
        """
        if not objs:
            return []
        models_to_add = [self.model(**o.model_dump()) for o in objs]
        db.add_all(models_to_add)
        # Ensure PKs and defaults are assigned by the DB before returning
        await db.flush()
        return models_to_add

    async def bulk_update_hash(
        self,
        db: AsyncSession,
        *,
        rows: list[tuple[UUID, str]],
    ) -> None:
        """Bulk update the 'hash' field for many entities.

        Args:
            rows: list of tuples (entity_db_id, new_hash)
        """
        if not rows:
            return
        # Execute per-row UPDATEs within the same transaction context.
        # (Can be optimized to a single CASE WHEN statement if needed.)
        for entity_db_id, new_hash in rows:
            stmt = (
                update(Entity)
                .where(Entity.id == entity_db_id)
                .values(hash=new_hash, modified_at=datetime.now(datetime.UTC))
            )
            await db.execute(stmt)
        # Caller is responsible for committing via session context

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

    async def get_by_sync_id(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> list[Entity]:
        """Get all entities for a specific sync."""
        stmt = select(Entity).where(Entity.sync_id == sync_id)
        result = await db.execute(stmt)
        return list(result.unique().scalars().all())


entity = CRUDEntity()
