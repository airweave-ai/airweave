"""Fake source connection deletion service for testing."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.schemas.source_connection import SourceConnection as SourceConnectionSchema


class FakeSourceConnectionDeletionService:
    """In-memory fake for SourceConnectionDeletionServiceProtocol."""

    def __init__(self) -> None:
        self._responses: dict[UUID, SourceConnectionSchema] = {}
        self._should_raise: Optional[Exception] = None
        self._calls: list[tuple[Any, ...]] = []

    def seed_response(self, id: UUID, response: SourceConnectionSchema) -> None:
        self._responses[id] = response

    def set_should_raise(self, exc: Exception) -> None:
        self._should_raise = exc

    async def delete(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
    ) -> SourceConnectionSchema:
        self._calls.append(("delete", db, id, ctx))
        if self._should_raise:
            raise self._should_raise
        response = self._responses.get(id)
        if response is None:
            raise NotFoundException("Source connection not found")
        del self._responses[id]
        return response
