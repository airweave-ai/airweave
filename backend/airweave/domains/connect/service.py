"""Connect service — owns all Connect session business logic.

Replaces the inline logic that was previously in api/v1/endpoints/connect.py.
All legacy singletons replaced with injected domain services/protocols.
"""

from datetime import datetime, timedelta, timezone
from typing import FrozenSet, List
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ConnectContext
from airweave.core.context import BaseContext
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.connect.protocols import ConnectServiceProtocol
from airweave.domains.connect.types import MODES_CREATE, MODES_DELETE, MODES_VIEW
from airweave.domains.organizations.protocols import OrganizationRepositoryProtocol
from airweave.domains.source_connections.protocols import SourceConnectionServiceProtocol
from airweave.domains.sources.protocols import SourceServiceProtocol
from airweave.domains.syncs.protocols import SyncJobRepositoryProtocol
from airweave.platform.auth.state import make_state
from airweave.schemas.connect_session import (
    ConnectSessionContext,
    ConnectSessionCreate,
    ConnectSessionResponse,
)


class ConnectService(ConnectServiceProtocol):
    """Service for Connect session operations.

    All guard logic lives as private methods — nothing floats outside.
    All dependencies are injected — no legacy singletons.
    """

    def __init__(  # noqa: D107
        self,
        source_connection_service: SourceConnectionServiceProtocol,
        source_service: SourceServiceProtocol,
        org_repo: OrganizationRepositoryProtocol,
        collection_repo: CollectionRepositoryProtocol,
        sync_job_repo: SyncJobRepositoryProtocol,
    ) -> None:
        self._sc_service = source_connection_service
        self._source_service = source_service
        self._org_repo = org_repo
        self._collection_repo = collection_repo
        self._sync_job_repo = sync_job_repo

    # ------------------------------------------------------------------
    # Guards (private — all access checks live on the service)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_mode(
        session: ConnectSessionContext,
        allowed_modes: FrozenSet[schemas.ConnectSessionMode],
        operation: str,
    ) -> None:
        """Validate session mode allows the requested operation."""
        if session.mode not in allowed_modes:
            raise HTTPException(
                status_code=403,
                detail=f"Session mode does not allow {operation}",
            )

    @staticmethod
    def _check_integration_access(
        session: ConnectSessionContext,
        short_name: str,
    ) -> None:
        """Raise 403 if integration is not in allowed_integrations."""
        if session.allowed_integrations and short_name not in session.allowed_integrations:
            raise HTTPException(
                status_code=403,
                detail=f"Source '{short_name}' is not allowed for this session",
            )

    @staticmethod
    def _check_collection_scope(
        readable_collection_id: str,
        session: ConnectSessionContext,
    ) -> None:
        """Raise 403 if connection does not belong to session's collection."""
        if readable_collection_id != session.collection_id:
            raise HTTPException(
                status_code=403,
                detail="Source connection does not belong to this session's collection",
            )

    # ------------------------------------------------------------------
    # Context builder
    # ------------------------------------------------------------------

    async def _build_context(
        self,
        db: AsyncSession,
        session: ConnectSessionContext,
    ) -> ConnectContext:
        """Build a ConnectContext from a decoded session token."""
        org = await self._org_repo.get(
            db, id=session.organization_id, skip_access_validation=True, enrich=True
        )
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")

        return ConnectContext.from_session(
            organization=org,
            session_id=session.session_id,
            collection_id=session.collection_id,
            end_user_id=session.end_user_id,
            allowed_integrations=session.allowed_integrations,
            mode=session.mode.value,
        )

    # ------------------------------------------------------------------
    # Verified-connection helper (reused by get/delete/jobs/subscribe)
    # ------------------------------------------------------------------

    async def _get_verified_connection(
        self,
        db: AsyncSession,
        connection_id: UUID,
        session: ConnectSessionContext,
        ctx: BaseContext,
    ) -> schemas.SourceConnection:
        """Fetch a connection and verify it belongs to the session scope."""
        try:
            connection = await self._sc_service.get(
                db,
                id=connection_id,
                ctx=ctx,  # type: ignore[arg-type]
            )
        except HTTPException as e:
            if e.status_code == 404:
                raise HTTPException(status_code=404, detail="Source connection not found") from e
            raise

        self._check_collection_scope(str(connection.readable_collection_id), session)
        self._check_integration_access(session, connection.short_name)
        return connection  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Session operations
    # ------------------------------------------------------------------

    async def create_session(
        self,
        db: AsyncSession,
        session_in: ConnectSessionCreate,
        ctx: BaseContext,
    ) -> ConnectSessionResponse:
        """Create a connect session token (server-to-server, API key auth)."""
        collection = await self._collection_repo.get_by_readable_id(
            db,
            readable_id=session_in.readable_collection_id,
            ctx=ctx,  # type: ignore[arg-type]
        )
        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")

        session_id = uuid4()

        token = make_state(
            {
                "sid": str(session_id),
                "oid": str(ctx.organization.id),
                "cid": session_in.readable_collection_id,
                "int": session_in.allowed_integrations,
                "mode": session_in.mode.value,
                "uid": session_in.end_user_id,
            }
        )

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        # TODO: track connect_session_created via event bus

        ctx.logger.info(
            f"Created connect session {session_id} for collection "
            f"{session_in.readable_collection_id}"
            + (f" (end_user: {session_in.end_user_id})" if session_in.end_user_id else "")
        )

        return ConnectSessionResponse(
            session_id=session_id,
            session_token=token,
            expires_at=expires_at,
        )

    # ------------------------------------------------------------------
    # Source catalog
    # ------------------------------------------------------------------

    async def list_sources(
        self,
        db: AsyncSession,
        session: ConnectSessionContext,
    ) -> List[schemas.Source]:
        """List available sources, filtered by session restrictions."""
        ctx = await self._build_context(db, session)
        ctx.logger.info("Listing available sources for connect session")

        all_sources = await self._source_service.list(ctx)  # type: ignore[arg-type]

        if session.allowed_integrations:
            all_sources = [s for s in all_sources if s.short_name in session.allowed_integrations]

        ctx.logger.info(f"Returning {len(all_sources)} sources for connect session")
        return all_sources

    async def get_source(
        self,
        db: AsyncSession,
        short_name: str,
        session: ConnectSessionContext,
    ) -> schemas.Source:
        """Get a single source's details."""
        self._check_integration_access(session, short_name)
        ctx = await self._build_context(db, session)
        return await self._source_service.get(short_name, ctx)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Source connections (CRUD)
    # ------------------------------------------------------------------

    async def list_source_connections(
        self,
        db: AsyncSession,
        session: ConnectSessionContext,
    ) -> List[schemas.SourceConnectionListItem]:
        """List connections in session's collection."""
        self._check_mode(session, MODES_VIEW, "viewing source connections")

        ctx = await self._build_context(db, session)
        connections = await self._sc_service.list(
            db,
            ctx=ctx,  # type: ignore[arg-type]
            readable_collection_id=session.collection_id,
        )

        if session.allowed_integrations:
            connections = [c for c in connections if c.short_name in session.allowed_integrations]

        return connections

    async def get_source_connection(
        self,
        db: AsyncSession,
        connection_id: UUID,
        session: ConnectSessionContext,
    ) -> schemas.SourceConnection:
        """Get a single source connection within session scope."""
        self._check_mode(session, MODES_VIEW, "viewing source connections")
        ctx = await self._build_context(db, session)
        return await self._get_verified_connection(db, connection_id, session, ctx)

    async def delete_source_connection(
        self,
        db: AsyncSession,
        connection_id: UUID,
        session: ConnectSessionContext,
    ) -> schemas.SourceConnection:
        """Delete a source connection within session scope."""
        self._check_mode(session, MODES_DELETE, "deleting source connections")
        ctx = await self._build_context(db, session)
        await self._get_verified_connection(db, connection_id, session, ctx)

        ctx.logger.info(
            f"Deleting source connection {connection_id} via connect session {session.session_id}"
        )

        # TODO: track connect_source_connection_deleted via event bus

        return await self._sc_service.delete(db, connection_id, ctx)  # type: ignore[arg-type,return-value]

    async def create_source_connection(
        self,
        db: AsyncSession,
        source_connection_in: schemas.SourceConnectionCreate,
        session: ConnectSessionContext,
        session_token: str,
    ) -> schemas.SourceConnection:
        """Create a source connection via Connect session."""
        self._check_mode(session, MODES_CREATE, "creating source connections")
        self._check_integration_access(session, source_connection_in.short_name)

        # SECURITY: Override collection_id from session (ignore request body)
        source_connection_in.readable_collection_id = session.collection_id

        ctx = await self._build_context(db, session)
        ctx.logger.info(
            f"Creating source connection via connect session {session.session_id} "
            f"for source '{source_connection_in.short_name}' "
            f"in collection '{session.collection_id}'"
        )

        # Attach connect session data for OAuth callback validation
        connect_context = {
            "session_id": str(session.session_id),
            "organization_id": str(session.organization_id),
            "collection_id": session.collection_id,
            "end_user_id": session.end_user_id,
        }
        source_connection_in._connect_session_token = session_token  # type: ignore[attr-defined]  # noqa: SLF001
        source_connection_in._connect_session_context = connect_context  # type: ignore[attr-defined]  # noqa: SLF001

        result = await self._sc_service.create(db, source_connection_in, ctx)  # type: ignore[arg-type]

        # TODO: track connect_source_connection_created via event bus

        return result  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Sync jobs
    # ------------------------------------------------------------------

    async def get_connection_jobs(
        self,
        db: AsyncSession,
        connection_id: UUID,
        session: ConnectSessionContext,
    ) -> List[schemas.SourceConnectionJob]:
        """Get sync jobs for a source connection within session scope."""
        ctx = await self._build_context(db, session)
        connection = await self._get_verified_connection(db, connection_id, session, ctx)

        if not connection.sync_id:
            return []

        jobs = await self._sync_job_repo.get_all_by_sync_id(
            db,
            sync_id=connection.sync_id,
            ctx=ctx,  # type: ignore[arg-type]
        )
        return [
            schemas.SyncJob.model_validate(job).to_source_connection_job(connection_id)  # type: ignore[misc]
            for job in jobs
        ]
