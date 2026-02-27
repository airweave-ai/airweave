"""Reimplemented Temporal schedule service.

Replaces platform/temporal/schedule_service.py singleton. Uses injected
repos instead of direct crud.* calls and removes the
source_connection_helpers dependency.

# [code blue] platform/temporal/schedule_service.py can be deleted once
# all consumers are migrated to use this via the container.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from croniter import croniter
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
    ScheduleState,
    ScheduleUpdate,
    ScheduleUpdateInput,
)
from temporalio.service import RPCError, RPCStatusCode

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.source_connections.protocols import (
    SourceConnectionRepositoryProtocol,
)
from airweave.domains.syncs.protocols import SyncRepositoryProtocol
from airweave.domains.temporal.protocols import TemporalScheduleServiceProtocol
from airweave.platform.temporal.client import temporal_client
from airweave.platform.temporal.workflows import RunSourceConnectionWorkflow

_MINUTE_LEVEL_RE = re.compile(r"^(\*/([1-5]?\d)|([0-5]?\d)) \* \* \* \*$")


class TemporalScheduleService(TemporalScheduleServiceProtocol):
    """Manages Temporal schedules: create/update and delete."""

    def __init__(
        self,
        sync_repo: SyncRepositoryProtocol,
        sc_repo: SourceConnectionRepositoryProtocol,
        collection_repo: CollectionRepositoryProtocol,
        connection_repo: ConnectionRepositoryProtocol,
    ) -> None:
        """Initialize with injected repositories."""
        self._sync_repo = sync_repo
        self._sc_repo = sc_repo
        self._collection_repo = collection_repo
        self._connection_repo = connection_repo
        self._client: Optional[Client] = None

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_client(self) -> Client:
        """Get (or cache) the Temporal client."""
        if self._client is None:
            self._client = await temporal_client.get_client()
        return self._client

    async def _check_schedule_exists(self, schedule_id: str) -> dict:
        """Check if a schedule exists and is running.

        Returns dict with 'exists', 'running', and 'schedule_info' keys.
        """
        client = await self._get_client()
        try:
            handle = client.get_schedule_handle(schedule_id)
            desc = await handle.describe()
            return {
                "exists": True,
                "running": not desc.schedule.state.paused,
                "schedule_info": {
                    "schedule_id": schedule_id,
                    "cron_expressions": desc.schedule.spec.cron_expressions,
                    "paused": desc.schedule.state.paused,
                },
            }
        except RPCError as e:
            if e.status == RPCStatusCode.NOT_FOUND:
                return {"exists": False, "running": False, "schedule_info": None}
            raise

    async def _create_schedule(
        self,
        sync_id: UUID,
        cron_expression: str,
        sync_dict: dict,
        collection_dict: dict,
        connection_dict: dict,
        db: AsyncSession,
        ctx: ApiContext,
        access_token: Optional[str] = None,
        schedule_type: str = "regular",
        force_full_sync: bool = False,
        uow: Optional[UnitOfWork] = None,
    ) -> str:
        """Create a Temporal schedule of the given type.

        Returns the schedule ID.
        """
        client = await self._get_client()

        if schedule_type == "minute":
            schedule_id = f"minute-sync-{sync_id}"
            jitter = timedelta(seconds=10)
            workflow_id_prefix = "minute-sync-workflow"
            note = f"Minute-level sync schedule for sync {sync_id}"
            sync_type = "incremental"
        elif schedule_type == "cleanup":
            schedule_id = f"daily-cleanup-{sync_id}"
            jitter = timedelta(minutes=30)
            workflow_id_prefix = "daily-cleanup-workflow"
            note = f"Daily cleanup schedule for sync {sync_id}"
            sync_type = "full"
        else:
            schedule_id = f"sync-{sync_id}"
            jitter = timedelta(minutes=5)
            workflow_id_prefix = "sync-workflow"
            note = f"Regular sync schedule for sync {sync_id}"
            sync_type = "full"

        status = await self._check_schedule_exists(schedule_id)
        if status["exists"]:
            logger.info(f"Schedule {schedule_id} already exists for sync {sync_id}")
            return schedule_id

        workflow_args: list = [
            sync_dict,
            None,  # no pre-created sync job for scheduled runs
            collection_dict,
            connection_dict,
            ctx.to_serializable_dict(),
            access_token,
        ]
        if force_full_sync:
            workflow_args.append(True)

        await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    RunSourceConnectionWorkflow.run,
                    args=workflow_args,
                    id=f"{workflow_id_prefix}-{sync_id}",
                    task_queue=settings.TEMPORAL_TASK_QUEUE,
                ),
                spec=ScheduleSpec(
                    cron_expressions=[cron_expression],
                    start_at=datetime.now(timezone.utc),
                    end_at=None,
                    jitter=jitter,
                ),
                state=ScheduleState(note=note, paused=False),
            ),
        )

        if schedule_type != "cleanup":
            sync_obj = await self._sync_repo.get_without_connections(db, sync_id, ctx)
            await self._sync_repo.update(
                db,
                sync_obj,
                {
                    "temporal_schedule_id": schedule_id,
                    "sync_type": sync_type,
                    "status": "ACTIVE",
                    "cron_schedule": cron_expression,
                },
                ctx,
                uow=uow,
            )

        logger.info(f"Created {schedule_type} schedule {schedule_id} for sync {sync_id}")
        return schedule_id

    async def _update_schedule(
        self,
        schedule_id: str,
        cron_expression: str,
        sync_id: UUID,
        db: AsyncSession,
        uow: UnitOfWork,
        ctx: ApiContext,
    ) -> None:
        """Update an existing Temporal schedule with a new cron expression."""
        if not croniter.is_valid(cron_expression):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid CRON expression: {cron_expression}",
            )

        client = await self._get_client()
        handle = client.get_schedule_handle(schedule_id)

        def _updater(input: ScheduleUpdateInput) -> ScheduleUpdate:
            schedule = input.description.schedule
            schedule.spec = ScheduleSpec(
                cron_expressions=[cron_expression],
                start_at=datetime.now(timezone.utc),
                end_at=None,
                jitter=timedelta(seconds=10),
            )
            return ScheduleUpdate(schedule=schedule)

        await handle.update(_updater)

        match = _MINUTE_LEVEL_RE.match(cron_expression)
        sync_type = "full"
        if match:
            if match.group(2):
                interval = int(match.group(2))
                if interval < 60:
                    sync_type = "incremental"
            elif match.group(3):
                sync_type = "incremental"

        sync_obj = await self._sync_repo.get_without_connections(db, sync_id, ctx)
        await self._sync_repo.update(
            db,
            sync_obj,
            {"cron_schedule": cron_expression, "sync_type": sync_type},
            ctx,
            uow=uow,
        )

        logger.info(f"Updated schedule {schedule_id} with cron {cron_expression}")

    async def _delete_schedule_by_id(
        self,
        schedule_id: str,
        sync_id: UUID,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> None:
        """Delete a single Temporal schedule and clear sync DB fields."""
        client = await self._get_client()
        handle = client.get_schedule_handle(schedule_id)
        await handle.delete()

        sync_obj = await self._sync_repo.get_without_connections(db, sync_id, ctx)
        await self._sync_repo.update(
            db,
            sync_obj,
            {
                "temporal_schedule_id": None,
                "cron_schedule": None,
                "sync_type": "full",
            },
            ctx,
        )
        logger.info(f"Deleted schedule {schedule_id}")

    async def _gather_schedule_data(
        self,
        sync_id: UUID,
        db: AsyncSession,
        ctx: ApiContext,
        collection_readable_id: Optional[str] = None,
        connection_id: Optional[UUID] = None,
    ) -> tuple[dict, dict, dict]:
        """Load sync/collection/connection and return serialised dicts."""
        sync_with_conns = await self._sync_repo.get(db, sync_id, ctx)

        source_connection = await self._sc_repo.get_by_sync_id(db, sync_id, ctx)
        resolved_collection_readable_id = collection_readable_id
        resolved_connection_id = connection_id
        if source_connection:
            resolved_collection_readable_id = source_connection.readable_collection_id
            resolved_connection_id = source_connection.connection_id
        elif resolved_collection_readable_id is None or resolved_connection_id is None:
            raise ValueError(f"No source connection found for sync {sync_id}")

        collection = await self._collection_repo.get_by_readable_id(
            db, resolved_collection_readable_id, ctx
        )
        if not collection:
            raise ValueError(f"No collection found for sync {sync_id}")

        if not resolved_connection_id:
            raise ValueError(f"Source connection for sync {sync_id} has no connection_id")
        connection_model = await self._connection_repo.get(db, resolved_connection_id, ctx)
        if not connection_model:
            raise ValueError(f"Connection {resolved_connection_id} not found")

        sync_dict = schemas.Sync.model_validate(sync_with_conns, from_attributes=True).model_dump(
            mode="json"
        )
        collection_dict = schemas.Collection.model_validate(
            collection, from_attributes=True
        ).model_dump(mode="json")
        connection_dict = schemas.Connection.model_validate(
            connection_model, from_attributes=True
        ).model_dump(mode="json")

        return sync_dict, collection_dict, connection_dict

    @staticmethod
    def _schedule_type_for_cron(cron_schedule: str) -> str:
        """Return 'minute' or 'regular' based on the cron pattern."""
        match = _MINUTE_LEVEL_RE.match(cron_schedule)
        if match:
            if match.group(2) and int(match.group(2)) < 60:
                return "minute"
            if match.group(3):
                return "minute"
        return "regular"

    # ------------------------------------------------------------------
    # Public API (protocol surface)
    # ------------------------------------------------------------------

    async def create_or_update_schedule(
        self,
        sync_id: UUID,
        cron_schedule: str,
        db: AsyncSession,
        ctx: ApiContext,
        uow: UnitOfWork,
        collection_readable_id: Optional[str] = None,
        connection_id: Optional[UUID] = None,
    ) -> str:
        """Create or update a Temporal schedule for a sync.

        Returns the schedule ID.
        """
        if not croniter.is_valid(cron_schedule):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid CRON expression: {cron_schedule}",
            )

        sync = await self._sync_repo.get_without_connections(db, sync_id, ctx)
        if not sync:
            raise ValueError(f"Sync {sync_id} not found")

        # If the sync already has a schedule in Temporal, update it
        if sync.temporal_schedule_id:
            status = await self._check_schedule_exists(sync.temporal_schedule_id)
            if status["exists"]:
                await self._update_schedule(
                    schedule_id=sync.temporal_schedule_id,
                    cron_expression=cron_schedule,
                    sync_id=sync_id,
                    db=db,
                    uow=uow,
                    ctx=ctx,
                )
                return sync.temporal_schedule_id
            logger.warning(
                f"Schedule {sync.temporal_schedule_id} not found in Temporal "
                f"for sync {sync_id}, will create new one"
            )

        sync_dict, collection_dict, connection_dict = await self._gather_schedule_data(
            sync_id,
            db,
            ctx,
            collection_readable_id=collection_readable_id,
            connection_id=connection_id,
        )

        schedule_id = await self._create_schedule(
            sync_id=sync_id,
            cron_expression=cron_schedule,
            sync_dict=sync_dict,
            collection_dict=collection_dict,
            connection_dict=connection_dict,
            db=db,
            ctx=ctx,
            schedule_type=self._schedule_type_for_cron(cron_schedule),
            uow=uow,
        )

        logger.info(f"Created new schedule {schedule_id} for sync {sync_id}")
        return schedule_id

    async def delete_all_schedules_for_sync(
        self,
        sync_id: UUID,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> None:
        """Delete all schedules (regular + minute + daily cleanup) for a sync."""
        for prefix in ("sync-", "minute-sync-", "daily-cleanup-"):
            schedule_id = f"{prefix}{sync_id}"
            try:
                await self._delete_schedule_by_id(schedule_id, sync_id, db, ctx)
            except Exception as e:
                logger.info(f"Schedule {schedule_id} not deleted (may not exist): {e}")
