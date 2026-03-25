"""Temporal schedule service.

Creates, updates, and deletes Temporal schedules for sync workflows.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from croniter import croniter
from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleSpec,
    ScheduleState,
    ScheduleUpdate,
    ScheduleUpdateInput,
)
from temporalio.common import SearchAttributeKey, SearchAttributePair, TypedSearchAttributes
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
from airweave.domains.temporal import schedule_ids as sched_ids
from airweave.domains.temporal.client import get_client as get_temporal_client
from airweave.domains.temporal.exceptions import InvalidCronExpressionError
from airweave.domains.temporal.protocols import TemporalScheduleServiceProtocol
from airweave.domains.temporal.types import ScheduleInfo
from airweave.domains.temporal.workflows import (
    APIKeyCleanupWorkflow,
    CleanupStuckSyncJobsWorkflow,
    RunSourceConnectionWorkflow,
)
from airweave.domains.temporal.workflows.api_key_notifications import (
    APIKeyExpirationCheckWorkflow,
)

# Schedule ID prefixes for the three schedule types per sync.
SCHEDULE_PREFIXES = ("sync-", "minute-sync-", "daily-cleanup-")

# Custom Temporal search attribute for linking schedules to syncs.
SYNC_ID_SEARCH_ATTRIBUTE = SearchAttributeKey.for_keyword("SyncId")

_MINUTE_LEVEL_RE = re.compile(r"^(\*/([1-5]?\d)|([0-5]?\d)) \* \* \* \*$")


@dataclass(frozen=True)
class ScheduleTypeSpec:
    """One schedule to create. A cron pattern may require multiple."""

    schedule_type: str  # "regular", "minute", or "cleanup"
    force_full_sync: bool = False
    cron_override: Optional[str] = None  # None = use the user's cron


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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _get_client(self) -> Client:
        """Get the Temporal client (module-level singleton handles caching)."""
        return await get_temporal_client()

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
            schedule_id = sched_ids.minute_schedule_id(sync_id)
            jitter = timedelta(seconds=10)
            workflow_id_prefix = "minute-sync-workflow"
            note = f"Minute-level sync schedule for sync {sync_id}"
            sync_type = "incremental"
        elif schedule_type == "cleanup":
            schedule_id = sched_ids.cleanup_schedule_id(sync_id)
            jitter = timedelta(minutes=30)
            workflow_id_prefix = "daily-cleanup-workflow"
            note = f"Daily cleanup schedule for sync {sync_id}"
            sync_type = "full"
        else:
            schedule_id = sched_ids.sync_schedule_id(sync_id)
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
            search_attributes=TypedSearchAttributes(
                [
                    SearchAttributePair(SYNC_ID_SEARCH_ATTRIBUTE, str(sync_id)),
                ]
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
            raise InvalidCronExpressionError(cron_expression)

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
        collection_dict = schemas.CollectionRecord.model_validate(
            collection, from_attributes=True
        ).model_dump(mode="json")
        connection_dict = schemas.Connection.model_validate(
            connection_model, from_attributes=True
        ).model_dump(mode="json")

        return sync_dict, collection_dict, connection_dict

    @staticmethod
    def _schedule_specs_for_cron(cron_schedule: str) -> list[ScheduleTypeSpec]:
        """Return all schedule specs required for a cron pattern.

        Minute-level crons produce incremental syncs that skip orphan cleanup.
        A daily forced-full-sync companion ensures orphans are cleaned up.
        Regular crons do full traversals each run — cleanup happens naturally.
        """
        match = _MINUTE_LEVEL_RE.match(cron_schedule)
        is_minute = match and ((match.group(2) and int(match.group(2)) < 60) or match.group(3))

        if is_minute:
            now = datetime.now(timezone.utc)
            daily_cleanup_cron = f"{now.minute} {(now.hour + 12) % 24} * * *"
            return [
                ScheduleTypeSpec(schedule_type="minute"),
                ScheduleTypeSpec(
                    schedule_type="cleanup",
                    force_full_sync=True,
                    cron_override=daily_cleanup_cron,
                ),
            ]
        return [ScheduleTypeSpec(schedule_type="regular")]

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
            raise InvalidCronExpressionError(cron_schedule)

        sync = await self._sync_repo.get_without_connections(db, sync_id, ctx)
        if not sync:
            raise ValueError(f"Sync {sync_id} not found")

        # If the sync already has a schedule in Temporal, tear down all
        # existing schedules and recreate from scratch.  A simple cron update
        # is insufficient because the schedule *type* may change (e.g.
        # regular ↔ minute-level), which requires adding/removing companion
        # cleanup schedules.
        if sync.temporal_schedule_id:
            status = await self._check_schedule_exists(sync.temporal_schedule_id)
            if status["exists"]:
                await self.delete_all_schedules_for_sync(sync_id, db, ctx)
            else:
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

        specs = self._schedule_specs_for_cron(cron_schedule)
        primary_schedule_id: str = ""

        for i, spec in enumerate(specs):
            sid = await self._create_schedule(
                sync_id=sync_id,
                cron_expression=spec.cron_override or cron_schedule,
                sync_dict=sync_dict,
                collection_dict=collection_dict,
                connection_dict=connection_dict,
                db=db,
                ctx=ctx,
                schedule_type=spec.schedule_type,
                force_full_sync=spec.force_full_sync,
                uow=uow,
            )
            if i == 0:
                primary_schedule_id = sid

        logger.info(
            f"Created {len(specs)} schedule(s) for sync {sync_id}: "
            f"{[s.schedule_type for s in specs]}"
        )
        return primary_schedule_id

    async def delete_all_schedules_for_sync(
        self,
        sync_id: UUID,
        db: AsyncSession,
        ctx: ApiContext,
    ) -> None:
        """Delete all schedules (regular + minute + daily cleanup) for a sync."""
        for sid in sched_ids.all_schedule_ids(sync_id):
            try:
                await self._delete_schedule_by_id(sid, sync_id, db, ctx)
            except Exception as e:
                logger.info(f"Schedule {sid} not deleted (may not exist): {e}")

    async def delete_schedule_handle(self, schedule_id: str) -> None:
        """Delete a Temporal schedule by ID without touching the DB.

        Ignores not-found errors. Used by activities and ORM listeners
        where the DB record is already gone.
        """
        try:
            client = await self._get_client()
            handle = client.get_schedule_handle(schedule_id)
            await handle.delete()
            logger.info(f"Deleted schedule handle {schedule_id}")
        except RPCError as e:
            if e.status == RPCStatusCode.NOT_FOUND:
                logger.debug(f"Schedule {schedule_id} not found (already deleted)")
            else:
                raise
        except Exception as e:
            logger.info(f"Schedule handle {schedule_id} not deleted: {e}")

    async def pause_schedules_for_sync(
        self,
        sync_id: UUID,
        *,
        reason: str = "",
    ) -> None:
        """Pause all Temporal schedules for a sync."""
        client = await self._get_client()

        for prefix in SCHEDULE_PREFIXES:
            schedule_id = f"{prefix}{sync_id}"
            try:
                handle = client.get_schedule_handle(schedule_id)
                await handle.pause(note=reason or "Credential error")
                logger.info(f"Paused schedule {schedule_id}")
            except RPCError as e:
                if e.status == RPCStatusCode.NOT_FOUND:
                    logger.debug(f"Schedule {schedule_id} not found (skipping pause)")
                else:
                    logger.warning(f"Failed to pause schedule {schedule_id}: {e}")
            except Exception as e:
                logger.warning(f"Failed to pause schedule {schedule_id}: {e}")

    async def unpause_schedules_for_sync(
        self,
        sync_id: UUID,
    ) -> None:
        """Unpause all Temporal schedules for a sync."""
        client = await self._get_client()

        for prefix in SCHEDULE_PREFIXES:
            schedule_id = f"{prefix}{sync_id}"
            try:
                handle = client.get_schedule_handle(schedule_id)
                await handle.unpause()
                logger.info(f"Unpaused schedule {schedule_id}")
            except RPCError as e:
                if e.status == RPCStatusCode.NOT_FOUND:
                    logger.debug(f"Schedule {schedule_id} not found (skipping unpause)")
                else:
                    logger.warning(f"Failed to unpause schedule {schedule_id}: {e}")
            except Exception as e:
                logger.warning(f"Failed to unpause schedule {schedule_id}: {e}")

    async def get_schedules_for_sync(self, sync_id: UUID) -> list[ScheduleInfo]:
        """Return schedule metadata for a sync via the SyncId search attribute."""
        client = await self._get_client()
        query = f'{SYNC_ID_SEARCH_ATTRIBUTE.name} = "{sync_id}"'
        schedules: list[ScheduleInfo] = []
        async for s in await client.list_schedules(query=query):
            schedule_type = "unknown"
            for prefix in SCHEDULE_PREFIXES:
                if s.id.startswith(prefix):
                    schedule_type = prefix.rstrip("-")
                    break

            next_times = s.info.next_action_times if s.info else []
            schedules.append(
                ScheduleInfo(
                    schedule_id=s.id,
                    schedule_type=schedule_type,
                    paused=s.schedule.state.paused,
                    note=s.schedule.state.note or "",
                    next_action_at=next_times[0].isoformat() if next_times else None,
                    num_recent_actions=len(s.info.recent_actions) if s.info else 0,
                )
            )
        return schedules

    async def ensure_system_schedules(self) -> None:
        """Create system-level singleton schedules if they don't already exist.

        Covers the stuck-job cleanup schedule and the API key expiration
        notification schedule. Called once during API server startup.
        """
        client = await self._get_client()

        await self._ensure_singleton_schedule(
            client=client,
            schedule_id="cleanup-stuck-sync-jobs",
            workflow_cls=CleanupStuckSyncJobsWorkflow,
            workflow_id="cleanup-workflow",
            interval=timedelta(seconds=150),
            note="Periodic cleanup of stuck sync jobs",
        )

        await self._ensure_singleton_schedule(
            client=client,
            schedule_id="api-key-expiration-notifications",
            workflow_cls=APIKeyExpirationCheckWorkflow,
            workflow_id="api-key-notification-workflow",
            interval=timedelta(days=1),
            note="API key expiration notifications (runs every day)",
        )

        await self._ensure_singleton_schedule(
            client=client,
            schedule_id="api-key-cleanup",
            workflow_cls=APIKeyCleanupWorkflow,
            workflow_id="api-key-cleanup-workflow",
            interval=timedelta(days=1),
            note="Revoked key deletion, expired status transitions, usage log pruning",
        )

    async def _ensure_singleton_schedule(
        self,
        client: Client,
        schedule_id: str,
        workflow_cls: type,
        workflow_id: str,
        interval: timedelta,
        note: str,
    ) -> None:
        """Create a singleton schedule if it doesn't already exist."""
        try:
            handle = client.get_schedule_handle(schedule_id)
            await handle.describe()
            logger.info(f"System schedule {schedule_id} already exists")
            return
        except RPCError as e:
            if e.status != RPCStatusCode.NOT_FOUND:
                raise
        except Exception:
            raise

        logger.info(f"Creating system schedule {schedule_id}")
        await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    workflow_cls.run,
                    id=workflow_id,
                    task_queue=settings.TEMPORAL_TASK_QUEUE,
                ),
                spec=ScheduleSpec(
                    intervals=[ScheduleIntervalSpec(every=interval)],
                ),
                state=ScheduleState(note=note, paused=False),
            ),
        )
        logger.info(f"Created system schedule {schedule_id}")
