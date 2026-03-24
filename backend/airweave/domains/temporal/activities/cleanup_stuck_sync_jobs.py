"""Cleanup stuck sync jobs activity — detects and cancels jobs stuck in transitional states."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from temporalio import activity

from airweave import crud, schemas
from airweave.core.context import BaseContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import LoggerConfigurator
from airweave.core.redis_client import redis_client
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.domains.syncs.protocols import SyncJobStateMachineProtocol
from airweave.domains.temporal.protocols import TemporalWorkflowServiceProtocol
from airweave.models.sync_job import SyncJob

_CANCELLING_PENDING_CUTOFF = timedelta(minutes=3)
_RUNNING_CUTOFF = timedelta(minutes=15)
_POST_CANCEL_SLEEP_S = 2
_STUCK_CANCEL_REASON = "Cancelled by cleanup job (stuck in transitional state)"
_STUCK_RUNNING_REASON = "Timed out by cleanup job (no activity for 15+ minutes)"
_REDIS_SNAPSHOT_KEY_PREFIX = "sync_progress_snapshot"


@dataclass
class CleanupStuckSyncJobsActivity:
    """Clean up sync jobs stuck in transitional states.

    Dependencies:
        temporal_workflow_service: Cancel stuck workflows via Temporal
        sync_job_service: Update sync job status

    Detects and cancels:
    - CANCELLING/PENDING jobs stuck for > 3 minutes
    - RUNNING jobs stuck for > 15 minutes with no entity updates
    """

    temporal_workflow_service: TemporalWorkflowServiceProtocol
    state_machine: SyncJobStateMachineProtocol

    @activity.defn(name="cleanup_stuck_sync_jobs_activity")
    async def run(self) -> None:
        """Run the cleanup activity."""
        logger = LoggerConfigurator.configure_logger(
            "airweave.temporal.cleanup",
            dimensions={"activity": "cleanup_stuck_sync_jobs"},
        )

        logger.info("Starting cleanup of stuck sync jobs...")

        now = utc_now_naive()
        cancelling_pending_cutoff = now - _CANCELLING_PENDING_CUTOFF
        running_cutoff = now - _RUNNING_CUTOFF

        try:
            async with get_db_context() as db:
                cancelling_pending_jobs = await crud.sync_job.get_stuck_jobs_by_status(
                    db=db,
                    status=[SyncJobStatus.CANCELLING.value, SyncJobStatus.PENDING.value],
                    modified_before=cancelling_pending_cutoff,
                )
                logger.info(
                    f"Found {len(cancelling_pending_jobs)} CANCELLING/PENDING jobs "
                    f"stuck for > {_CANCELLING_PENDING_CUTOFF}"
                )

                running_jobs = await crud.sync_job.get_stuck_jobs_by_status(
                    db=db,
                    status=[SyncJobStatus.RUNNING.value],
                    started_before=running_cutoff,
                )
                logger.info(
                    f"Found {len(running_jobs)} RUNNING jobs started >{_RUNNING_CUTOFF} ago "
                    f"(will check activity)"
                )

                stuck_running_jobs = [
                    job
                    for job in running_jobs
                    if await self._is_running_job_stuck(job, running_cutoff, db, logger)
                ]
                logger.info(
                    f"Found {len(stuck_running_jobs)} RUNNING jobs "
                    f"with no activity in last {_RUNNING_CUTOFF}"
                )

                all_stuck_jobs = cancelling_pending_jobs + stuck_running_jobs
                if not all_stuck_jobs:
                    logger.info("No stuck jobs found. Cleanup complete.")
                    return

                logger.info(f"Processing {len(all_stuck_jobs)} stuck sync jobs...")

                cancelled_count = 0
                failed_count = 0
                for job in all_stuck_jobs:
                    if await self._cancel_stuck_job(job, now, db, logger):
                        cancelled_count += 1
                    else:
                        failed_count += 1

                logger.info(
                    f"Cleanup complete. Processed {len(all_stuck_jobs)} stuck jobs: "
                    f"{cancelled_count} cancelled, {failed_count} failed"
                )

        except Exception as e:
            logger.error(f"Error during cleanup activity: {e}", exc_info=True)
            raise

    async def _is_running_job_stuck(
        self, job: SyncJob, running_cutoff: datetime, db: AsyncSession, logger: Any
    ) -> bool:
        """Check if a running job is stuck (no recent activity)."""
        if job.sync_config:
            handlers = job.sync_config.get("handlers", {})
            is_arf_only = not handlers.get("enable_postgres_handler", True)
            if is_arf_only:
                logger.debug(f"Skipping ARF-only job {job.id} from stuck detection")
                return False

        job_id_str = str(job.id)
        snapshot_key = f"{_REDIS_SNAPSHOT_KEY_PREFIX}:{job_id_str}"

        try:
            snapshot_json = await redis_client.client.get(snapshot_key)

            if not snapshot_json:
                logger.debug(f"No snapshot for job {job_id_str} - skipping")
                return False

            snapshot = json.loads(snapshot_json)
            last_update_str = snapshot.get("last_update_timestamp")

            if not last_update_str:
                latest_entity_time = await crud.entity.get_latest_entity_time_for_job(
                    db=db, sync_job_id=UUID(str(job.id))
                )
                return latest_entity_time is None or latest_entity_time < running_cutoff

            last_update = datetime.fromisoformat(last_update_str)
            if last_update.tzinfo is not None:
                last_update = last_update.replace(tzinfo=None)

            if last_update < running_cutoff:
                total_ops = sum(
                    snapshot.get(key, 0)
                    for key in ("inserted", "updated", "deleted", "kept", "skipped")
                )
                logger.info(
                    f"Job {job_id_str} last activity at {last_update} "
                    f"({total_ops} total ops) - marking as stuck"
                )
                return True

            logger.debug(f"Job {job_id_str} active at {last_update} - healthy")
            return False

        except Exception as e:
            logger.warning(f"Error checking job {job_id_str}: {e}, falling back to DB check")
            latest_entity_time = await crud.entity.get_latest_entity_time_for_job(
                db=db, sync_job_id=UUID(str(job.id))
            )
            return latest_entity_time is None or latest_entity_time < running_cutoff

    async def _cancel_stuck_job(
        self, job: SyncJob, now: datetime, db: AsyncSession, logger: Any
    ) -> bool:
        """Cancel a single stuck job via Temporal and update database.

        RUNNING jobs transition to FAILED (RUNNING → CANCELLED is invalid).
        CANCELLING/PENDING jobs transition to CANCELLED (valid transitions).
        """
        job_id = str(job.id)
        sync_id = str(job.sync_id)
        org_id = str(job.organization_id)
        current_status = SyncJobStatus(job.status)

        logger.info(
            f"Attempting to cancel stuck job {job_id} "
            f"(status: {job.status}, sync: {sync_id}, org: {org_id})"
        )

        try:
            organization = await crud.organization.get(
                db=db,
                id=job.organization_id,
                skip_access_validation=True,
            )
        except Exception as e:
            logger.error(f"Failed to fetch organization {org_id} for job {job_id}: {e}")
            return False

        ctx = BaseContext(
            organization=schemas.Organization.model_validate(organization),
            logger=logger,
        )

        try:
            cancel_success = await self.temporal_workflow_service.cancel_sync_job_workflow(
                job_id, ctx
            )

            if cancel_success:
                logger.info(f"Successfully requested Temporal cancellation for job {job_id}")
                await asyncio.sleep(_POST_CANCEL_SLEEP_S)

            if current_status == SyncJobStatus.RUNNING:
                await self.state_machine.transition(
                    sync_job_id=UUID(job_id),
                    target=SyncJobStatus.FAILED,
                    ctx=ctx,
                    error=_STUCK_RUNNING_REASON,
                )
            else:
                await self.state_machine.transition(
                    sync_job_id=UUID(job_id),
                    target=SyncJobStatus.CANCELLED,
                    ctx=ctx,
                    error=_STUCK_CANCEL_REASON,
                )

            logger.info(f"Successfully cleaned up stuck job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel stuck job {job_id}: {e}", exc_info=True)
            return False
