"""Fake entity repository for testing."""

from typing import Dict, List, Tuple
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
