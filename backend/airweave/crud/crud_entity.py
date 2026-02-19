"""CRUD operations for entities."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.core.context import BaseContext
from airweave.core.exceptions import NotFoundException
from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.db.unit_of_work import UnitOfWork
from airweave.models.entity import Entity
from airweave.schemas.entity import EntityCreate, EntityUpdate


class CRUDEntity(CRUDBaseOrganization[Entity, EntityCreate, EntityUpdate]):
    """CRUD operations for entities."""

    def __init__(self):
        """Initialize the CRUD object.

        Initialize with track_user=False since Entity model doesn't have user tracking fields.
        """
        super().__init__(Entity, track_user=False)

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: EntityCreate,
        ctx: BaseContext,
        uow: Optional["UnitOfWork"] = None,
        skip_validation: bool = False,
    ) -> Entity:
        """Create an entity with conflict resolution.

        Uses INSERT ... ON CONFLICT DO UPDATE to handle duplicate (sync_id, entity_id) pairs.
        This prevents deadlocks when multiple workers try to insert the same entity.

        Args:
            db: Database session
            obj_in: Entity data to create
            ctx: API context with organization info
            uow: Optional unit of work for transaction control
            skip_validation: Whether to skip validation

        Returns:
            The created or updated entity
        """
        if not skip_validation:
            # Validate auth context has org access
            await self._validate_organization_access(ctx, ctx.organization.id)

        if not isinstance(obj_in, dict):
            obj_in_dict = obj_in.model_dump(exclude_unset=True)
        else:
            obj_in_dict = obj_in

        obj_in_dict["organization_id"] = ctx.organization.id

        # Ensure we have timestamps
        if "created_at" not in obj_in_dict:
            obj_in_dict["created_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        if "modified_at" not in obj_in_dict:
            obj_in_dict["modified_at"] = datetime.now(timezone.utc).replace(tzinfo=None)

        # Use PostgreSQL's INSERT ... ON CONFLICT DO UPDATE
        stmt = insert(Entity).values(**obj_in_dict)

        # On conflict, update the existing row with the new data
        stmt = stmt.on_conflict_do_update(
            index_elements=["sync_id", "entity_id", "entity_definition_id"],
            set_={
                "sync_job_id": stmt.excluded.sync_job_id,
                "hash": stmt.excluded.hash,
                "modified_at": stmt.excluded.modified_at,
            },
        ).returning(Entity)

        # Execute the upsert
        result = await db.execute(stmt)
        db_obj = result.scalar_one()

        # Add to session for tracking
        db.add(db_obj)

        if not uow:
            await db.commit()
            await db.refresh(db_obj)

        return db_obj

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

    async def bulk_get_by_entity_and_sync(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        entity_ids: list[str],
    ) -> dict[str, Entity]:
        """Get many entities by (entity_id, sync_id) in a single query.

        Returns a mapping of entity_id -> Entity. Missing ids are simply absent.

        WARNING: If multiple entity types share the same entity_id, only one will be returned.
        Use bulk_get_by_entity_sync_and_definition() for multi-type scenarios.
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

    async def bulk_get_by_entity_sync_and_definition(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        entity_requests: list[tuple[str, UUID]],
    ) -> dict[tuple[str, UUID], Entity]:
        """Get many entities by (entity_id, sync_id, entity_definition_id).

        This method handles multi-type entities correctly by including entity_definition_id
        in the lookup. For example, GoogleCalendarList and GoogleCalendarCalendar can both
        use "daan@airweave.ai" as entity_id, but they'll have different entity_definition_ids.

        For large datasets (>1000 entities), this method chunks requests to avoid
        database timeouts from massive OR conditions.

        Args:
            db: Database session
            sync_id: The sync ID to filter by
            entity_requests: List of (entity_id, entity_definition_id) tuples

        Returns:
            Dict mapping (entity_id, entity_definition_id) -> Entity
        """
        if not entity_requests:
            return {}

        from sqlalchemy import and_, or_

        # Chunk requests to avoid timeouts with large datasets
        CHUNK_SIZE = 1000
        result_map: dict[tuple[str, UUID], Entity] = {}

        for i in range(0, len(entity_requests), CHUNK_SIZE):
            chunk = entity_requests[i : i + CHUNK_SIZE]

            # Build OR conditions for this chunk
            conditions = [
                and_(Entity.entity_id == eid, Entity.entity_definition_id == def_id)
                for eid, def_id in chunk
            ]

            stmt = select(Entity).where(Entity.sync_id == sync_id, or_(*conditions))

            result = await db.execute(stmt)
            rows = list(result.unique().scalars().all())

            # Merge into result map with composite key to avoid collisions
            for row in rows:
                result_map[(row.entity_id, row.entity_definition_id)] = row

        return result_map

    def _get_org_id_from_context(self, ctx: BaseContext) -> UUID | None:
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
        ctx: BaseContext,
    ) -> list[Entity]:
        """Create many Entity rows in a single transaction with conflict resolution.

        Uses INSERT ... ON CONFLICT DO UPDATE to handle duplicate (sync_id, entity_id) pairs.
        This prevents deadlocks when multiple workers try to insert the same entity.

        Ensures organization_id is set from the provided context.
        Caller controls commit via the session context.
        """
        if not objs:
            return []

        # HARD GUARANTEE: entity_definition_id must be present for every row
        missing_def = [
            o.entity_id for o in objs if getattr(o, "entity_definition_id", None) is None
        ]
        if missing_def:
            preview = ", ".join(missing_def[:5])
            more = f" (+{len(missing_def) - 5} more)" if len(missing_def) > 5 else ""
            raise ValueError(
                f"EntityCreate missing entity_definition_id for parent(s): {preview}{more}"
            )

        org_id = self._get_org_id_from_context(ctx)
        if org_id is None:
            raise ValueError("BaseContext must contain valid organization information")

        # Prepare data for bulk upsert
        values_list = []
        for o in objs:
            data = o.model_dump()
            data["organization_id"] = org_id
            # Ensure we have timestamps
            if "created_at" not in data:
                data["created_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
            if "modified_at" not in data:
                data["modified_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
            values_list.append(data)

        # Use PostgreSQL's INSERT ... ON CONFLICT DO UPDATE
        # This handles the unique constraint on (sync_id, entity_id, entity_definition_id)
        stmt = insert(Entity).values(values_list)

        # On conflict, update the existing row with the new data
        # This ensures we always have the latest sync_job_id and hash
        stmt = stmt.on_conflict_do_update(
            index_elements=["sync_id", "entity_id", "entity_definition_id"],
            set_={
                "sync_job_id": stmt.excluded.sync_job_id,
                "hash": stmt.excluded.hash,
                "modified_at": stmt.excluded.modified_at,
                # Keep the original organization_id to prevent cross-org updates
                # organization_id is not updated on conflict
            },
        ).returning(Entity)

        # Execute the upsert and get all affected rows
        result = await db.execute(stmt)
        entities = list(result.scalars().all())

        # Ensure the session knows about these entities
        for entity in entities:
            db.add(entity)

        await db.flush()
        return entities

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
                .values(hash=new_hash, modified_at=datetime.now(timezone.utc).replace(tzinfo=None))
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
        update_data = EntityUpdate(
            sync_job_id=sync_job_id, modified_at=datetime.now(timezone.utc).replace(tzinfo=None)
        )

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

    async def get_latest_entity_time_for_job(
        self,
        db: AsyncSession,
        sync_job_id: UUID,
    ) -> Optional[datetime]:
        """Get the most recent entity created_at timestamp for a sync job.

        Args:
            db: Database session
            sync_job_id: The sync job ID to check

        Returns:
            The most recent created_at timestamp, or None if no entities exist
        """
        stmt = select(func.max(Entity.created_at)).where(Entity.sync_job_id == sync_job_id)
        result = await db.execute(stmt)
        return result.scalar()


entity = CRUDEntity()
