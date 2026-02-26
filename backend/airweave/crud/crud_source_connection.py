"""Refactored CRUD operations for source connections with optimized queries."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from airweave.core.context import BaseContext
from airweave.core.shared_models import SourceConnectionStatus, SyncJobStatus
from airweave.models.connection import Connection
from airweave.models.source_connection import SourceConnection
from airweave.models.sync import Sync
from airweave.models.sync_job import SyncJob
from airweave.schemas.source_connection import (
    SourceConnectionUpdate,
)

from ._base_organization import CRUDBaseOrganization


class CRUDSourceConnection(
    CRUDBaseOrganization[SourceConnection, Dict[str, Any], SourceConnectionUpdate]
):
    """Refactored CRUD with optimized queries and clean abstractions.

    Key improvements:
    - Bulk fetching to avoid N+1 queries
    - Optimized joins for related data
    - Clean separation of concerns
    - No exposure of internal sync/job IDs
    """

    async def get_with_relations(
        self,
        db: AsyncSession,
        *,
        id: UUID,
        ctx: BaseContext,
        include_sync: bool = False,
        include_collection: bool = False,
        include_credential: bool = False,
    ) -> Optional[SourceConnection]:
        """Get source connection with optional eager loading of relations."""
        query = select(SourceConnection).where(
            and_(
                SourceConnection.id == id,
                SourceConnection.organization_id == ctx.organization.id,
            )
        )

        # Add eager loading based on requirements
        if include_sync:
            query = query.options(joinedload(SourceConnection.sync))
        if include_collection:
            query = query.options(joinedload(SourceConnection.sync).joinedload(Sync.collection))
        if include_credential:
            query = query.options(
                joinedload(SourceConnection.connection).joinedload(
                    Connection.integration_credential
                )
            )

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_multi_with_stats(
        self,
        db: AsyncSession,
        *,
        ctx: BaseContext,
        collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get source connections with all necessary stats in minimal queries.

        Returns list of dictionaries with complete data for the list endpoint.
        """
        # 1. Get base source connections
        query = select(SourceConnection).where(
            SourceConnection.organization_id == ctx.organization.id
        )

        if collection_id:
            query = query.where(SourceConnection.readable_collection_id == collection_id)

        query = query.offset(skip).limit(limit).order_by(SourceConnection.created_at.desc())
        result = await db.execute(query)
        source_connections = list(result.scalars().all())

        if not source_connections:
            return []

        # 2. Bulk fetch all related data
        # These queries can run independently
        auth_methods = await self._fetch_auth_methods(db, source_connections)
        last_jobs = await self._fetch_last_jobs(db, source_connections)
        entity_counts = await self._fetch_entity_counts(db, source_connections)
        federated_search_flags = await self._fetch_federated_search_flags(db, source_connections)

        # 3. Combine into response dictionaries
        results = []
        for sc in source_connections:
            results.append(
                {
                    # Base fields
                    "id": sc.id,
                    "name": sc.name,
                    "short_name": sc.short_name,
                    "readable_collection_id": sc.readable_collection_id,
                    "created_at": sc.created_at,
                    "modified_at": sc.modified_at,
                    "is_authenticated": sc.is_authenticated,
                    "readable_auth_provider_id": sc.readable_auth_provider_id,
                    "connection_init_session_id": sc.connection_init_session_id,
                    "is_active": getattr(sc, "is_active", True),
                    # Fetched data
                    "authentication_method": auth_methods.get(sc.id),
                    "last_job": last_jobs.get(sc.id),
                    "entity_count": entity_counts.get(sc.id, 0),
                    "federated_search": federated_search_flags.get(sc.short_name, False),
                }
            )

        return results

    async def _attach_last_sync_info_bulk(
        self,
        db: AsyncSession,
        source_connections: List[SourceConnection],
    ) -> None:
        """Efficiently attach last sync job info to multiple connections."""
        sync_ids = [sc.sync_id for sc in source_connections if sc.sync_id]
        if not sync_ids:
            return

        # Get latest sync job for each sync in one query
        subq = (
            select(
                SyncJob.sync_id,
                SyncJob.id,
                SyncJob.status,
                SyncJob.started_at,
                SyncJob.completed_at,
                SyncJob.entities_inserted,
                SyncJob.entities_updated,
                SyncJob.entities_deleted,
                SyncJob.entities_kept,
                SyncJob.entities_skipped,
                SyncJob.error,
                func.row_number()
                .over(partition_by=SyncJob.sync_id, order_by=SyncJob.created_at.desc())
                .label("rn"),
            )
            .where(SyncJob.sync_id.in_(sync_ids))
            .subquery()
        )

        query = select(subq).where(subq.c.rn == 1)
        result = await db.execute(query)

        # Map sync_id to last job info
        last_jobs = {
            row.sync_id: {
                "id": row.id,
                "status": row.status,
                "started_at": row.started_at,
                "completed_at": row.completed_at,
                "duration_seconds": (
                    (row.completed_at - row.started_at).total_seconds()
                    if row.completed_at and row.started_at
                    else None
                ),
                "entities_inserted": row.entities_inserted or 0,
                "entities_updated": row.entities_updated or 0,
                "entities_deleted": row.entities_deleted or 0,
                "entities_kept": row.entities_kept or 0,
                "entities_skipped": row.entities_skipped or 0,
                "error": row.error,
            }
            for row in result
        }

        # Attach to source connections
        for sc in source_connections:
            if sc.sync_id and sc.sync_id in last_jobs:
                sc._last_sync_job = last_jobs[sc.sync_id]

                # Update status based on last job
                if not sc.is_authenticated:
                    sc.status = SourceConnectionStatus.PENDING_AUTH
                elif sc._last_sync_job["status"] == SyncJobStatus.FAILED:
                    sc.status = SourceConnectionStatus.ERROR
                elif sc._last_sync_job["status"] in (
                    SyncJobStatus.RUNNING,
                    SyncJobStatus.CANCELLING,
                ):
                    sc.status = SourceConnectionStatus.SYNCING
                else:
                    sc.status = SourceConnectionStatus.ACTIVE
            else:
                sc.status = SourceConnectionStatus.PENDING_SYNC

    async def _fetch_auth_methods(
        self, db: AsyncSession, source_conns: List[SourceConnection]
    ) -> Dict[UUID, str]:
        """Fetch authentication methods from credentials."""
        from airweave.models.connection import Connection
        from airweave.models.integration_credential import IntegrationCredential

        conn_ids = [sc.connection_id for sc in source_conns if sc.connection_id]
        if not conn_ids:
            return {}

        query = (
            select(SourceConnection.id, IntegrationCredential.authentication_method)
            .join(Connection, SourceConnection.connection_id == Connection.id)
            .join(
                IntegrationCredential,
                Connection.integration_credential_id == IntegrationCredential.id,
            )
            .where(SourceConnection.id.in_([sc.id for sc in source_conns]))
        )

        result = await db.execute(query)
        auth_methods = {}

        for row in result:
            # Store the raw authentication method string
            auth_methods[row[0]] = row[1]

        # Also check for auth provider connections
        for sc in source_conns:
            if hasattr(sc, "readable_auth_provider_id") and sc.readable_auth_provider_id:
                auth_methods[sc.id] = "auth_provider"

        return auth_methods

    async def _fetch_last_jobs(
        self, db: AsyncSession, source_conns: List[SourceConnection]
    ) -> Dict[UUID, Dict]:
        """Fetch last sync job for each connection."""
        sync_ids = [sc.sync_id for sc in source_conns if sc.sync_id]
        if not sync_ids:
            return {}

        # Use window function to get latest job per sync
        subq = (
            select(
                SyncJob.sync_id,
                SyncJob.status,
                SyncJob.completed_at,
                func.row_number()
                .over(partition_by=SyncJob.sync_id, order_by=SyncJob.created_at.desc())
                .label("rn"),
            )
            .where(SyncJob.sync_id.in_(sync_ids))
            .subquery()
        )

        query = select(subq).where(subq.c.rn == 1)
        result = await db.execute(query)

        # Map to source connection IDs
        sync_to_sc = {sc.sync_id: sc.id for sc in source_conns if sc.sync_id}
        return {
            sync_to_sc[row.sync_id]: {"status": row.status, "completed_at": row.completed_at}
            for row in result
            if row.sync_id in sync_to_sc
        }

    async def _fetch_entity_counts(
        self, db: AsyncSession, source_conns: List[SourceConnection]
    ) -> Dict[UUID, int]:
        """Fetch total entity counts from EntityCount table."""
        from airweave.models.entity_count import EntityCount

        sync_ids = [sc.sync_id for sc in source_conns if sc.sync_id]
        if not sync_ids:
            return {}

        query = (
            select(EntityCount.sync_id, func.sum(EntityCount.count).label("total"))
            .where(EntityCount.sync_id.in_(sync_ids))
            .group_by(EntityCount.sync_id)
        )

        result = await db.execute(query)

        # Map to source connection IDs
        sync_to_sc = {sc.sync_id: sc.id for sc in source_conns if sc.sync_id}
        return {
            sync_to_sc[row.sync_id]: row.total or 0 for row in result if row.sync_id in sync_to_sc
        }

    async def _fetch_federated_search_flags(
        self, db: AsyncSession, source_conns: List[SourceConnection]
    ) -> Dict[str, bool]:
        """Fetch federated_search flags from Source table by short_name."""
        from airweave.models.source import Source

        short_names = {sc.short_name for sc in source_conns}
        if not short_names:
            return {}

        query = select(Source.short_name, Source.federated_search).where(
            Source.short_name.in_(short_names)
        )

        result = await db.execute(query)

        # Map short_name to federated_search flag
        return {row.short_name: row.federated_search or False for row in result}

    async def get_by_query_and_org(
        self,
        db: AsyncSession,
        ctx: BaseContext,
        **kwargs,
    ) -> Optional[SourceConnection]:
        """Get source connection by arbitrary query within organization scope."""
        query = select(SourceConnection).where(
            SourceConnection.organization_id == ctx.organization.id
        )

        for key, value in kwargs.items():
            if hasattr(SourceConnection, key):
                query = query.where(getattr(SourceConnection, key) == value)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def bulk_update_status(
        self,
        db: AsyncSession,
        *,
        ids: List[UUID],
        status: SourceConnectionStatus,
        ctx: BaseContext,
    ) -> int:
        """Bulk update status for multiple source connections."""
        query = select(SourceConnection).where(
            and_(
                SourceConnection.id.in_(ids),
                SourceConnection.organization_id == ctx.organization.id,
            )
        )

        result = await db.execute(query)
        source_connections = result.scalars().all()

        for sc in source_connections:
            sc.status = status

        await db.commit()
        return len(source_connections)

    async def get_schedule_info(
        self,
        db: AsyncSession,
        source_connection: SourceConnection,
    ) -> Optional[Dict[str, Any]]:
        """Get schedule information for a source connection."""
        if not source_connection.sync_id:
            return None

        sync = await db.get(Sync, source_connection.sync_id)
        if not sync:
            return None

        # Convert naive UTC datetime to timezone-aware for proper serialization
        next_run_at = None
        if sync.next_scheduled_run:
            from datetime import timezone

            # Database stores naive UTC, make it timezone-aware
            next_run_at = sync.next_scheduled_run.replace(tzinfo=timezone.utc)

        return {
            "cron_expression": sync.cron_schedule,
            "next_run_at": next_run_at,
            "is_continuous": getattr(sync, "is_continuous", False),
            "cursor_field": getattr(sync, "cursor_field", None),
            "cursor_value": getattr(sync, "cursor_value", None),
        }

    async def get_entity_states(
        self,
        db: AsyncSession,
        source_connection: SourceConnection,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Get entity state information for a source connection.

        NOTE: This method needs to be refactored to use either:
        1. SyncJob's actual fields (entities_inserted, entities_updated, etc.)
        2. EntityCount model for per-entity-type tracking

        Currently returning empty list to avoid mixing concepts.
        """
        if not source_connection.sync_id:
            return []

        # TODO: Implement proper entity states
        # Option 1: Use SyncJob stats directly
        # query = (
        #     select(
        #         SyncJob.id,
        #         SyncJob.entities_inserted,
        #         SyncJob.entities_updated,
        #         SyncJob.entities_deleted,
        #         SyncJob.entities_kept,
        #         SyncJob.entities_skipped,
        #         SyncJob.created_at,
        #     )
        #     .where(SyncJob.sync_id == source_connection.sync_id)
        #     .order_by(SyncJob.created_at.desc())
        #     .limit(1)
        # )

        # Option 2: Use EntityCount for per-type tracking
        # from airweave import crud
        # entity_counts = await crud.entity_count.get_counts_per_sync_and_type(
        #     db, source_connection.sync_id
        # )

        return []

    async def count_by_status(
        self,
        db: AsyncSession,
        *,
        ctx: BaseContext,
        collection_id: Optional[str] = None,
    ) -> Dict[SourceConnectionStatus, int]:
        """Count source connections by status."""
        query = (
            select(
                SourceConnection.status,
                func.count(SourceConnection.id).label("count"),
            )
            .where(SourceConnection.organization_id == ctx.organization.id)
            .group_by(SourceConnection.status)
        )

        if collection_id:
            query = query.where(SourceConnection.readable_collection_id == collection_id)

        result = await db.execute(query)
        return {row.status: row.count for row in result}

    async def get_for_collection(
        self,
        db: AsyncSession,
        *,
        readable_collection_id: str,
        ctx: BaseContext,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnection]:
        """Get all source connections for a collection."""
        query = select(SourceConnection).where(
            and_(
                SourceConnection.readable_collection_id == readable_collection_id,
                SourceConnection.organization_id == ctx.organization.id,
            )
        )
        query = query.offset(skip).limit(limit).order_by(SourceConnection.created_at.desc())
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_by_sync_id(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        ctx: BaseContext,
    ) -> Optional[SourceConnection]:
        """Get a source connection by sync ID."""
        query = select(SourceConnection).where(
            and_(
                SourceConnection.sync_id == sync_id,
                SourceConnection.organization_id == ctx.organization.id,
            )
        )
        result = await db.execute(query)
        source_connection = result.scalar_one_or_none()
        if not source_connection:
            return None

        await self._validate_organization_access(ctx, source_connection.organization_id)
        return source_connection


# Singleton instance
source_connection = CRUDSourceConnection(SourceConnection)
