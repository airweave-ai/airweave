"""Fake source connection update service for testing."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.schemas.source_connection import (
    SourceConnection as SourceConnectionSchema,
)
from airweave.schemas.source_connection import SourceConnectionUpdate


class FakeSourceConnectionUpdateService:
    """In-memory fake for SourceConnectionUpdateServiceProtocol."""

    def __init__(self) -> None:
        self._responses: dict[UUID, SourceConnectionSchema] = {}
        self._should_raise: Optional[Exception] = None
        self._calls: list[tuple[Any, ...]] = []

    def seed_response(self, id: UUID, response: SourceConnectionSchema) -> None:
        self._responses[id] = response

    def set_should_raise(self, exc: Exception) -> None:
        self._should_raise = exc

    async def update(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        obj_in: SourceConnectionUpdate,
        ctx: ApiContext,
    ) -> SourceConnectionSchema:
        self._calls.append(("update", db, id, obj_in, ctx))
        if self._should_raise:
            raise self._should_raise
        response = self._responses.get(id)
        if response is None:
            raise NotFoundException("Source connection not found")
        return response
