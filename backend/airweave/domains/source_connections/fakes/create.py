"""Fake source connection creation service for testing."""

from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.schemas.source_connection import (
    SourceConnection as SourceConnectionSchema,
    SourceConnectionCreate,
)


class FakeSourceConnectionCreationService:
    """In-memory fake for SourceConnectionCreationServiceProtocol."""

    def __init__(self) -> None:
        self._calls: list[tuple[Any, ...]] = []
        self._create_result: Optional[SourceConnectionSchema] = None

    def set_create_result(self, result: SourceConnectionSchema) -> None:
        self._create_result = result

    async def create(
        self, db: AsyncSession, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnectionSchema:
        self._calls.append(("create", db, obj_in, ctx))
        if self._create_result is not None:
            return self._create_result
        raise NotImplementedError(
            "FakeSourceConnectionCreationService.create: call set_create_result()"
        )
