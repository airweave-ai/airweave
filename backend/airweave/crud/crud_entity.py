"""CRUD operations for entities."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.entity import Entity
from airweave.models.sync import Sync
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

    def _get_org_id_from_context(self, ctx: ApiContext) -> UUID | None:
        """Attempt to extract organization ID from the API context."""
        # 1) Direct attributes
        for attr in ("organization_id", "org_id"):
            if org_id := getattr(ctx, attr, None):
                return org_id

        # 2) Nested objects
        for holder_name in ("organization", "org", "tenant"):
            if holder_obj := getattr(ctx, holder_name, None):
                if org_id := getattr(holder_obj, "id", None):
                    return org_id
        return None

    async def bulk_create(
        self,
        db: AsyncSession,
        *,
        objs: list[EntityCreate],
        ctx: ApiContext | None = None,
    ) -> list[Entity]:
        """Create many Entity rows in a single transaction.

        Ensures organization_id is set. Prefer taking it from ctx; if missing,
        fall back to the Sync row referenced by the first object.
        Caller controls commit via the session context.
        """
        if not objs:
            return []

        org_id = self._get_org_id_from_context(ctx) if ctx else None

        # Fallback: resolve from Sync if ctx didn't have it
        if org_id is None:
            first_sync_id = objs[0].sync_id
            res = await db.execute(select(Sync.organization_id).where(Sync.id == first_sync_id))
            org_id = res.scalar_one_or_none()

        if org_id is None:
            raise ValueError(
                "bulk_create requires a ctx with organization_id or resolvable org via sync_id"
            )

        models_to_add: list[Entity] = []
        for o in objs:
            data = o.model_dump()
            model = self.model(organization_id=org_id, **data)
            models_to_add.append(model)

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
            db: The async database session.
            rows: list of tuples (entity_db_id, new_hash)
        """
        if not rows:
            return
        for entity_db_id, new_hash in rows:
            stmt = (
                update(Entity)
                .where(Entity.id == entity_db_id)
                .values(hash=new_hash, modified_at=datetime.now(datetime.UTC))
            )
            await db.execute(stmt)

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
