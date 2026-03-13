"""Fake ConnectService for testing."""

from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.domains.connect.protocols import ConnectServiceProtocol
from airweave.schemas.connect_session import (
    ConnectSessionContext,
    ConnectSessionCreate,
    ConnectSessionResponse,
)


class FakeConnectService(ConnectServiceProtocol):
    """In-memory fake for ConnectServiceProtocol.

    Seeds control return values; _calls records all invocations.
    """

    def __init__(self) -> None:
        self._calls: list[tuple[str, ...]] = []
        self._session_response: Optional[ConnectSessionResponse] = None
        self._sources: List[schemas.Source] = []
        self._source_by_name: dict[str, schemas.Source] = {}
        self._connections: List[schemas.SourceConnectionListItem] = []
        self._connection_by_id: dict[UUID, Any] = {}
        self._jobs: List[schemas.SourceConnectionJob] = []

    # -- seeding helpers ------------------------------------------------

    def seed_session_response(self, resp: ConnectSessionResponse) -> None:
        self._session_response = resp

    def seed_sources(self, sources: List[schemas.Source]) -> None:
        self._sources = sources
        self._source_by_name = {s.short_name: s for s in sources}

    def seed_connections(self, items: List[schemas.SourceConnectionListItem]) -> None:
        self._connections = items

    def seed_connection(self, id: UUID, conn: Any) -> None:
        self._connection_by_id[id] = conn

    def seed_jobs(self, jobs: List[schemas.SourceConnectionJob]) -> None:
        self._jobs = jobs

    # -- protocol methods -----------------------------------------------

    async def create_session(
        self,
        db: AsyncSession,
        session_in: ConnectSessionCreate,
        ctx: ApiContext,
    ) -> ConnectSessionResponse:
        self._calls.append(("create_session", session_in, ctx))
        if self._session_response:
            return self._session_response
        raise NotImplementedError("FakeConnectService.create_session not seeded")

    async def list_sources(
        self,
        db: AsyncSession,
        session: ConnectSessionContext,
    ) -> List[schemas.Source]:
        self._calls.append(("list_sources", session))
        return self._sources

    async def get_source(
        self,
        db: AsyncSession,
        short_name: str,
        session: ConnectSessionContext,
    ) -> schemas.Source:
        self._calls.append(("get_source", short_name, session))
        source = self._source_by_name.get(short_name)
        if not source:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail=f"Source not found: {short_name}")
        return source

    async def list_source_connections(
        self,
        db: AsyncSession,
        session: ConnectSessionContext,
    ) -> List[schemas.SourceConnectionListItem]:
        self._calls.append(("list_source_connections", session))
        return self._connections

    async def get_source_connection(
        self,
        db: AsyncSession,
        connection_id: UUID,
        session: ConnectSessionContext,
    ) -> Any:
        self._calls.append(("get_source_connection", connection_id, session))
        conn = self._connection_by_id.get(connection_id)
        if not conn:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Source connection not found")
        return conn

    async def delete_source_connection(
        self,
        db: AsyncSession,
        connection_id: UUID,
        session: ConnectSessionContext,
    ) -> Any:
        self._calls.append(("delete_source_connection", connection_id, session))
        conn = self._connection_by_id.pop(connection_id, None)
        if not conn:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Source connection not found")
        return conn

    async def create_source_connection(
        self,
        db: AsyncSession,
        source_connection_in: schemas.SourceConnectionCreate,
        session: ConnectSessionContext,
        session_token: str,
    ) -> Any:
        self._calls.append(
            ("create_source_connection", source_connection_in, session, session_token)
        )
        raise NotImplementedError("FakeConnectService.create_source_connection not seeded")

    async def get_connection_jobs(
        self,
        db: AsyncSession,
        connection_id: UUID,
        session: ConnectSessionContext,
    ) -> List[schemas.SourceConnectionJob]:
        self._calls.append(("get_connection_jobs", connection_id, session))
        return self._jobs
