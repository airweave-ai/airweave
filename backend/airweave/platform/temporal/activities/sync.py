"""Temporal activities for Airweave."""

import asyncio
from contextlib import suppress
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from temporalio import activity

from airweave.core.exceptions import NotFoundException


async def _run_sync_task(
    sync,
    sync_job,
    collection,
    connection,
    ctx,
    access_token,
    force_full_sync=False,
):
    """Run the actual sync service."""
    from airweave import crud
    from airweave.core.exceptions import NotFoundException
    from airweave.core.sync_service import sync_service
    from airweave.db.session import get_db_context
    from airweave.platform.sync.config import SyncConfig

    # Refetch sync_job from DB to get sync_config
    execution_config = None
    try:
        async with get_db_context() as db:
            sync_job_model = await crud.sync_job.get(db, id=sync_job.id, ctx=ctx)
            if sync_job_model and sync_job_model.sync_config:
                execution_config = SyncConfig(**sync_job_model.sync_config)
                ctx.logger.info(f"Loaded execution config from DB: {sync_job_model.sync_config}")
    except Exception as e:
        ctx.logger.warning(f"Failed to load execution config from DB: {e}")

    try:
        return await sync_service.run(
            sync=sync,
            sync_job=sync_job,
            collection=collection,
            source_connection=connection,
            ctx=ctx,
            access_token=access_token,
            force_full_sync=force_full_sync,
            execution_config=execution_config,
        )
    except NotFoundException as e:
        # Check if this is the specific "Source connection record not found" error
        if "Source connection record not found" in str(e) or "Connection not found" in str(e):
            ctx.logger.info(
                f"🧹 Source connection for sync {sync.id} not found. "
                f"Resource was likely deleted during workflow execution."
            )
            # Re-raise. Custom exception types don't serialize cleanly, so we use a string marker.
            raise Exception("ORPHANED_SYNC: Source connection record not found") from e
        # Other NotFoundException errors should be re-raised as-is
        raise


