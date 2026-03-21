"""Temporal activity for cleaning up stuck sync jobs."""

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
from airweave.domains.syncs.protocols import SyncJobServiceProtocol
from airweave.domains.temporal.protocols import TemporalWorkflowServiceProtocol
from airweave.models.sync_job import SyncJob


@dataclass
class CleanupStuckSyncJobsActivity:
    """Clean up sync jobs stuck in transitional states.

    Detects and cancels:
    - CANCELLING/PENDING jobs stuck for > 3 minutes
    - RUNNING jobs stuck for > 15 minutes with no entity updates
    """

    temporal_workflow_service: TemporalWorkflowServiceProtocol
    sync_job_service: SyncJobServiceProtocol

    @activity.defn(name="cleanup_stuck_sync_jobs_activity")
    async def run(self) -> None:
        """Scan for and cancel stuck sync jobs."""
        logger = LoggerConfigurator.configure_logger(
            "airweave.temporal.cleanup",
            dimensions={"activity": "cleanup_stuck_sync_jobs"},
        )

        logger.info("Starting cleanup of stuck sync jobs...")

        now = utc_now_naive()
        cancelling_pending_cutoff = now - timedelta(minutes=3)
        running_cutoff = now - timedelta(minutes=15)

        try:
            async with get_db_context() as db:
                cancelling_pending_jobs = await crud.sync_job.get_stuck_jobs_by_status(
                    db=db,
                    status=[SyncJobStatus.CANCELLING.value, SyncJobStatus.PENDING.value],
                    modified_before=cancelling_pending_cutoff,
                )
                logger.info(
                    f"Found {len(cancelling_pending_jobs)} CANCELLING/PENDING jobs "
                    f"stuck for > 3 minutes"
                )

                running_jobs = await crud.sync_job.get_stuck_jobs_by_status(
                    db=db,
                    status=[SyncJobStatus.RUNNING.value],
                    started_before=running_cutoff,
                )
                logger.info(
                    f"Found {len(running_jobs)} RUNNING jobs started >15min ago "
                    f"(will check activity)"
                )

                stuck_running_jobs = []
                for job in running_jobs:
                    if await self._is_running_job_stuck(job, running_cutoff, db, logger):
                        stuck_running_jobs.append(job)
                logger.info(
                    f"Found {len(stuck_running_jobs)} RUNNING jobs "
                    f"with no activity in last 15 minutes"
                )

                all_stuck_jobs = cancelling_pending_jobs + stuck_running_jobs
                stuck_job_count = len(all_stuck_jobs)

                if stuck_job_count == 0:
                    logger.info("No stuck jobs found. Cleanup complete.")
                    return

                logger.info(f"Processing {stuck_job_count} stuck sync jobs...")

                cancelled_count = 0
                failed_count = 0
                for job in all_stuck_jobs:
                    success = await self._cancel_stuck_job(job, now, db, logger)
                    if success:
                        cancelled_count += 1
                    else:
                        failed_count += 1

                logger.info(
                    f"Cleanup complete. Processed {stuck_job_count} stuck jobs: "
                    f"{cancelled_count} cancelled, {failed_count} failed"
                )

        except Exception as e:
            logger.error(f"Error during cleanup activity: {e}", exc_info=True)
            raise

    async def _is_running_job_stuck(
        self,
        job: SyncJob,
        running_cutoff: datetime,
        db: AsyncSession,
        logger: Any,
    ) -> bool:
        if job.sync_config:
            handlers = job.sync_config.get("handlers", {})
            is_arf_only = not handlers.get("enable_postgres_handler", True)
            if is_arf_only:
                logger.debug(f"Skipping ARF-only job {job.id} from stuck detection")
                return False

        job_id_str = str(job.id)
        snapshot_key = f"sync_progress_snapshot:{job_id_str}"

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
                    [
                        snapshot.get("inserted", 0),
                        snapshot.get("updated", 0),
                        snapshot.get("deleted", 0),
                        snapshot.get("kept", 0),
                        snapshot.get("skipped", 0),
                    ]
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
        self,
        job: SyncJob,
        now: datetime,
        db: AsyncSession,
        logger: Any,
    ) -> bool:
        job_id = str(job.id)
        sync_id = str(job.sync_id)
        org_id = str(job.organization_id)

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
                job_id,
                ctx,  # type: ignore[arg-type]
            )
            if cancel_success:
                logger.info(f"Successfully requested Temporal cancellation for job {job_id}")
                await asyncio.sleep(2)

            await self.sync_job_service.update_status(
                sync_job_id=UUID(job_id),
                status=SyncJobStatus.CANCELLED,
                ctx=ctx,  # type: ignore[arg-type]
                error="Cancelled by cleanup job (stuck in transitional state)",
                failed_at=now,
            )

            logger.info(f"Successfully cancelled stuck job {job_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to cancel stuck job {job_id}: {e}", exc_info=True)
            return False
