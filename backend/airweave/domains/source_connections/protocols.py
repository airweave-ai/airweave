"""Protocols for source connection domain."""

from datetime import datetime
from typing import Any, List, Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.source_connections.types import ScheduleInfo, SourceConnectionStats
from airweave.models.connection_init_session import ConnectionInitSession
from airweave.models.source_connection import SourceConnection
from airweave.models.sync_job import SyncJob
from airweave.schemas.source_connection import (
    SourceConnection as SourceConnectionSchema,
)
from airweave.schemas.source_connection import (
    SourceConnectionCreate,
    SourceConnectionJob,
    SourceConnectionListItem,
    SourceConnectionUpdate,
)


class SourceConnectionRepositoryProtocol(Protocol):
    """Data access for source connections.

    Wraps crud.source_connection for testability.
    """

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[SourceConnection]:
        """Get a source connection by ID within org scope."""
        ...

    async def get_by_sync_id(
        self, db: AsyncSession, sync_id: UUID, ctx: ApiContext
    ) -> Optional[SourceConnection]:
        """Get a source connection by sync ID within org scope."""
        ...

    async def get_schedule_info(
        self, db: AsyncSession, source_connection: SourceConnection
    ) -> Optional[ScheduleInfo]:
        """Get schedule info for a source connection."""
        ...

    async def get_by_init_session(
        self, db: AsyncSession, *, init_session_id: UUID, ctx: ApiContext
    ) -> Optional[SourceConnection]:
        """Get source connection by init session ID within org scope."""
        ...

    async def get_init_session_with_redirect(
        self, db: AsyncSession, session_id: UUID, ctx: ApiContext
    ) -> Optional[ConnectionInitSession]:
        """Get a ConnectionInitSession by ID with redirect_session eagerly loaded."""
        ...

    async def get_multi_with_stats(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnectionStats]:
        """Get source connections with complete stats."""
        ...

    async def get_sync_ids_for_collection(
        self,
        db: AsyncSession,
        *,
        organization_id: UUID,
        readable_collection_id: str,
    ) -> List[UUID]:
        """Get all sync IDs for source connections in a collection."""
        ...

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: SourceConnection,
        obj_in: dict[str, Any],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> SourceConnection:
        """Update a source connection."""
        ...

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: dict[str, Any],
        ctx: ApiContext,
        uow: Optional[UnitOfWork] = None,
    ) -> SourceConnection:
        """Create a source connection."""
        ...

    async def remove(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
    ) -> Optional[SourceConnection]:
        """Delete a source connection by ID."""
        ...


class ResponseBuilderProtocol(Protocol):
    """Builds API response schemas for source connections."""

    async def build_response(
        self,
        db: AsyncSession,
        source_conn: SourceConnection,
        ctx: ApiContext,
        *,
        auth_url_override: Optional[str] = None,
        auth_url_expiry_override: Optional[datetime] = None,
    ) -> SourceConnectionSchema:
        """Build full SourceConnection response from ORM object."""
        ...

    def build_list_item(self, stats: SourceConnectionStats) -> SourceConnectionListItem:
        """Build a SourceConnectionListItem from a typed stats object."""
        ...

    def map_sync_job(self, job: SyncJob, source_connection_id: UUID) -> SourceConnectionJob:
        """Convert sync job to SourceConnectionJob schema."""
        ...


class SourceConnectionDeletionServiceProtocol(Protocol):
    """Deletes a source connection and all related data."""

    async def delete(
        self, db: AsyncSession, *, id: UUID, ctx: ApiContext
    ) -> SourceConnectionSchema:
        """Delete a source connection."""
        ...


class SourceConnectionUpdateServiceProtocol(Protocol):
    """Updates a source connection."""

    async def update(
        self, db: AsyncSession, *, id: UUID, obj_in: SourceConnectionUpdate, ctx: ApiContext
    ) -> SourceConnectionSchema:
        """Update a source connection."""
        ...


class SourceConnectionCreateServiceProtocol(Protocol):
    """Creates source connections across supported auth flows."""

    async def create(
        self, db: AsyncSession, *, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnectionSchema:
        """Create a source connection."""
        ...


class SourceConnectionServiceProtocol(Protocol):
    """Service for source connections."""

    async def get(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> SourceConnection:
        """Get a source connection by ID."""
        ...

    async def list(
        self,
        db: AsyncSession,
        *,
        ctx: ApiContext,
        readable_collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnectionListItem]:
        """List source connections."""
        ...

    async def create(
        self, db: AsyncSession, obj_in: SourceConnectionCreate, ctx: ApiContext
    ) -> SourceConnection:
        """Create a source connection."""
        ...

    async def update(
        self, db: AsyncSession, id: UUID, obj_in: SourceConnectionUpdate, ctx: ApiContext
    ) -> SourceConnection:
        """Update a source connection."""
        ...

    async def delete(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> SourceConnection:
        """Delete a source connection."""
        ...

    async def run(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        force_full_sync: bool = False,
    ) -> SourceConnectionJob:
        """Trigger a sync run for this source connection."""
        ...

    async def get_jobs(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: ApiContext,
        limit: int = 100,
    ) -> List[SourceConnectionJob]:
        """List sync jobs for this source connection."""
        ...

    async def cancel_job(
        self,
        db: AsyncSession,
        *,
        source_connection_id: UUID,
        job_id: UUID,
        ctx: ApiContext,
    ) -> SourceConnectionJob:
        """Cancel a running sync job."""
        ...

    async def get_sync_id(self, db: AsyncSession, *, id: UUID, ctx: ApiContext) -> dict:
        """Get the sync_id for a source connection."""
        ...

    async def get_redirect_url(self, db: AsyncSession, *, code: str) -> str:
        """Resolve a short redirect code to its final OAuth authorization URL."""
        ...