# Import inside the activity to avoid issues with Temporal's sandboxing
@activity.defn
async def run_sync_activity(  # noqa: C901
    sync_dict: Dict[str, Any],
    sync_job_dict: Dict[str, Any],
    collection_dict: Dict[str, Any],
    connection_dict: Dict[str, Any],
    ctx_dict: Dict[str, Any],
    access_token: Optional[str] = None,
    force_full_sync: bool = False,
) -> None:
    """Activity to run a sync job.

    This activity wraps the existing sync_service.run method.

    Args:
        sync_dict: The sync configuration as dict
        sync_job_dict: The sync job as dict
        collection_dict: The collection as dict
        connection_dict: The connection as dict (Connection schema, NOT SourceConnection)
        ctx_dict: The API context as dict
        access_token: Optional access token
        force_full_sync: If True, forces a full sync with orphaned entity deletion
    """
    # Import here to avoid Temporal sandboxing issues
    from airweave import crud, schemas
    from airweave.api.context import ApiContext
    from airweave.core.logging import LoggerConfigurator
    from airweave.core.shared_models import SyncJobStatus
    from airweave.db.session import get_db_context
    from airweave.platform.temporal.worker_metrics import worker_metrics
    from airweave.webhooks.service import service as webhooks_service

    # Convert dicts back to Pydantic models
    sync = schemas.Sync(**sync_dict)
    sync_job = schemas.SyncJob(**sync_job_dict)
    connection = schemas.Connection(**connection_dict)

    user = schemas.User(**ctx_dict["user"]) if ctx_dict.get("user") else None
    organization = schemas.Organization(**ctx_dict["organization"])

    ctx = ApiContext(
        request_id=ctx_dict["request_id"],
        organization=organization,
        user=user,
        auth_method=ctx_dict["auth_method"],
        auth_metadata=ctx_dict.get("auth_metadata"),
        logger=LoggerConfigurator.configure_logger(
            "airweave.temporal.activity",
            dimensions={
                "sync_job_id": str(sync_job.id),
                "organization_id": str(organization.id),
                "organization_name": organization.name,
            },
        ),
    )

    collection_id = UUID(collection_dict["id"])
    async with get_db_context() as db:
        collection_model = await crud.collection.get(db=db, id=collection_id, ctx=ctx)
        if not collection_model:
            raise ValueError(f"Collection {collection_id} not found in database")

        collection = schemas.Collection.model_validate(collection_model, from_attributes=True)
        ctx.logger.info(
            f"Fetched fresh collection data from DB: {collection.readable_id} "
            f"(vector_size={collection.vector_size}, model={collection.embedding_model_name})"
        )

    ctx.logger.debug(f"\n\nStarting sync activity for job {sync_job.id}\n\n")

    # Track this activity in worker metrics (fail-safe: never crash sync)
    try:
        tracking_context = worker_metrics.track_activity(
            activity_name="run_sync_activity",
            sync_job_id=sync_job.id,
            sync_id=sync.id,
            organization_id=organization.id,
            metadata={
                "connection_name": connection.name,
                "collection_name": collection.name,
                "force_full_sync": force_full_sync,
                "source_type": connection.short_name,
                "org_name": organization.name,
            },
        )
        await tracking_context.__aenter__()
    except Exception as e:
        ctx.logger.warning(f"Failed to register activity in metrics: {e}")
        tracking_context = None

    try:
        # Start the sync task
        sync_task = asyncio.create_task(
            _run_sync_task(
                sync,
                sync_job,
                collection,
                connection,
                ctx,
                access_token,
                force_full_sync,
            )
        )
        # Publish RUNNING webhook
        running_sync_job = sync_job.model_copy(update={"status": SyncJobStatus.RUNNING})
        await webhooks_service.publish_event_sync(
            source_connection_id=sync.source_connection_id,
            organisation=organization,
            sync_job=running_sync_job,
            collection=collection,
            source_type=connection.short_name,
        )

        try:
            while True:
                done, _ = await asyncio.wait({sync_task}, timeout=1)
                if sync_task in done:
                    # Propagate result/exception (including CancelledError from inner task)
                    await sync_task
                    break
                ctx.logger.debug("HEARTBEAT: Sync in progress")
                activity.heartbeat("Sync in progress")

            # Fetch updated sync_job with metrics for COMPLETED webhook
            from airweave import crud
            from airweave.db.session import get_db_context

            async with get_db_context() as db:
                updated_sync_job_model = await crud.sync_job.get(db, id=sync_job.id, ctx=ctx)
                if updated_sync_job_model:
                    completed_sync_job = schemas.SyncJob.model_validate(
                        updated_sync_job_model, from_attributes=True
                    )
                    completed_sync_job = completed_sync_job.model_copy(
                        update={"status": SyncJobStatus.COMPLETED}
                    )
                    await webhooks_service.publish_event_sync(
                        source_connection_id=sync.source_connection_id,
                        organisation=organization,
                        sync_job=completed_sync_job,
                        collection=collection,
                        source_type=connection.short_name,
                    )
            ctx.logger.info(f"\n\nCompleted sync activity for job {sync_job.id}\n\n")

        except asyncio.CancelledError:
            ctx.logger.info(f"\n\n[ACTIVITY] Sync activity cancelled for job {sync_job.id}\n\n")
            # 1) Flip job status to CANCELLED immediately so UI reflects truth
            try:
                # Import inside to avoid sandbox issues
                from airweave.core.datetime_utils import utc_now_naive
                from airweave.core.shared_models import SyncJobStatus
                from airweave.core.sync_job_service import sync_job_service

                await sync_job_service.update_status(
                    sync_job_id=sync_job.id,
                    status=SyncJobStatus.CANCELLED,
                    ctx=ctx,
                    error="Workflow was cancelled",
                    failed_at=utc_now_naive(),
                )
                ctx.logger.debug(f"\n\n[ACTIVITY] Updated job {sync_job.id} to CANCELLED\n\n")
                cancelled_sync_job = sync_job.model_copy(
                    update={"status": SyncJobStatus.CANCELLED, "error": "Workflow was cancelled"}
                )
                await webhooks_service.publish_event_sync(
                    source_connection_id=sync.source_connection_id,
                    organisation=organization,
                    sync_job=cancelled_sync_job,
                    collection=collection,
                    source_type=connection.short_name,
                    error="Workflow was cancelled",
                )
            except Exception as status_err:
                ctx.logger.error(f"Failed to update job {sync_job.id} to CANCELLED: {status_err}")

            # 2) Ensure the internal sync task is cancelled and awaited while heartbeating
            sync_task.cancel()
            while not sync_task.done():
                try:
                    await asyncio.wait_for(sync_task, timeout=1)
                except asyncio.TimeoutError:
                    activity.heartbeat("Cancelling sync...")
            with suppress(asyncio.CancelledError):
                await sync_task

            # 3) Re-raise so Temporal records the activity as CANCELED
            raise
        except Exception as e:
            ctx.logger.error(f"Failed sync activity for job {sync_job.id}: {e}")
            failed_sync_job = sync_job.model_copy(
                update={"status": SyncJobStatus.FAILED, "error": str(e)}
            )
            await webhooks_service.publish_event_sync(
                organisation=organization,
                source_connection_id=sync.source_connection_id,
                sync_job=failed_sync_job,
                collection=collection,
                source_type=connection.short_name,
                error=str(e),
            )
            raise
    finally:
        # Clean up metrics tracking (fail-safe)
        if tracking_context:
            try:
                await tracking_context.__aexit__(None, None, None)
            except Exception as cleanup_err:
                ctx.logger.warning(f"Failed to cleanup metrics tracking: {cleanup_err}")


