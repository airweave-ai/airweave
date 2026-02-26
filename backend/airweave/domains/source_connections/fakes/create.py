"""Fake source connection creation service for testing."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.schemas.source_connection import SourceConnection, SourceConnectionCreate


class FakeSourceConnectionCreateService:
    """In-memory fake for SourceConnectionCreateServiceProtocol."""

    def __init__(self) -> None:
        self._result: Optional[SourceConnection] = None
        self._error: Optional[Exception] = None
        self._calls: list[tuple] = []

    def set_result(self, result: SourceConnection) -> None:
        self._result = result

    def set_error(self, error: Exception) -> None:
        self._error = error

    async def create(
        self, db: AsyncSession, *, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnection:
        self._calls.append(("create", db, obj_in, ctx))
        if self._error:
            raise self._error
        if self._result is None:
            raise RuntimeError("FakeSourceConnectionCreateService.result not configured")
        return self._result
