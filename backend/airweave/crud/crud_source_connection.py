"""CRUD operations for source connections."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.logging import logger
from airweave.core.shared_models import SourceConnectionStatus, SyncJobStatus
from airweave.models.source_connection import SourceConnection
from airweave.models.sync_job import SyncJob
from airweave.schemas.source_connection import SourceConnectionCreate, SourceConnectionUpdate

from ._base_organization import CRUDBaseOrganization


class CRUDSourceConnection(
    CRUDBaseOrganization[SourceConnection, SourceConnectionCreate, SourceConnectionUpdate]
):
    """CRUD operations for source connections."""

    async def get_status(
        self, source_connection: SourceConnection, latest_sync_job: Optional[SyncJob] = None
    ) -> SourceConnectionStatus:
        """Determine the ephemeral status of a source connection based on its sync job status.

        Args:
            source_connection: The source connection
            latest_sync_job: Optional pre-fetched latest sync job

        Returns:
            The derived ephemeral status
        """
        # When no sync job exists yet
        if not source_connection.sync_id or not latest_sync_job:
            return SourceConnectionStatus.ACTIVE

        # Map sync job status to source connection status
        if latest_sync_job.status == SyncJobStatus.FAILED:
            return SourceConnectionStatus.FAILING
        elif latest_sync_job.status == SyncJobStatus.IN_PROGRESS:
            return SourceConnectionStatus.IN_PROGRESS
        else:
            return SourceConnectionStatus.ACTIVE

    async def _attach_latest_sync_job_info(
        self, db: AsyncSession, source_connections: List[SourceConnection]
    ) -> List[SourceConnection]:
        """Attach latest sync job information to source connections.

        Args:
            db: The database session
            source_connections: List of source connections to augment

        Returns:
            The source connections with attached sync job info and status
        """
        if not source_connections:
            return []

        # Get all sync IDs
        sync_ids = [sc.sync_id for sc in source_connections if sc.sync_id]
        if not sync_ids:
            return source_connections

        # Get all sync jobs for the sync_ids to log before filtering
        all_jobs_query = select(
            SyncJob.sync_id, SyncJob.id, SyncJob.status, SyncJob.created_at
        ).where(SyncJob.sync_id.in_(sync_ids))

        all_jobs_result = await db.execute(all_jobs_query)
        all_jobs = list(all_jobs_result.fetchall())

        job_info = [
            {
                "id": str(job.id),
                "sync_id": str(job.sync_id),
                "status": job.status,
                "created_at": job.created_at,
            }
            for job in all_jobs
        ]

        # Get the latest sync job for each sync ID in a single query
        subq = (
            select(
                SyncJob.sync_id,
                SyncJob.id,
                SyncJob.status,
                SyncJob.created_at,
                SyncJob.started_at,
                SyncJob.completed_at,
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

        # Log the query results
        latest_jobs = list(result.fetchall())

        # Create a dictionary of sync_id -> latest sync job info
        sync_job_info = {
            row.sync_id: {
                "id": row.id,
                "status": row.status,
                "started_at": row.started_at,
                "completed_at": row.completed_at,
                "error": row.error,
                "created_at": row.created_at,  # Log created_at as well
            }
            for row in latest_jobs
        }

        # Attach the latest sync job info to each source connection
        for sc in source_connections:
            sc_id = str(sc.id) if hasattr(sc, "id") else "unknown"
            if sc.sync_id and sc.sync_id in sync_job_info:
                job_info = sync_job_info[sc.sync_id]
                sc.latest_sync_job_id = job_info["id"]
                sc.latest_sync_job_status = job_info["status"]
                sc.latest_sync_job_started_at = job_info["started_at"]
                sc.latest_sync_job_completed_at = job_info["completed_at"]
                sc.latest_sync_job_error = job_info["error"] if "error" in job_info else None

                # Set the ephemeral status based on the latest sync job
                job = SyncJob(
                    id=job_info["id"],
                    status=job_info["status"],
                    started_at=job_info["started_at"],
                    completed_at=job_info["completed_at"],
                    sync_id=sc.sync_id,
                )
                sc.status = await self.get_status(sc, job)
            else:
                logger.info(
                    f"Source connection {sc_id} with sync_id {sc.sync_id}: "
                    f"No matching latest job found"
                )
                # No sync job found, set default status
                sc.status = await self.get_status(sc)

        return source_connections

    async def _attach_sync_schedule_info(
        self, db: AsyncSession, source_connections: List[SourceConnection]
    ) -> List[SourceConnection]:
        """Attach sync schedule information to source connections.

        Args:
            db: The database session
            source_connections: List of source connections to augment

        Returns:
            The source connections with attached schedule info
        """
        if not source_connections:
            return []

        # Get all sync IDs
        sync_ids = [sc.sync_id for sc in source_connections if sc.sync_id]
        if not sync_ids:
            return source_connections

        # Get all syncs for these IDs in a single query
        from airweave.models.sync import Sync

        query = select(Sync.id, Sync.cron_schedule, Sync.next_scheduled_run).where(
            Sync.id.in_(sync_ids)
        )
        result = await db.execute(query)
        sync_schedules = {
            row.id: {
                "cron_schedule": row.cron_schedule,
                "next_scheduled_run": row.next_scheduled_run,
            }
            for row in result.fetchall()
        }

        # Attach schedule info to each source connection
        for sc in source_connections:
            if sc.sync_id and sc.sync_id in sync_schedules:
                schedule_info = sync_schedules[sc.sync_id]
                sc.cron_schedule = schedule_info["cron_schedule"]
                sc.next_scheduled_run = schedule_info["next_scheduled_run"]

        return source_connections

    async def get(self, db: AsyncSession, id: UUID, ctx: ApiContext) -> Optional[SourceConnection]:
        """Get a source connection by ID with its ephemeral status.

        Args:
            db: The database session
            id: The ID of the source connection
            ctx: The API context

        Returns:
            The source connection with ephemeral status
        """
        # Call parent class method to get the base source connection
        source_connection = await super().get(db, id=id, ctx=ctx)

        if source_connection:
            # Attach latest sync job info and compute status
            source_connection = (await self._attach_latest_sync_job_info(db, [source_connection]))[
                0
            ]
            # Also attach schedule info
            source_connection = (await self._attach_sync_schedule_info(db, [source_connection]))[0]

        return source_connection

    async def get_multi(
        self, db: AsyncSession, *, ctx: ApiContext, skip: int = 0, limit: int = 100
    ) -> List[SourceConnection]:
        """Get all source connections for the current user with ephemeral statuses.

        Args:
            db: The database session
            ctx: The API context
            skip: The number of connections to skip
            limit: The number of connections to return

        Returns:
            A list of source connections with ephemeral statuses
        """
        query = (
            select(self.model)
            .where(self.model.organization_id == ctx.organization.id)
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        source_connections = list(result.scalars().all())

        # Attach latest sync job info and compute statuses
        source_connections = await self._attach_latest_sync_job_info(db, source_connections)
        # Also attach schedule info
        source_connections = await self._attach_sync_schedule_info(db, source_connections)

        return source_connections

    async def get_for_collection(
        self,
        db: AsyncSession,
        *,
        readable_collection_id: str,
        skip: int = 0,
        limit: int = 100,
        ctx: ApiContext,
    ) -> List[SourceConnection]:
        """Get all source connections for a specific collection with ephemeral statuses.

        Args:
            db: The database session
            readable_collection_id: The readable ID of the collection
            ctx: The API context
            skip: The number of source connections to skip
            limit: The maximum number of source connections to return

        Returns:
            A list of source connections with ephemeral statuses
        """
        query = (
            select(self.model)
            .where(
                self.model.readable_collection_id == readable_collection_id,
                self.model.organization_id == ctx.organization.id,
            )
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(query)
        source_connections = list(result.scalars().all())

        # Attach latest sync job info and compute statuses
        source_connections = await self._attach_latest_sync_job_info(db, source_connections)
        # Also attach schedule info
        source_connections = await self._attach_sync_schedule_info(db, source_connections)

        return source_connections

    async def get_by_sync_id(
        self, db: AsyncSession, *, sync_id: UUID, ctx: ApiContext
    ) -> Optional[SourceConnection]:
        """Get a source connection by sync ID.

        Args:
            db: The database session
            sync_id: The ID of the sync
            ctx: The API context

        Returns:
            The source connection for the sync
        """
        query = select(self.model).where(
            self.model.sync_id == sync_id,
            self.model.organization_id == ctx.organization.id,
        )
        result = await db.execute(query)
        source_connection = result.scalar_one_or_none()

        if source_connection:
            # Attach latest sync job info and compute status
            source_connection = (await self._attach_latest_sync_job_info(db, [source_connection]))[
                0
            ]
            # Also attach schedule info
            source_connection = (await self._attach_sync_schedule_info(db, [source_connection]))[0]

        return source_connection

    async def get_for_white_label(
        self, db: AsyncSession, *, white_label_id: UUID, ctx: ApiContext
    ) -> List[SourceConnection]:
        """Get all source connections for a specific white label.

        Args:
            db: The database session
            white_label_id: The ID of the white label
            ctx: The API context

        Returns:
            A list of source connections for the white label
        """
        query = select(self.model).where(
            self.model.white_label_id == white_label_id,
            self.model.organization_id == ctx.organization.id,
        )
        result = await db.execute(query)
        source_connections = list(result.scalars().all())

        # Attach latest sync job info and compute statuses
        source_connections = await self._attach_latest_sync_job_info(db, source_connections)
        # Also attach schedule info
        source_connections = await self._attach_sync_schedule_info(db, source_connections)

        return source_connections


source_connection = CRUDSourceConnection(SourceConnection)