@activity.defn
async def mark_sync_job_cancelled_activity(
    sync_job_id: str,
    ctx_dict: Dict[str, Any],
    reason: Optional[str] = None,
    when_iso: Optional[str] = None,
) -> None:
    """Mark a sync job as CANCELLED (used when workflow cancels before activity starts).

    Args:
        sync_job_id: The sync job ID (str UUID)
        ctx_dict: Serialized ApiContext dict
        reason: Optional cancellation reason
        when_iso: Optional ISO timestamp for failed_at
    """
    from airweave import schemas
    from airweave.api.context import ApiContext
    from airweave.core.logging import LoggerConfigurator
    from airweave.core.shared_models import SyncJobStatus
    from airweave.core.sync_job_service import sync_job_service

    # Reconstruct context
    organization = schemas.Organization(**ctx_dict["organization"])
    user = schemas.User(**ctx_dict["user"]) if ctx_dict.get("user") else None

    ctx = ApiContext(
        request_id=ctx_dict["request_id"],
        organization=organization,
        user=user,
        auth_method=ctx_dict["auth_method"],
        auth_metadata=ctx_dict.get("auth_metadata"),
        logger=LoggerConfigurator.configure_logger(
            "airweave.temporal.activity.cancel_pre_activity",
            dimensions={
                "sync_job_id": sync_job_id,
                "organization_id": str(organization.id),
                "organization_name": organization.name,
            },
        ),
    )

    failed_at = None
    if when_iso:
        try:
            failed_at = datetime.fromisoformat(when_iso)
        except Exception:
            failed_at = None

    ctx.logger.debug(
        f"[WORKFLOW] Marking sync job {sync_job_id} as CANCELLED (pre-activity): {reason or ''}"
    )

    try:
        await sync_job_service.update_status(
            sync_job_id=UUID(sync_job_id),
            status=SyncJobStatus.CANCELLED,
            ctx=ctx,
            error=reason,
            failed_at=failed_at,
        )
        ctx.logger.debug(f"[WORKFLOW] Updated job {sync_job_id} to CANCELLED")
    except Exception as e:
        ctx.logger.error(f"Failed to update job {sync_job_id} to CANCELLED: {e}")
        raise


