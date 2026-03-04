"""Temporal schedule service for managing minute-level sync schedules."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

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

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.db.unit_of_work import UnitOfWork
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

    async def _create_schedule(
        self,
        sync_id: UUID,
        cron_expression: str,
        sync_dict: dict,
        collection_dict: dict,
        connection_dict: dict,
        db: AsyncSession,
        ctx,
        access_token: Optional[str] = None,
        schedule_type: str = "regular",  # "regular", "minute", or "cleanup"
        force_full_sync: bool = False,
    ) -> str:
        """Private method to create any type of schedule.

        Args:
            sync_id: The sync ID
            cron_expression: Cron expression for the schedule
            sync_dict: The sync configuration as dict
            collection_dict: The collection as dict
            connection_dict: The connection as dict (Connection schema, NOT SourceConnection)
            db: Database session
            ctx: Authentication context
            access_token: Optional access token
            schedule_type: Type of schedule ("regular", "minute", or "cleanup")
            force_full_sync: Whether to force full sync (for cleanup schedules)

        Returns:
            The schedule ID
        """
        client = await self._get_client()

        # Create schedule ID and parameters based on type
        if schedule_type == "minute":
            schedule_id = f"minute-sync-{sync_id}"
            jitter = timedelta(seconds=10)
            workflow_id_prefix = "minute-sync-workflow"
            note = f"Minute-level sync schedule for sync {sync_id} (paused initially)"
            sync_type = "incremental"
        elif schedule_type == "cleanup":
            schedule_id = f"daily-cleanup-{sync_id}"
            jitter = timedelta(minutes=30)
            workflow_id_prefix = "daily-cleanup-workflow"
            note = f"Daily cleanup schedule for sync {sync_id} (paused initially)"
            sync_type = "full"
        else:  # regular
            schedule_id = f"sync-{sync_id}"
            jitter = timedelta(minutes=5)
            workflow_id_prefix = "sync-workflow"
            note = f"Regular sync schedule for sync {sync_id} (paused initially)"
            sync_type = "full"

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
            start_at=datetime.now(timezone.utc),
            end_at=None,
            jitter=jitter,
        )

        # Build workflow args
        workflow_args = [
            sync_dict,
            None,  # No pre-created sync job for scheduled runs
            collection_dict,
            connection_dict,
            ctx.to_serializable_dict(),  # Use full context dict, not just user_dict
            access_token,
        ]

        # Add force_full_sync for cleanup schedules
        if force_full_sync:
            workflow_args.append(True)

        # Create the schedule in paused state
        await client.create_schedule(
            schedule_id,
            Schedule(
                action=ScheduleActionStartWorkflow(
                    RunSourceConnectionWorkflow.run,
                    args=workflow_args,
                    id=f"{workflow_id_prefix}-{sync_id}",
                    task_queue=settings.TEMPORAL_TASK_QUEUE,
                ),
                spec=schedule_spec,
                state=ScheduleState(
                    note=note,
                    paused=False,
                ),
            ),
        )

        # Update the sync record in the database (only for non-cleanup schedules)
        if schedule_type != "cleanup":
            sync_obj = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
            update_fields = {
                "temporal_schedule_id": schedule_id,
                "sync_type": sync_type,
                "status": "ACTIVE",  # Mark as active since schedule is running
            }

            # Store cron schedule - unified field for all types
            update_fields["cron_schedule"] = cron_expression

            await crud.sync.update(
                db=db,
                db_obj=sync_obj,
                obj_in=update_fields,
                ctx=ctx,
            )

        logger.info(f"Created {schedule_type} schedule {schedule_id} for sync {sync_id} (active)")
        return schedule_id

    async def create_minute_level_schedule(
        self,
        sync_id: UUID,
        cron_expression: str,
        sync_dict: dict,
        collection_dict: dict,
        connection_dict: dict,
        db: AsyncSession,
        ctx,
        access_token: Optional[str] = None,
    ) -> str:
        """Create a minute-level schedule for incremental sync."""
        return await self._create_schedule(
            sync_id=sync_id,
            cron_expression=cron_expression,
            sync_dict=sync_dict,
            collection_dict=collection_dict,
            connection_dict=connection_dict,
            db=db,
            ctx=ctx,
            access_token=access_token,
            schedule_type="minute",
        )

    async def create_regular_schedule(
        self,
        sync_id: UUID,
        cron_expression: str,
        sync_dict: dict,
        collection_dict: dict,
        connection_dict: dict,
        db: AsyncSession,
        ctx,
        access_token: Optional[str] = None,
    ) -> str:
        """Create a regular (e.g., daily) schedule for sync."""
        return await self._create_schedule(
            sync_id=sync_id,
            cron_expression=cron_expression,
            sync_dict=sync_dict,
            collection_dict=collection_dict,
            connection_dict=connection_dict,
            db=db,
            ctx=ctx,
            access_token=access_token,
            schedule_type="regular",
        )

    async def create_daily_cleanup_schedule(
        self,
        sync_id: UUID,
        cron_expression: str,  # e.g., "0 2 * * *" for 2 AM daily
        sync_dict: dict,
        collection_dict: dict,
        connection_dict: dict,
        db: AsyncSession,
        ctx,
        access_token: Optional[str] = None,
    ) -> str:
        """Create a daily cleanup schedule for full sync with deletion.

        Args:
            sync_id: The sync ID
            cron_expression: Cron expression for daily schedule (e.g., "0 2 * * *")
            sync_dict: The sync configuration as dict
            collection_dict: The collection as dict
            connection_dict: The connection as dict (Connection schema, NOT SourceConnection)
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
                        collection_dict,
                        connection_dict,
                        ctx.to_serializable_dict(),  # Use full context dict, not just user_dict
                        access_token,
                        True,  # force_full_sync=True for cleanup
                    ],
                    id=f"daily-cleanup-workflow-{sync_id}",
                    task_queue=settings.TEMPORAL_TASK_QUEUE,
                ),
                spec=schedule_spec,
                state=ScheduleState(
                    note=f"Daily cleanup schedule for sync {sync_id} (active)",
                    paused=False,  # Start active
                ),
            ),
        )

        logger.info(f"Created daily cleanup schedule {schedule_id} for sync {sync_id} (active)")
        return schedule_id

    async def update_schedule(
        self,
        schedule_id: str,
        cron_expression: str,
        sync_id: UUID,
        db: AsyncSession,
        uow: UnitOfWork,
        ctx,
    ) -> None:
        """Update an existing schedule with a new cron expression.

        Args:
            schedule_id: The schedule ID to update
            cron_expression: New cron expression
            sync_id: The sync ID
            db: Database session
            uow: Unit of work
            ctx: Authentication context
        """
        # Validate CRON expression before sending to Temporal
        from croniter import croniter

        if not croniter.is_valid(cron_expression):
            from fastapi import HTTPException

            raise HTTPException(
                status_code=422, detail=f"Invalid CRON expression: {cron_expression}"
            )

        client = await self._get_client()

        # Get the schedule handle
        handle = client.get_schedule_handle(schedule_id)

        # Define the update callback function
        def update_schedule_spec(input: ScheduleUpdateInput) -> ScheduleUpdate:
            """Callback to update the schedule spec with new cron expression."""
            # Get the current schedule from the input
            schedule = input.description.schedule

            # Update the spec with the new cron expression
            schedule.spec = ScheduleSpec(
                cron_expressions=[cron_expression],
                start_at=datetime.now(timezone.utc),
                end_at=None,
                jitter=timedelta(seconds=10),
            )

            # Return the updated schedule wrapped in ScheduleUpdate
            return ScheduleUpdate(schedule=schedule)

        # Update the schedule using the callback
        await handle.update(update_schedule_spec)

        # Determine sync type based on the cron pattern
        # Minute-level pattern: "*/N * * * *" or "N * * * *" where N < 60
        import re

        minute_level_pattern = r"^(\*/([1-5]?[0-9])|([0-5]?[0-9])) \* \* \* \*$"
        match = re.match(minute_level_pattern, cron_expression)

        sync_type = "full"  # Default
        if match:
            # Extract interval for minute-level schedules
            if match.group(2):  # */N pattern
                interval = int(match.group(2))
                if interval < 60:
                    sync_type = "incremental"
            elif match.group(3):  # Specific minute
                sync_type = "incremental"

        # Update the unified cron_schedule field and sync type
        update_data = {"cron_schedule": cron_expression, "sync_type": sync_type}

        # Update the sync record in the database
        sync_obj = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        await crud.sync.update(db=db, db_obj=sync_obj, obj_in=update_data, ctx=ctx, uow=uow)

        field_type = "minute-level" if sync_type == "incremental" else "regular"
        logger.info(
            f"Updated {field_type} schedule {schedule_id} with cron expression {cron_expression}"
        )

    async def pause_schedule(self, schedule_id: str, sync_id: UUID, db: AsyncSession, ctx) -> None:
        """Pause a schedule.

        Args:
            schedule_id: The schedule ID to pause
            sync_id: The sync ID
            db: Database session
            ctx: Authentication context
        """
        client = await self._get_client()
        handle = client.get_schedule_handle(schedule_id)

        await handle.pause()

        # Update sync status to indicate paused schedule
        sync_obj = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        await crud.sync.update(
            db=db,
            db_obj=sync_obj,
            obj_in={"status": "INACTIVE"},
            ctx=ctx,
        )

        logger.info(f"Paused schedule {schedule_id}")

    async def resume_schedule(self, schedule_id: str, sync_id: UUID, db: AsyncSession, ctx) -> None:
        """Resume a paused schedule.

        Args:
            schedule_id: The schedule ID to resume
            sync_id: The sync ID
            db: Database session
            ctx: Authentication context
        """
        client = await self._get_client()
        handle = client.get_schedule_handle(schedule_id)

        await handle.unpause()

        # Update sync status to indicate active schedule
        sync_obj = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        await crud.sync.update(
            db=db,
            db_obj=sync_obj,
            obj_in={"status": "ACTIVE"},
            ctx=ctx,
        )

        logger.info(f"Resumed schedule {schedule_id}")

    async def delete_schedule_by_id(
        self, schedule_id: str, sync_id: UUID, db: AsyncSession, ctx
    ) -> None:
        """Delete a schedule by schedule ID.

        Args:
            schedule_id: The schedule ID to delete
            sync_id: The sync ID
            db: Database session
            ctx: Authentication context
        """
        client = await self._get_client()
        handle = client.get_schedule_handle(schedule_id)

        await handle.delete()

        # Clear the temporal schedule fields from the sync record
        sync_obj = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        await crud.sync.update(
            db=db,
            db_obj=sync_obj,
            obj_in={
                "temporal_schedule_id": None,
                "cron_schedule": None,
                "sync_type": "full",
            },
            ctx=ctx,
        )

        logger.info(f"Deleted schedule {schedule_id}")

    async def delete_all_schedules_for_sync(self, sync_id: UUID, db: AsyncSession, ctx) -> None:
        """Delete all schedules associated with a sync (regular + minute + daily).

        This attempts to delete all three types of schedules based on naming conventions.
        It ignores missing schedules and continues.
        """
        # Regular schedule
        regular_schedule_id = f"sync-{sync_id}"
        try:
            await self.delete_schedule_by_id(regular_schedule_id, sync_id, db, ctx)
        except Exception as e:
            logger.info(f"Regular schedule {regular_schedule_id} not deleted (may not exist): {e}")

        # Minute-level schedule
        minute_schedule_id = f"minute-sync-{sync_id}"
        try:
            await self.delete_schedule_by_id(minute_schedule_id, sync_id, db, ctx)
        except Exception as e:
            logger.info(
                f"Minute-level schedule {minute_schedule_id} not deleted (may not exist): {e}"
            )

        # Daily cleanup schedule
        daily_schedule_id = f"daily-cleanup-{sync_id}"
        try:
            await self.delete_schedule_by_id(daily_schedule_id, sync_id, db, ctx)
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
        sync = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        if not sync or not sync.temporal_schedule_id:
            return None

        try:
            schedule_info = await self.get_schedule_info(sync.temporal_schedule_id)
            return {
                **schedule_info,
                "sync_id": str(sync_id),
                "cron_schedule": sync.cron_schedule,
                "sync_type": sync.sync_type,
            }
        except Exception as e:
            logger.error(f"Error getting schedule info for sync {sync_id}: {e}")
            return None

    async def create_or_update_schedule(  # noqa: C901
        self,
        sync_id: UUID,
        cron_schedule: str,
        db: AsyncSession,
        ctx,
        uow: UnitOfWork,
    ) -> str:
        """Create or update a schedule for a sync.

        If a schedule already exists for the sync, it will be updated.
        If no schedule exists, a new one will be created.

        Args:
            sync_id: The sync ID
            cron_schedule: Cron expression for the schedule
            db: Database session
            ctx: Authentication context
            uow: Unit of work
        Returns:
            The schedule ID
        """
        # Validate CRON expression before proceeding
        from croniter import croniter

        if not croniter.is_valid(cron_schedule):
            from fastapi import HTTPException

            raise HTTPException(status_code=422, detail=f"Invalid CRON expression: {cron_schedule}")

        # Get the sync - first just check if it exists and has a schedule
        sync = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        if not sync:
            raise ValueError(f"Sync {sync_id} not found")

        # Check if a schedule already exists and is valid in Temporal
        if sync.temporal_schedule_id:
            schedule_id = sync.temporal_schedule_id
            schedule_status = await self.check_schedule_exists_and_running(schedule_id)

            if schedule_status["exists"]:
                # Just update the existing schedule
                await self.update_schedule(
                    schedule_id=schedule_id,
                    cron_expression=cron_schedule,
                    sync_id=sync_id,
                    db=db,
                    uow=uow,
                    ctx=ctx,
                )
                logger.info(f"Updated existing schedule {schedule_id} for sync {sync_id}")
                return schedule_id
            else:
                logger.warning(
                    f"Schedule {schedule_id} not found in Temporal for sync {sync_id}, "
                    "will create new one"
                )

        # Need to create a new schedule - gather required data
        # Load the sync with all relationships needed
        sync = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=True)

        source_connection = await crud.source_connection.get_by_sync_id(
            db=db, sync_id=sync_id, ctx=ctx
        )
        if not source_connection:
            raise ValueError(f"No source connection found for sync {sync_id}")

        # Get the collection - it should be loaded with the source connection
        collection = await crud.collection.get_by_readable_id(
            db=db, readable_id=source_connection.readable_collection_id, ctx=ctx
        )
        if not collection:
            raise ValueError(f"No collection found for source connection {source_connection.id}")

        # Get the actual Connection object (not SourceConnection!)
        from airweave.core.source_connection_service_helpers import source_connection_helpers

        connection_schema = await source_connection_helpers.get_connection_for_source_connection(
            db=db, source_connection=source_connection, ctx=ctx
        )

        sync_schema = schemas.Sync.model_validate(sync, from_attributes=True)
        collection_schema = schemas.CollectionRecord.model_validate(
            collection, from_attributes=True
        )

        # Convert to dicts for Temporal workflow
        sync_dict = sync_schema.model_dump(mode="json")
        collection_dict = collection_schema.model_dump(mode="json")
        connection_dict = connection_schema.model_dump(mode="json")

        # Determine schedule type based on cron pattern
        import re

        minute_level_pattern = r"^(\*/([1-5]?[0-9])|([0-5]?[0-9])) \* \* \* \*$"
        match = re.match(minute_level_pattern, cron_schedule)

        schedule_type = "regular"  # Default
        if match:
            # Check if it's a minute-level schedule (< 60 minutes)
            if match.group(2):  # */N pattern
                interval = int(match.group(2))
                if interval < 60:
                    schedule_type = "minute"
            elif match.group(3):  # Specific minute
                schedule_type = "minute"

        # Create appropriate schedule type
        if schedule_type == "minute":
            schedule_id = await self.create_minute_level_schedule(
                sync_id=sync_id,
                cron_expression=cron_schedule,
                sync_dict=sync_dict,
                collection_dict=collection_dict,
                connection_dict=connection_dict,
                db=db,
                ctx=ctx,
                access_token=None,  # Access token will be handled by the workflow
            )
        else:
            schedule_id = await self.create_regular_schedule(
                sync_id=sync_id,
                cron_expression=cron_schedule,
                sync_dict=sync_dict,
                collection_dict=collection_dict,
                connection_dict=connection_dict,
                db=db,
                ctx=ctx,
                access_token=None,  # Access token will be handled by the workflow
            )

        logger.info(f"Created new schedule {schedule_id} for sync {sync_id}")
        return schedule_id

    async def delete_schedule(
        self,
        sync_id: UUID,
        db: AsyncSession,
        ctx,
    ) -> None:
        """Delete a schedule for a sync by sync ID.

        This is a convenience method that looks up the schedule ID from the sync
        and delegates to delete_schedule_by_id.

        Args:
            sync_id: The sync ID
            db: Database session
            ctx: Authentication context
        """
        # Get the sync to find the schedule ID
        sync = await crud.sync.get(db=db, id=sync_id, ctx=ctx, with_connections=False)
        if not sync or not sync.temporal_schedule_id:
            logger.warning(f"No schedule found for sync {sync_id}")
            return

        # Delegate to the main delete method
        await self.delete_schedule_by_id(
            schedule_id=sync.temporal_schedule_id,
            sync_id=sync_id,
            db=db,
            ctx=ctx,
        )

    async def create_cleanup_schedule(self) -> str:
        """Create a singleton schedule for cleaning up stuck sync jobs.

        This schedule runs every 150 seconds to detect and cancel:
        - CANCELLING/PENDING jobs stuck for > 3 minutes
        - RUNNING jobs stuck for > 10 minutes with no entity updates

        Returns:
            Schedule ID of the cleanup schedule
        """
        from airweave.platform.temporal.workflows import CleanupStuckSyncJobsWorkflow

        client = await self._get_client()
        schedule_id = "cleanup-stuck-sync-jobs"

        # Check if schedule already exists
        try:
            handle = client.get_schedule_handle(schedule_id)
            await handle.describe()
            logger.info(f"Cleanup schedule {schedule_id} already exists")
            return schedule_id
        except Exception:
            # Schedule doesn't exist, create it
            pass

        logger.info(f"Creating cleanup schedule {schedule_id}")

        # Create schedule with 150 second interval
        schedule = Schedule(
            action=ScheduleActionStartWorkflow(
                CleanupStuckSyncJobsWorkflow.run,
                id="cleanup-workflow",
                task_queue=settings.TEMPORAL_TASK_QUEUE,
            ),
            spec=ScheduleSpec(
                intervals=[ScheduleIntervalSpec(every=timedelta(seconds=150))],
            ),
            state=ScheduleState(
                note="Periodic cleanup of stuck sync jobs",
                paused=False,
            ),
        )

        await client.create_schedule(schedule_id, schedule)
        logger.info(f"Successfully created cleanup schedule {schedule_id}")
        return schedule_id

    async def create_api_key_notification_schedule(self) -> str:
        """Create a singleton schedule for API key expiration notifications.

        This schedule runs every minute to check for and notify about:
        - API keys expiring in 14 days
        - API keys expiring in 3 days
        - API keys that have recently expired (within last 24h)

        Returns:
            Schedule ID of the notification schedule
        """
        from airweave.platform.temporal.workflows.api_key_notifications import (
            APIKeyExpirationCheckWorkflow,
        )

        client = await self._get_client()
        schedule_id = "api-key-expiration-notifications"

        # Check if schedule already exists
        try:
            handle = client.get_schedule_handle(schedule_id)
            await handle.describe()
            logger.info(f"API key notification schedule {schedule_id} already exists")
            return schedule_id
        except Exception:
            # Schedule doesn't exist, create it
            pass

        logger.info(f"Creating API key notification schedule {schedule_id}")

        # Create schedule to run every minute (for testing)
        schedule = Schedule(
            action=ScheduleActionStartWorkflow(
                APIKeyExpirationCheckWorkflow.run,
                id="api-key-notification-workflow",
                task_queue=settings.TEMPORAL_TASK_QUEUE,
            ),
            spec=ScheduleSpec(
                intervals=[ScheduleIntervalSpec(every=timedelta(days=1))],
            ),
            state=ScheduleState(
                note="API key expiration notifications (runs every day)",
                paused=False,
            ),
        )

        await client.create_schedule(schedule_id, schedule)
        logger.info(f"Successfully created API key notification schedule {schedule_id} (every day)")
        return schedule_id


# Singleton instance
temporal_schedule_service = TemporalScheduleService()
