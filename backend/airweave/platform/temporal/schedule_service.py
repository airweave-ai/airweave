"""Temporal schedule service for managing minute-level sync schedules."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
    ScheduleState,
)

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.crud.crud_sync import sync as sync_crud
from airweave.platform.temporal.client import temporal_client
from airweave.platform.temporal.workflows import RunSourceConnectionWorkflow


class TemporalScheduleService:
    """Service for managing Temporal schedules for minute-level syncs."""

    def __init__(self):
        """Initialize the Temporal schedule service."""
        self._client: Optional[Client] = None

    async def _get_client(self) -> Client:
        """Get the Temporal client."""
        if self._client is None:
            self._client = await temporal_client.get_client()
        return self._client

    async def check_schedule_exists_and_running(self, schedule_id: str) -> dict:
        """Check if a schedule exists and is running.

        Args:
            schedule_id: The schedule ID to check

        Returns:
            Dictionary with 'exists' and 'running' boolean flags, and schedule info if exists
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
                    # Note: next_run_time and last_run_time are not available on ScheduleState
                    # They would need to be accessed differently if needed
                },
            }
        except Exception as e:
            logger.error(f"Error checking schedule {schedule_id}: {e}")
            return {"exists": False, "running": False, "schedule_info": None}

    async def create_minute_level_schedule(
        self,
        sync_id: UUID,
        cron_expression: str,
        sync_dict: dict,
        sync_dag_dict: dict,
        collection_dict: dict,
        source_connection_dict: dict,
        user_dict: dict,
        db: AsyncSession,
        ctx,
        access_token: Optional[str] = None,
    ) -> str:
        """Create a minute-level schedule for incremental sync.

        Args:
            sync_id: The sync ID
            cron_expression: Cron expression for the schedule (e.g., "*/1 * * * *")
            sync_dict: The sync configuration as dict
            sync_job_dict: The sync job as dict
            sync_dag_dict: The sync DAG as dict
            collection_dict: The collection as dict
            source_connection_dict: The source connection as dict
            user_dict: The current user as dict
            db: Database session
            ctx: Authentication context
            access_token: Optional access token

        Returns:
            The schedule ID
        """
        client = await self._get_client()

        # Create schedule ID using sync ID
        schedule_id = f"minute-sync-{sync_id}"

        # Check if schedule already exists and is running
        schedule_status = await self.check_schedule_exists_and_running(schedule_id)

        if schedule_status["exists"]:
            if schedule_status["running"]:
                logger.info(
                    f"Schedule {schedule_id} already exists and is running for sync {sync_id}"
                )
                return schedule_id
            else:
                logger.info(
                    f"Schedule {schedule_id} exists but is paused for sync {sync_id}. "
                    f"Returning existing schedule ID without resuming."
                )
                return schedule_id

        # Create schedule spec with cron expression
        schedule_spec = ScheduleSpec(
            cron_expressions=[cron_expression],
            # Start immediately (but schedule will be paused initially)
            start_at=datetime.now(timezone.utc),
            # No end time (runs indefinitely)
            end_at=None,
            # Jitter to avoid thundering herd
            jitter=timedelta(seconds=10),
        )

        # Create the schedule in paused state
        await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    RunSourceConnectionWorkflow.run,
                    args=[
                        sync_dict,
                        None,  # No pre-created sync job for scheduled runs
                        sync_dag_dict,
                        collection_dict,
                        source_connection_dict,
                        user_dict,
                        access_token,
                    ],
                    id=f"minute-sync-workflow-{sync_id}",
                    task_queue=settings.TEMPORAL_TASK_QUEUE,
                ),
                spec=schedule_spec,
                state=ScheduleState(
                    note=f"Minute-level sync schedule for sync {sync_id} (paused initially)",
                    paused=True,
                ),
            ),
        )

        # Update the sync record in the database
        # Get the sync model object (not schema) for updating
        sync_obj = await sync_crud.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        await sync_crud.update(
            db=db,
            db_obj=sync_obj,
            obj_in={
                "temporal_schedule_id": schedule_id,
                "minute_level_cron_schedule": cron_expression,
                "sync_type": "incremental",
                "status": "INACTIVE",  # Mark as inactive since schedule is paused
            },
            ctx=ctx,
        )

        logger.info(
            f"Created minute-level schedule {schedule_id} for sync {sync_id} (paused initially)"
        )
        return schedule_id

    async def create_daily_cleanup_schedule(
        self,
        sync_id: UUID,
        cron_expression: str,  # e.g., "0 2 * * *" for 2 AM daily
        sync_dict: dict,
        sync_dag_dict: dict,
        collection_dict: dict,
        source_connection_dict: dict,
        user_dict: dict,
        db: AsyncSession,
        ctx,
        access_token: Optional[str] = None,
    ) -> str:
        """Create a daily cleanup schedule for full sync with deletion.

        Args:
            sync_id: The sync ID
            cron_expression: Cron expression for daily schedule (e.g., "0 2 * * *")
            sync_dict: The sync configuration as dict
            sync_dag_dict: The sync DAG as dict
            collection_dict: The collection as dict
            source_connection_dict: The source connection as dict
            user_dict: The current user as dict
            db: Database session
            ctx: Authentication context
            access_token: Optional access token

        Returns:
            The schedule ID
        """
        client = await self._get_client()

        # Create schedule ID using sync ID
        schedule_id = f"daily-cleanup-{sync_id}"

        # Check if schedule already exists
        schedule_status = await self.check_schedule_exists_and_running(schedule_id)

        if schedule_status["exists"]:
            if schedule_status["running"]:
                logger.info(
                    f"Daily cleanup schedule {schedule_id} already exists and is running "
                    f"for sync {sync_id}"
                )
                return schedule_id
            else:
                logger.info(
                    f"Daily cleanup schedule {schedule_id} exists but is paused for sync {sync_id}."
                )
                return schedule_id

        # Create schedule spec with daily cron expression
        schedule_spec = ScheduleSpec(
            cron_expressions=[cron_expression],
            start_at=datetime.now(timezone.utc),
            end_at=None,
            jitter=timedelta(minutes=30),  # More jitter for daily runs
        )

        # Create the schedule in paused state
        await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    RunSourceConnectionWorkflow.run,
                    args=[
                        sync_dict,
                        None,  # No pre-created sync job for scheduled runs
                        sync_dag_dict,
                        collection_dict,
                        source_connection_dict,
                        user_dict,
                        access_token,
                        True,  # force_full_sync=True for cleanup
                    ],
                    id=f"daily-cleanup-workflow-{sync_id}",
                    task_queue=settings.TEMPORAL_TASK_QUEUE,
                ),
                spec=schedule_spec,
                state=ScheduleState(
                    note=f"Daily cleanup schedule for sync {sync_id} (paused initially)",
                    paused=True,
                ),
            ),
        )

        logger.info(
            f"Created daily cleanup schedule {schedule_id} for sync {sync_id} (paused initially)"
        )
        return schedule_id

    async def update_schedule(
        self,
        schedule_id: str,
        cron_expression: str,
        sync_id: UUID,
        user_dict: dict,
        db: AsyncSession,
        ctx,
    ) -> None:
        """Update an existing schedule with a new cron expression.

        Args:
            schedule_id: The schedule ID to update
            cron_expression: New cron expression
            sync_id: The sync ID
            user_dict: The current user as dict
            db: Database session
            ctx: Authentication context
        """
        client = await self._get_client()

        # Get the schedule handle
        handle = client.get_schedule_handle(schedule_id)

        # Update the schedule spec
        await handle.update(
            ScheduleSpec(
                cron_expressions=[cron_expression],
                start_at=datetime.now(timezone.utc),
                end_at=None,
                jitter=timedelta(seconds=10),
            )
        )

        # Update the sync record in the database
        sync_obj = await sync_crud.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        await sync_crud.update(
            db=db,
            db_obj=sync_obj,
            obj_in={"minute_level_cron_schedule": cron_expression},
            ctx=ctx,
        )

        logger.info(f"Updated schedule {schedule_id} with cron expression {cron_expression}")

    async def pause_schedule(
        self, schedule_id: str, sync_id: UUID, user_dict: dict, db: AsyncSession, ctx
    ) -> None:
        """Pause a schedule.

        Args:
            schedule_id: The schedule ID to pause
            sync_id: The sync ID
            user_dict: The current user as dict
            db: Database session
            ctx: Authentication context
        """
        client = await self._get_client()
        handle = client.get_schedule_handle(schedule_id)

        await handle.pause()

        # Update sync status to indicate paused schedule
        sync_obj = await sync_crud.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        await sync_crud.update(
            db=db,
            db_obj=sync_obj,
            obj_in={"status": "INACTIVE"},
            ctx=ctx,
        )

        logger.info(f"Paused schedule {schedule_id}")

    async def resume_schedule(
        self, schedule_id: str, sync_id: UUID, user_dict: dict, db: AsyncSession, ctx
    ) -> None:
        """Resume a paused schedule.

        Args:
            schedule_id: The schedule ID to resume
            sync_id: The sync ID
            user_dict: The current user as dict
            db: Database session
            ctx: Authentication context
        """
        client = await self._get_client()
        handle = client.get_schedule_handle(schedule_id)

        await handle.unpause()

        # Update sync status to indicate active schedule
        sync_obj = await sync_crud.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        await sync_crud.update(
            db=db,
            db_obj=sync_obj,
            obj_in={"status": "ACTIVE"},
            ctx=ctx,
        )

        logger.info(f"Resumed schedule {schedule_id}")

    async def delete_schedule(
        self, schedule_id: str, sync_id: UUID, user_dict: dict, db: AsyncSession, ctx
    ) -> None:
        """Delete a schedule.

        Args:
            schedule_id: The schedule ID to delete
            sync_id: The sync ID
            user_dict: The current user as dict
            db: Database session
            ctx: Authentication context
        """
        client = await self._get_client()
        handle = client.get_schedule_handle(schedule_id)

        await handle.delete()

        # Clear the temporal schedule fields from the sync record
        sync_obj = await sync_crud.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        await sync_crud.update(
            db=db,
            db_obj=sync_obj,
            obj_in={
                "temporal_schedule_id": None,
                "minute_level_cron_schedule": None,
                "sync_type": "full",
            },
            ctx=ctx,
        )

        logger.info(f"Deleted schedule {schedule_id}")

    async def delete_all_schedules_for_sync(self, sync_id: UUID, db: AsyncSession, ctx) -> None:
        """Delete all schedules associated with a sync (minute + daily).

        This attempts to delete both the minute-level and daily-cleanup schedules
        based on naming conventions. It ignores missing schedules and continues.
        """
        user_dict: dict = {}

        # Minute-level schedule (also stored in Sync.temporal_schedule_id)
        minute_schedule_id = f"minute-sync-{sync_id}"
        try:
            await self.delete_schedule(minute_schedule_id, sync_id, user_dict, db, ctx)
        except Exception as e:
            logger.info(
                f"Minute-level schedule {minute_schedule_id} not deleted (may not exist): {e}"
            )

        # Daily cleanup schedule
        daily_schedule_id = f"daily-cleanup-{sync_id}"
        try:
            await self.delete_schedule(daily_schedule_id, sync_id, user_dict, db, ctx)
        except Exception as e:
            logger.info(
                f"Daily cleanup schedule {daily_schedule_id} not deleted (may not exist): {e}"
            )

    async def get_schedule_info(self, schedule_id: str) -> dict:
        """Get information about a schedule.

        Args:
            schedule_id: The schedule ID

        Returns:
            Schedule information as dict
        """
        client = await self._get_client()
        handle = client.get_schedule_handle(schedule_id)

        desc = await handle.describe()

        return {
            "schedule_id": schedule_id,
            "cron_expressions": list(desc.schedule.spec.cron_expressions),  # Convert to list
            "paused": desc.schedule.state.paused,
            # Note: next_run_time and last_run_time are not available on ScheduleState
            # They would need to be accessed differently if needed
        }

    async def delete_schedule_handle(self, schedule_id: str) -> None:
        """Delete a schedule by ID without touching the database.

        Useful for model-level cascade deletions where the DB row is already
        being removed and we only need to remove Temporal state.
        """
        try:
            client = await self._get_client()
            handle = client.get_schedule_handle(schedule_id)
            await handle.delete()
            logger.info(f"Deleted schedule handle {schedule_id}")
        except Exception as e:
            logger.info(f"Schedule handle {schedule_id} not deleted (may not exist): {e}")

    async def get_sync_schedule_info(self, sync_id: UUID, db: AsyncSession, ctx) -> Optional[dict]:
        """Get schedule information for a specific sync.

        Args:
            sync_id: The sync ID
            db: Database session
            ctx: Authentication context

        Returns:
            Schedule information if exists, None otherwise
        """
        sync = await sync_crud.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        if not sync or not sync.temporal_schedule_id:
            return None

        try:
            schedule_info = await self.get_schedule_info(sync.temporal_schedule_id)
            return {
                **schedule_info,
                "sync_id": str(sync_id),
                "minute_level_cron_schedule": sync.minute_level_cron_schedule,
                "sync_type": sync.sync_type,
            }
        except Exception as e:
            logger.error(f"Error getting schedule info for sync {sync_id}: {e}")
            return None


# Singleton instance
temporal_schedule_service = TemporalScheduleService()