@activity.defn
async def create_sync_job_activity(
    sync_id: str,
    ctx_dict: Dict[str, Any],
    force_full_sync: bool = False,
) -> Dict[str, Any]:
    """Create a new sync job for the given sync.

    This activity creates a new sync job in the database, checking first
    if there's already a running job for this sync.

    Args:
        sync_id: The sync ID to create a job for
        ctx_dict: The API context as dict
        force_full_sync: If True (daily cleanup), wait for running jobs to complete

    Returns:
        The created sync job as a dict

    Raises:
        Exception: If a sync job is already running and force_full_sync is False
    """
    from airweave import crud, schemas
    from airweave.api.context import ApiContext
    from airweave.core.logging import LoggerConfigurator
    from airweave.db.session import get_db_context

    # Reconstruct organization and user from the dictionary
    organization = schemas.Organization(**ctx_dict["organization"])
    user = schemas.User(**ctx_dict["user"]) if ctx_dict.get("user") else None

    ctx = ApiContext(
        request_id=ctx_dict["request_id"],
        organization=organization,
        user=user,
        auth_method=ctx_dict["auth_method"],
        auth_metadata=ctx_dict.get("auth_metadata"),
        logger=LoggerConfigurator.configure_logger(
            "airweave.temporal.activity.create_sync_job",
            dimensions={
                "sync_id": sync_id,
                "organization_id": str(organization.id),
                "organization_name": organization.name,
            },
        ),
    )

    ctx.logger.info(f"Creating sync job for sync {sync_id} (force_full_sync={force_full_sync})")

    async with get_db_context() as db:
        # First, check if the sync still exists (defensive check for orphaned workflows)
        try:
            _ = await crud.sync.get(db=db, id=UUID(sync_id), ctx=ctx, with_connections=False)
        except NotFoundException as e:
            ctx.logger.info(
                f"🧹 Could not verify sync {sync_id} exists: {e}. "
                f"Marking as orphaned to trigger cleanup."
            )
            return {"_orphaned": True, "sync_id": sync_id, "reason": f"Sync lookup error: {e}"}

        # Check if there's already a running/cancellable sync job for this sync
        from airweave.core.shared_models import SyncJobStatus

        running_jobs = await crud.sync_job.get_all_by_sync_id(
            db=db,
            sync_id=UUID(sync_id),
            # Database now stores lowercase string statuses
            status=[
                SyncJobStatus.PENDING.value,
                SyncJobStatus.RUNNING.value,
                SyncJobStatus.CANCELLING.value,
            ],
        )

        if running_jobs:
            if force_full_sync:
                # For daily cleanup, wait for running jobs to complete
                ctx.logger.info(
                    f"🔄 Daily cleanup sync for {sync_id}: "
                    f"Found {len(running_jobs)} running job(s). "
                    f"Waiting for them to complete before starting cleanup..."
                )

                # Wait for running jobs to complete (check every 30 seconds)
                import asyncio

                max_wait_time = 60 * 60  # 1 hour max wait
                wait_interval = 30  # Check every 30 seconds
                total_waited = 0

                while total_waited < max_wait_time:
                    # Send heartbeat to prevent timeout
                    activity.heartbeat(f"Waiting for running jobs to complete ({total_waited}s)")

                    # Wait before checking again
                    await asyncio.sleep(wait_interval)
                    total_waited += wait_interval

                    # Check if jobs are still running
                    async with get_db_context() as check_db:
                        still_running = await crud.sync_job.get_all_by_sync_id(
                            db=check_db,
                            sync_id=UUID(sync_id),
                            status=[
                                SyncJobStatus.PENDING.value,
                                SyncJobStatus.RUNNING.value,
                                SyncJobStatus.CANCELLING.value,
                            ],
                        )

                        if not still_running:
                            ctx.logger.info(
                                f"✅ Running jobs completed. "
                                f"Proceeding with cleanup sync for {sync_id}"
                            )
                            break
                else:
                    # Timeout reached
                    ctx.logger.error(
                        f"❌ Timeout waiting for running jobs to complete for sync {sync_id}. "
                        f"Skipping cleanup sync."
                    )
                    raise Exception(
                        f"Timeout waiting for running jobs to complete after {max_wait_time}s"
                    )
            else:
                # For regular incremental syncs, skip if job is running
                ctx.logger.warning(
                    f"Sync {sync_id} already has {len(running_jobs)} running jobs. "
                    f"Skipping new job creation."
                )
                raise Exception(
                    f"Sync {sync_id} already has a running job. "
                    f"Skipping this scheduled run to avoid conflicts."
                )

        # Create the new sync job
        sync_job_in = schemas.SyncJobCreate(sync_id=UUID(sync_id))
        sync_job = await crud.sync_job.create(db=db, obj_in=sync_job_in, ctx=ctx)

        # Access the ID before commit to avoid lazy loading issues
        sync_job_id = sync_job.id

        await db.commit()

        # Refresh the object to ensure all attributes are loaded
        await db.refresh(sync_job)

        ctx.logger.info(f"Created sync job {sync_job_id} for sync {sync_id}")

        # Publish PENDING webhook event
        try:
            from airweave.webhooks.service import service as webhooks_service

            source_conn = await crud.source_connection.get_by_sync_id(
                db=db, sync_id=UUID(sync_id), ctx=ctx
            )
            if source_conn:
                connection = await crud.connection.get(db=db, id=source_conn.connection_id, ctx=ctx)
                collection = await crud.collection.get(db=db, id=source_conn.collection_id, ctx=ctx)
                if connection and collection:
                    collection_schema = schemas.Collection.model_validate(
                        collection, from_attributes=True
                    )
                    sync_job_schema = schemas.SyncJob.model_validate(sync_job)
                    await webhooks_service.publish_event_sync(
                        organisation=organization,
                        sync_job=sync_job_schema,
                        collection=collection_schema,
                        source_type=connection.short_name,
                        source_connection_id=source_conn.id,
                    )
        except Exception as webhook_err:
            ctx.logger.warning(f"Failed to publish pending webhook: {webhook_err}")

        # Convert to dict for return
        sync_job_schema = schemas.SyncJob.model_validate(sync_job)
        return sync_job_schema.model_dump(mode="json")


