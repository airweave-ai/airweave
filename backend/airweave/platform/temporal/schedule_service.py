"""Temporal schedule service for managing minute-level sync schedules."""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from temporalio.client import Client, ScheduleSpec

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

    async def create_minute_level_schedule(
        self,
        sync_id: UUID,
        cron_expression: str,
        sync_dict: dict,
        sync_job_dict: dict,
        sync_dag_dict: dict,
        collection_dict: dict,
        source_connection_dict: dict,
        user_dict: dict,
        db: AsyncSession,
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
            access_token: Optional access token

        Returns:
            The schedule ID
        """
        client = await self._get_client()

        # Create schedule ID using sync ID
        schedule_id = f"minute-sync-{sync_id}"

        # Create schedule spec with cron expression
        schedule_spec = ScheduleSpec(
            cron_expressions=[cron_expression],
            # Start immediately
            start_at=datetime.now(timezone.utc),
            # No end time (runs indefinitely)
            end_at=None,
            # Jitter to avoid thundering herd
            jitter=timedelta(seconds=10),
        )

        # Create the schedule
        await client.create_schedule(
            id=schedule_id,
            spec=schedule_spec,
            action=ScheduleSpec.Action.start_workflow(
                RunSourceConnectionWorkflow.run,
                args=[
                    sync_dict,
                    sync_job_dict,
                    sync_dag_dict,
                    collection_dict,
                    source_connection_dict,
                    user_dict,
                    access_token,
                ],
                id=f"minute-sync-workflow-{sync_id}",
                task_queue="airweave-task-queue",
            ),
        )

        # Update the sync record in the database
        await sync_crud.update(
            db=db,
            db_obj_id=sync_id,
            obj_in={
                "temporal_schedule_id": schedule_id,
                "minute_level_cron_schedule": cron_expression,
                "sync_type": "incremental",
            },
            user_email=user_dict.get("email"),
        )

        logger.info(f"Created minute-level schedule {schedule_id} for sync {sync_id}")
        return schedule_id

    async def update_schedule(
        self,
        schedule_id: str,
        cron_expression: str,
        sync_id: UUID,
        user_dict: dict,
        db: AsyncSession,
    ) -> None:
        """Update an existing schedule with a new cron expression.

        Args:
            schedule_id: The schedule ID to update
            cron_expression: New cron expression
            sync_id: The sync ID
            user_dict: The current user as dict
            db: Database session
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
        await sync_crud.update(
            db=db,
            db_obj_id=sync_id,
            obj_in={"minute_level_cron_schedule": cron_expression},
            user_email=user_dict.get("email"),
        )

        logger.info(f"Updated schedule {schedule_id} with cron expression {cron_expression}")

    async def pause_schedule(
        self, schedule_id: str, sync_id: UUID, user_dict: dict, db: AsyncSession
    ) -> None:
        """Pause a schedule.

        Args:
            schedule_id: The schedule ID to pause
            sync_id: The sync ID
            user_dict: The current user as dict
            db: Database session
        """
        client = await self._get_client()
        handle = client.get_schedule_handle(schedule_id)

        await handle.pause()

        # Update sync status to indicate paused schedule
        await sync_crud.update(
            db=db,
            db_obj_id=sync_id,
            obj_in={"status": "INACTIVE"},
            user_email=user_dict.get("email"),
        )

        logger.info(f"Paused schedule {schedule_id}")

    async def resume_schedule(
        self, schedule_id: str, sync_id: UUID, user_dict: dict, db: AsyncSession
    ) -> None:
        """Resume a paused schedule.

        Args:
            schedule_id: The schedule ID to resume
            sync_id: The sync ID
            user_dict: The current user as dict
            db: Database session
        """
        client = await self._get_client()
        handle = client.get_schedule_handle(schedule_id)

        await handle.unpause()

        # Update sync status to indicate active schedule
        await sync_crud.update(
            db=db,
            db_obj_id=sync_id,
            obj_in={"status": "ACTIVE"},
            user_email=user_dict.get("email"),
        )

        logger.info(f"Resumed schedule {schedule_id}")

    async def delete_schedule(
        self, schedule_id: str, sync_id: UUID, user_dict: dict, db: AsyncSession
    ) -> None:
        """Delete a schedule.

        Args:
            schedule_id: The schedule ID to delete
            sync_id: The sync ID
            user_dict: The current user as dict
            db: Database session
        """
        client = await self._get_client()
        handle = client.get_schedule_handle(schedule_id)

        await handle.delete()

        # Clear the temporal schedule fields from the sync record
        await sync_crud.update(
            db=db,
            db_obj_id=sync_id,
            obj_in={
                "temporal_schedule_id": None,
                "minute_level_cron_schedule": None,
                "sync_type": "full",
            },
            user_email=user_dict.get("email"),
        )

        logger.info(f"Deleted schedule {schedule_id}")

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
            "cron_expressions": desc.schedule.spec.cron_expressions,
            "paused": desc.schedule.state.paused,
            "next_run_time": desc.schedule.state.next_run_time,
            "last_run_time": desc.schedule.state.last_run_time,
        }

    async def get_sync_schedule_info(
        self, sync_id: UUID, db: AsyncSession, auth_context
    ) -> Optional[dict]:
        """Get schedule information for a specific sync.

        Args:
            sync_id: The sync ID
            db: Database session
            auth_context: Authentication context

        Returns:
            Schedule information if exists, None otherwise
        """
        sync = await sync_crud.get(db=db, id=sync_id, auth_context=auth_context)
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
