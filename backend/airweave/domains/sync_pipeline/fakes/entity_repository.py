"""Fake entity repository for testing."""

from typing import Any, Dict, List, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.models.entity import Entity


class FakeEntityRepository:
    """In-memory fake for EntityRepositoryProtocol."""

    def __init__(self) -> None:
        self._entities: List[Entity] = []

    async def get_by_sync_id(self, db: AsyncSession, sync_id: UUID) -> List[Entity]:
        return [e for e in self._entities if e.sync_id == sync_id]

    async def bulk_get_by_entity_sync_and_definition(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        entity_requests: list[Tuple[str, str]],
    ) -> Dict[Tuple[str, str], Entity]:
        return {}

    async def bulk_create(
        self, db: AsyncSession, *, objs: list, ctx: Any
    ) -> List[Entity]:
        return []

    async def bulk_update_hash(
        self, db: AsyncSession, *, rows: List[Tuple[UUID, str]]
    ) -> None:
        pass

    async def bulk_remove(
        self, db: AsyncSession, *, ids: List[UUID], ctx: Any
    ) -> List[Entity]:
        self._entities = [e for e in self._entities if e.id not in ids]
        return []

    async def bulk_get_by_entity_and_sync(
        self, db: AsyncSession, *, sync_id: UUID, entity_ids: List[str]
    ) -> Dict[str, Entity]:
        return {
            e.entity_id: e
            for e in self._entities
            if e.sync_id == sync_id and e.entity_id in entity_ids
        }