async def _is_running_job_stuck(job, running_cutoff, db, redis_client, crud, logger) -> bool:
    """Check if a running job is stuck (no recent activity).

    Returns True if the job should be considered stuck, False otherwise.
    """
    import json
    from datetime import datetime

    # Skip ARF-only backfills (no postgres handler = no stats updates)
    if job.sync_config:
        handlers = job.sync_config.get("handlers", {})
        is_arf_only = not handlers.get("enable_postgres_handler", True)
        if is_arf_only:
            logger.debug(
                f"Skipping ARF-only job {job.id} from stuck detection (no stats updates expected)"
            )
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
            # Old snapshot without timestamp - fall back to DB check
            latest_entity_time = await crud.entity.get_latest_entity_time_for_job(
                db=db, sync_job_id=job.id
            )
            return latest_entity_time is None or latest_entity_time < running_cutoff

        # Check if activity is recent
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
            db=db, sync_job_id=job.id
        )
        return latest_entity_time is None or latest_entity_time < running_cutoff


async def _cancel_stuck_job(job, now, db, crud, logger) -> bool:
    """Cancel a single stuck job via Temporal and update database.

    Returns True if cancellation succeeded, False otherwise.
    """
    from airweave import schemas
    from airweave.api.context import ApiContext
    from airweave.core.shared_models import SyncJobStatus
    from airweave.core.sync_job_service import sync_job_service
    from airweave.core.temporal_service import temporal_service

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

    ctx = ApiContext(
        request_id=f"cleanup-{job_id}",
        organization=schemas.Organization.model_validate(organization),
        user=None,
        auth_method="system",
        auth_metadata={"source": "cleanup_activity"},
        logger=logger,
    )

    try:
        cancel_success = await temporal_service.cancel_sync_job_workflow(job_id, ctx)

        if cancel_success:
            logger.info(f"Successfully requested Temporal cancellation for job {job_id}")
            await asyncio.sleep(2)

        await sync_job_service.update_status(
            sync_job_id=UUID(job_id),
            status=SyncJobStatus.CANCELLED,
            ctx=ctx,
            error="Cancelled by cleanup job (stuck in transitional state)",
            failed_at=now,
        )

        logger.info(f"Successfully cancelled stuck job {job_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to cancel stuck job {job_id}: {e}", exc_info=True)
        return False


@activity.defn
async def cleanup_stuck_sync_jobs_activity() -> None:
    """Activity to clean up sync jobs stuck in transitional states.

    Detects and cancels:
    - CANCELLING/PENDING jobs stuck for > 3 minutes
    - RUNNING jobs stuck for > 10 minutes with no entity updates

    For each stuck job:
    1. Attempts graceful cancellation via Temporal workflow
    2. Falls back to force-cancelling in the database if workflow doesn't exist
    """
    from datetime import timedelta

    from airweave import crud
    from airweave.core.datetime_utils import utc_now_naive
    from airweave.core.logging import LoggerConfigurator
    from airweave.core.redis_client import redis_client
    from airweave.core.shared_models import SyncJobStatus
    from airweave.db.session import get_db_context

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
            # Query CANCELLING/PENDING jobs stuck for > 3 minutes
            cancelling_pending_jobs = await crud.sync_job.get_stuck_jobs_by_status(
                db=db,
                status=[SyncJobStatus.CANCELLING.value, SyncJobStatus.PENDING.value],
                modified_before=cancelling_pending_cutoff,
            )
            logger.info(
                f"Found {len(cancelling_pending_jobs)} CANCELLING/PENDING jobs "
                f"stuck for > 3 minutes"
            )

            # Query RUNNING jobs > 15 minutes old
            running_jobs = await crud.sync_job.get_stuck_jobs_by_status(
                db=db,
                status=[SyncJobStatus.RUNNING.value],
                started_before=running_cutoff,
            )
            logger.info(
                f"Found {len(running_jobs)} RUNNING jobs started >15min ago (will check activity)"
            )

            # Filter to jobs with no recent activity
            stuck_running_jobs = []
            for job in running_jobs:
                if await _is_running_job_stuck(job, running_cutoff, db, redis_client, crud, logger):
                    stuck_running_jobs.append(job)
            logger.info(
                f"Found {len(stuck_running_jobs)} RUNNING jobs with no activity in last 15 minutes"
            )

            # Combine all stuck jobs
            all_stuck_jobs = cancelling_pending_jobs + stuck_running_jobs
            stuck_job_count = len(all_stuck_jobs)

            if stuck_job_count == 0:
                logger.info("No stuck jobs found. Cleanup complete.")
                return

            logger.info(f"Processing {stuck_job_count} stuck sync jobs...")

            # Process each stuck job
            cancelled_count = 0
            failed_count = 0
            for job in all_stuck_jobs:
                success = await _cancel_stuck_job(job, now, db, crud, logger)
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
