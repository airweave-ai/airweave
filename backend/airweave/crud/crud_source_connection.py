"""Refactored CRUD operations for source connections with optimized queries."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from airweave.api.context import ApiContext
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
        ctx: ApiContext,
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
        ctx: ApiContext,
        collection_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnection]:
        """Get multiple source connections with aggregated stats."""
        query = select(SourceConnection).where(
            SourceConnection.organization_id == ctx.organization.id
        )

        if collection_id:
            query = query.where(SourceConnection.readable_collection_id == collection_id)

        query = query.offset(skip).limit(limit)

        result = await db.execute(query)
        source_connections = list(result.scalars().all())

        if source_connections:
            # Bulk fetch last sync job info
            await self._attach_last_sync_info_bulk(db, source_connections)

            # Bulk fetch entity counts
            # await self._attach_entity_counts_bulk(db, source_connections)

        return source_connections

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
                elif sc._last_sync_job["status"] == SyncJobStatus.RUNNING:
                    sc.status = SourceConnectionStatus.SYNCING
                else:
                    sc.status = SourceConnectionStatus.ACTIVE
            else:
                sc.status = SourceConnectionStatus.PENDING_SYNC

    async def _attach_entity_counts_bulk(
        self,
        db: AsyncSession,
        source_connections: List[SourceConnection],
    ) -> None:
        """Efficiently attach entity counts to multiple connections."""
        sync_ids = [sc.sync_id for sc in source_connections if sc.sync_id]
        if not sync_ids:
            return

        # Get entity counts per sync
        query = (
            select(
                SyncJob.sync_id,
                func.sum(SyncJob.entities_inserted).label("total_entities_inserted"),
                func.sum(SyncJob.entities_updated).label("total_entities_updated"),
                func.sum(SyncJob.entities_deleted).label("total_entities_deleted"),
                func.sum(SyncJob.entities_kept).label("total_entities_kept"),
                func.sum(SyncJob.entities_skipped).label("total_entities_skipped"),
            )
            .where(SyncJob.sync_id.in_(sync_ids))
            .group_by(SyncJob.sync_id)
        )

        result = await db.execute(query)
        entity_counts = {row.sync_id: row.total_entities or 0 for row in result}

        # Attach to source connections
        for sc in source_connections:
            if sc.sync_id:
                sc._entities_count = entity_counts.get(sc.sync_id, 0)

    async def get_by_query_and_org(
        self,
        db: AsyncSession,
        ctx: ApiContext,
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
        ctx: ApiContext,
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

        return {
            "cron_expression": sync.cron_schedule,
            "next_run_at": sync.next_scheduled_run,
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
        ctx: ApiContext,
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
        ctx: ApiContext,
        skip: int = 0,
        limit: int = 100,
    ) -> List[SourceConnection]:
        """Get all source connections for a collection."""
        return await self.get_multi_with_stats(
            db,
            ctx=ctx,
            collection_id=readable_collection_id,
            skip=skip,
            limit=limit,
        )

    async def get_by_sync_id(
        self,
        db: AsyncSession,
        *,
        sync_id: UUID,
        ctx: ApiContext,
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
        await self._validate_organization_access(ctx, source_connection.organization_id)
        return source_connection


# Singleton instance
source_connection = CRUDSourceConnection(SourceConnection)
