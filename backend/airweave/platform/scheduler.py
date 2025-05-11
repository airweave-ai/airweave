"""Scheduler for sync jobs.

This module provides a scheduler that checks for syncs with cron schedules
and triggers them when they are due.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus, SyncStatus
from airweave.core.sync_service import sync_service
from airweave.db.session import get_db_context
from airweave.models.sync import Sync


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure a datetime is UTC timezone-aware.

    Args:
        dt: The datetime to ensure is UTC timezone-aware

    Returns:
        The datetime with UTC timezone, or None if input was None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class PlatformScheduler:
    """Scheduler for platform tasks.

    This class provides functionality to check for syncs with cron schedules
    and trigger them when they are due.
    """

    def __init__(self):
        """Initialize the scheduler."""
        self.running = False
        self.task: Optional[asyncio.Task] = None
        self.check_interval = 1  # Check every 1 second

    async def update_all_next_scheduled_runs(self):
        """Update all next_scheduled_run values for syncs with cron schedules.

        This is useful for maintenance or after changing cron schedules.
        """
        logger.info("Starting update of all next_scheduled_run values")
        updated_count = 0
        error_count = 0

        async with get_db_context() as db:
            # Get all active syncs with cron schedules
            stmt = select(Sync).where(
                (Sync.status == SyncStatus.ACTIVE) & (Sync.cron_schedule.is_not(None))
            )
            result = await db.execute(stmt)
            syncs = result.scalars().all()
            syncs = [schemas.SyncWithoutConnections.model_validate(sync) for sync in syncs]

            if not syncs:
                logger.info("No syncs with cron schedules found")
                return

            logger.info(f"Found {len(syncs)} syncs with cron schedules")
            now = datetime.now(timezone.utc)

            # Process each sync
            for sync in syncs:
                try:
                    # Get the latest job for this sync
                    latest_job = await crud.sync_job.get_latest_by_sync_id(db, sync_id=sync.id)

                    # Get the last run time (or use epoch if never run)
                    last_run_time = (
                        ensure_utc(latest_job.created_at)
                        if latest_job
                        else datetime.fromtimestamp(0, tz=timezone.utc)
                    )

                    # Calculate the next run time
                    cron = croniter(sync.cron_schedule, last_run_time)
                    next_run = ensure_utc(cron.get_next(datetime))

                    # If next run is in the past, calculate from now
                    if next_run < now:
                        cron = croniter(sync.cron_schedule, now)
                        next_run = ensure_utc(cron.get_next(datetime))

                    # Update the sync
                    current_user = await crud.user.get_by_email(db, email=sync.created_by_email)
                    db_sync = await crud.sync.get(
                        db, id=sync.id, current_user=current_user, with_connections=False
                    )
                    if not db_sync:
                        raise ValueError(f"Could not find sync {sync.id} in database")
                    await crud.sync.update(
                        db=db,
                        db_obj=db_sync,
                        obj_in={"next_scheduled_run": next_run},
                        current_user=current_user,
                    )
                    updated_count += 1

                    logger.debug(
                        f"Updated sync {sync.id} ({sync.name}) next_scheduled_run to "
                        f"{next_run.isoformat()}"
                    )
                except Exception as e:
                    logger.error(f"Error updating sync {sync.id}: {e}", exc_info=True)
                    error_count += 1

            logger.info(
                f"Completed update of next_scheduled_run values: "
                f"{updated_count} updated, {error_count} errors"
            )

    async def start(self):
        """Start the scheduler."""
        if self.running:
            logger.warning("Scheduler is already running")
            return

        # Update all next_scheduled_run values before starting
        logger.info("Initializing scheduler by updating all next_scheduled_run values")
        await self.update_all_next_scheduled_runs()

        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        logger.info("Sync scheduler started")
        logger.info(f"Scheduler check interval set to {self.check_interval} seconds")

    async def stop(self):
        """Stop the scheduler."""
        if not self.running:
            logger.warning("Scheduler is not running")
            return

        self.running = False
        if self.task:
            logger.info("Cancelling scheduler task")
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("Scheduler task cancelled successfully")
                pass
            self.task = None
        logger.info("Sync scheduler stopped")

    async def _scheduler_loop(self):
        """Main scheduler loop that checks for due syncs."""
        logger.info("Scheduler loop started")
        loop_count = 0

        while self.running:
            loop_count += 1
            loop_start_time = datetime.now(timezone.utc)
            logger.debug(f"Starting scheduler loop iteration #{loop_count}")

            try:
                await self._check_syncs()
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}", exc_info=True)

            # Calculate how long this loop iteration took
            loop_duration = (datetime.now(timezone.utc) - loop_start_time).total_seconds()
            logger.debug(
                f"Scheduler loop iteration #{loop_count} completed in {loop_duration:.3f}s"
            )

            # Sleep for the check interval
            await asyncio.sleep(self.check_interval)

    async def _check_syncs(self):
        """Check for syncs that are due to run."""
        check_start_time = datetime.now(timezone.utc)
        logger.debug(f"Checking for due syncs at {check_start_time.isoformat()}")

        async with get_db_context() as db:
            # Get all active syncs with cron schedules
            syncs = await self._get_active_syncs_with_schedule(db)

            if syncs:
                logger.info(f"Found {len(syncs)} syncs that may be due for execution")
            else:
                logger.debug("No syncs found that are due for execution")

            # Check each sync
            processed_count = 0
            triggered_count = 0
            for sync in syncs:
                sync_start_time = datetime.now(timezone.utc)
                logger.debug(f"Processing sync {sync.id} ({sync.name})")

                was_triggered = await self._process_sync(db, sync)
                processed_count += 1
                if was_triggered:
                    triggered_count += 1

                sync_duration = (datetime.now(timezone.utc) - sync_start_time).total_seconds()
                logger.debug(f"Processed sync {sync.id} in {sync_duration:.3f}s")

            check_duration = (datetime.now(timezone.utc) - check_start_time).total_seconds()
            if processed_count > 0:
                logger.info(
                    f"Processed {processed_count} syncs, triggered {triggered_count} in "
                    f"{check_duration:.3f}s"
                )
            else:
                logger.debug(f"No syncs processed in {check_duration:.3f}s")

    async def _get_active_syncs_with_schedule(self, db: AsyncSession) -> list[schemas.Sync]:
        """Get all active syncs with cron schedules that are due to run."""
        now = datetime.now(timezone.utc)
        logger.debug(f"Querying for active syncs with schedules at {now.isoformat()}")

        # First, get syncs with next_scheduled_run in the past or null
        query_start = datetime.now(timezone.utc)
        syncs = await crud.sync.get_all_with_schedule(db)
        query_duration = (datetime.now(timezone.utc) - query_start).total_seconds()

        sync_list = [schemas.SyncWithoutConnections.model_validate(sync) for sync in syncs]
        logger.debug(f"Found {len(sync_list)} candidate syncs in {query_duration:.3f}s")

        # Log some details about the syncs
        if sync_list:
            sync_details = ", ".join([f"{s.id} ({s.name})" for s in sync_list[:5]])
            if len(sync_list) > 5:
                sync_details += f", and {len(sync_list) - 5} more"
            logger.debug(f"Candidate syncs: {sync_details}")

        return sync_list

    async def _process_sync(self, db: AsyncSession, sync: schemas.Sync) -> bool:
        """Process a sync to check if it's due and trigger it if needed.

        Returns:
            bool: True if the sync was triggered, False otherwise
        """
        if not sync.cron_schedule:
            logger.warning(f"Sync {sync.id} has no cron schedule, skipping")
            return False

        # Get the latest job for this sync
        logger.debug(f"Getting latest job for sync {sync.id}")
        latest_job = await crud.sync_job.get_latest_by_sync_id(db, sync_id=sync.id)
        db_user = await crud.user.get_by_email(db, email=sync.created_by_email)
        current_user = schemas.User.model_validate(db_user)

        if latest_job:
            logger.debug(
                f"Latest job for sync {sync.id} is {latest_job.id} with status {latest_job.status}"
            )
        else:
            logger.debug(f"No previous jobs found for sync {sync.id}")

        # Check if there's an active job running
        if latest_job and latest_job.status == SyncJobStatus.IN_PROGRESS:
            # Skip this sync as it's already running
            logger.info(
                f"Sync {sync.id} ({sync.name}) already has job {latest_job.id} in progress."
            )
            # TODO: We must create a sync job that is autocancelled, to indicate to the user
            # that another sync job is already running.
            return False

        # Get the last run time (or use epoch if never run)
        last_run_time = (
            ensure_utc(latest_job.created_at)
            if latest_job
            else datetime.fromtimestamp(0, tz=timezone.utc)
        )
        logger.debug(f"Last run time for sync {sync.id}: {last_run_time.isoformat()}")

        # Calculate the next run time
        now = datetime.now(timezone.utc)
        cron = croniter(sync.cron_schedule, last_run_time)
        next_run = ensure_utc(cron.get_next(datetime))
        logger.debug(
            f"Calculated next run for sync {sync.id} at {next_run.isoformat()} "
            f"(cron: {sync.cron_schedule})"
        )

        # If next_scheduled_run is None or different from what we calculated, update it
        if (
            sync.next_scheduled_run is None
            or abs((ensure_utc(sync.next_scheduled_run) - next_run).total_seconds()) > 1
        ):
            logger.info(
                f"Updating next_scheduled_run for sync {sync.id} from "
                f"{sync.next_scheduled_run.isoformat() if sync.next_scheduled_run else 'None'} "
                f"to {next_run.isoformat()}"
            )

            async with get_db_context() as db:
                # Get the actual SQLAlchemy model object from the database
                db_sync = await crud.sync.get(
                    db, id=sync.id, current_user=current_user, with_connections=False
                )
                if not db_sync:
                    logger.error(f"Could not find sync {sync.id} in database, skipping update")
                    return False

                # Update the next_scheduled_run field
                await crud.sync.update(
                    db=db,
                    db_obj=db_sync,
                    obj_in={"next_scheduled_run": next_run},
                    current_user=current_user,
                )
                logger.debug(f"Successfully updated next_scheduled_run for sync {sync.id}")
                # Update our local copy
                sync.next_scheduled_run = next_run

        # Check if the sync is due
        if next_run <= now:
            time_diff = (now - next_run).total_seconds()
            logger.info(
                f"Sync {sync.id} ({sync.name}) is due (overdue by {time_diff:.1f}s), triggering"
            )
            sync_schema = await crud.sync.get(
                db, id=sync.id, current_user=current_user, with_connections=True
            )
            await self._trigger_sync(db, sync_schema)

            return True
        else:
            time_to_next = (next_run - now).total_seconds()
            logger.debug(
                f"Sync {sync.id} ({sync.name}) not due yet, next run in {time_to_next:.1f}s "
                f"at {next_run.isoformat()}"
            )
            return False

    async def _trigger_sync(self, db: AsyncSession, sync: schemas.Sync):
        """Trigger a sync job."""
        try:
            logger.info(f"Triggering sync {sync.id} ({sync.name})")

            # Get the user who created the sync for running the job
            user_email = sync.created_by_email
            logger.debug(f"Looking up user {user_email} for sync {sync.id}")
            db_user = await crud.user.get_by_email(db, email=user_email)

            if not db_user:
                logger.error(f"User {user_email} not found for sync {sync.id}, cannot trigger sync")
                return

            current_user = schemas.User.model_validate(db_user)
            logger.debug(
                f"Found user {current_user.email} (id: {current_user.id}) for sync {sync.id}"
            )

            # Create a new sync job with unit of work
            logger.debug(f"Creating new sync job for sync {sync.id}")
            async with get_db_context() as db:
                sync_job_in = schemas.SyncJobCreate(sync_id=sync.id)
                # Use the system user for creating the job
                sync_job = await crud.sync_job.create(
                    db=db, obj_in=sync_job_in, current_user=current_user
                )
                logger.info(f"Created sync job {sync_job.id} for sync {sync.id}")

            # Get the DAG for this sync
            logger.debug(f"Getting DAG for sync {sync.id}")
            sync_dag = await crud.sync_dag.get_by_sync_id(
                db=db, sync_id=sync.id, current_user=current_user
            )

            if not sync_dag:
                logger.error(f"No DAG found for sync {sync.id}, cannot trigger sync")
                return

            logger.debug(
                f"Found DAG {sync_dag.id} for sync {sync.id} with "
                f"{len(sync_dag.nodes)} nodes and {len(sync_dag.edges)} edges"
            )

            # Convert to schemas
            sync_job_schema = schemas.SyncJob.model_validate(sync_job)
            sync_dag_schema = schemas.SyncDag.model_validate(sync_dag)

            # Run the sync using the original user
            logger.info(f"Starting sync task for job {sync_job.id} (sync {sync.id})")
            asyncio.create_task(
                sync_service.run(sync, sync_job_schema, sync_dag_schema, current_user)
            )

            logger.info(
                f"Successfully triggered sync job {sync_job.id} for sync {sync.id} ({sync.name})"
            )
        except Exception as e:
            logger.error(f"Error triggering sync {sync.id}: {e}", exc_info=True)


# Create a singleton instance
platform_scheduler = PlatformScheduler()
