"""Entity repository wrapping crud.entity for sync pipeline usage."""

from typing import Any, Dict, List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.models.entity import Entity
from airweave.schemas.entity import EntityCreate


class EntityRepository:
    """Delegates to the crud.entity singleton."""

    async def get_by_sync_id(self, db: AsyncSession, sync_id: UUID) -> List[Entity]:
        return await crud.entity.get_by_sync_id(db, sync_id)

    async def bulk_get_by_entity_sync_and_definition(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        entity_requests: list[Tuple[str, str]],
    ) -> Dict[Tuple[str, str], Entity]:
        return await crud.entity.bulk_get_by_entity_sync_and_definition(
            db, sync_id=sync_id, entity_requests=entity_requests
        )

    async def bulk_create(
        self,
        db: AsyncSession,
        *,
        objs: List[EntityCreate],
        ctx: Any,
    ) -> List[Entity]:
        return await crud.entity.bulk_create(db, objs=objs, ctx=ctx)

    async def bulk_update_hash(
        self,
        db: AsyncSession,
        *,
        rows: List[Tuple[UUID, str]],
    ) -> None:
        return await crud.entity.bulk_update_hash(db, rows=rows)

    async def bulk_remove(
        self,
        db: AsyncSession,
        *,
        ids: List[UUID],
        ctx: Any,
    ) -> List[Entity]:
        return await crud.entity.bulk_remove(db, ids=ids, ctx=ctx)

    async def bulk_get_by_entity_and_sync(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        entity_ids: List[str],
    ) -> Dict[str, Entity]:
        return await crud.entity.bulk_get_by_entity_and_sync(
            db, sync_id=sync_id, entity_ids=entity_ids
        )
