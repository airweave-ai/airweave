"""Service for managing sync job status."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from airweave import crud, schemas
from airweave.analytics.service import analytics
from airweave.api.context import ApiContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.core.shared_models import SyncJobStatus
from airweave.db.session import get_db_context
from airweave.platform.sync.pubsub import SyncProgressUpdate


class SyncJobService:
    """Service for managing sync job status updates."""

    def _build_stats_update_data(self, stats: SyncProgressUpdate) -> Dict[str, Any]:
        """Build update data from stats."""
        update_data = {
            "entities_inserted": stats.inserted,
            "entities_updated": stats.updated,
            "entities_deleted": stats.deleted,
            "entities_kept": stats.kept,
            "entities_skipped": stats.skipped,
        }

        # Use the counts directly - they're already in the right format
        if hasattr(stats, "entities_encountered"):
            update_data["entities_encountered"] = stats.entities_encountered

        return update_data

    def _build_timestamp_update_data(
        self,
        status: SyncJobStatus,
        started_at: Optional[datetime],
        completed_at: Optional[datetime],
        failed_at: Optional[datetime],
        error: Optional[str],
    ) -> Dict[str, Any]:
        """Build timestamp and error update data."""
        update_data = {}

        if started_at:
            update_data["started_at"] = started_at

        if status == SyncJobStatus.COMPLETED and completed_at:
            update_data["completed_at"] = completed_at
        elif status == SyncJobStatus.FAILED:
            if failed_at:
                update_data["failed_at"] = failed_at or utc_now_naive()
            if error:
                update_data["error"] = error

        return update_data

    async def _update_status_in_database(self, db, sync_job_id: UUID, status_value: str) -> None:
        """Update status field using raw SQL."""
        from sqlalchemy import text

        # Update status with string value directly
        await db.execute(
            text(
                "UPDATE sync_job SET status = :status, "
                "modified_at = :modified_at WHERE id = :sync_job_id"
            ),
            {
                "status": status_value,
                "modified_at": utc_now_naive(),
                "sync_job_id": sync_job_id,
            },
        )

    async def update_status(
        self,
        sync_job_id: UUID,
        status: SyncJobStatus,
        ctx: ApiContext,
        stats: Optional[SyncProgressUpdate] = None,
        error: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        failed_at: Optional[datetime] = None,
    ) -> None:
        """Update sync job status with provided details."""
        try:
            sync_id_for_analytics = None
            async with get_db_context() as db:
                db_sync_job = await crud.sync_job.get(db=db, id=sync_job_id, ctx=ctx)

                if not db_sync_job:
                    logger.error(f"Sync job {sync_job_id} not found")
                    return

                # Use the enum value directly (it's already a string)
                status_value = status.value
                logger.info(f"Updating sync job {sync_job_id} status to {status_value}")

                update_data = {"status": status}

                if stats:
                    stats_data = self._build_stats_update_data(stats)
                    update_data.update(stats_data)

                timestamp_data = self._build_timestamp_update_data(
                    status, started_at, completed_at, failed_at, error
                )
                update_data.update(timestamp_data)

                # Update status using raw SQL
                await self._update_status_in_database(db, sync_job_id, status_value)

                # Update other fields using the normal ORM
                # (excluding status which we already updated)
                update_data.pop("status")
                if update_data:
                    await crud.sync_job.update(
                        db=db,
                        db_obj=db_sync_job,
                        obj_in=schemas.SyncJobUpdate(**update_data),
                        ctx=ctx,
                    )

                # Capture sync_id before commit to avoid attribute expiration
                try:
                    sync_id_for_analytics = db_sync_job.sync_id
                except Exception:
                    sync_id_for_analytics = None

                await db.commit()
                logger.info(f"Successfully updated sync job {sync_job_id} status to {status_value}")

        except Exception as e:
            logger.error(f"Failed to update sync job status: {e}")
            return

        # Track analytics for sync completion outside DB context to avoid session issues
        if status == SyncJobStatus.COMPLETED and stats and sync_id_for_analytics is not None:
            try:
                await self._track_sync_completion(sync_job_id, sync_id_for_analytics, stats, ctx)
            except Exception as e:
                # Analytics failure should not be treated as status update failure
                logger.warning(
                    f"Failed to track sync completion analytics for job {sync_job_id}: {e}"
                )

    async def _track_sync_completion(
        self, sync_job_id: UUID, sync_id: UUID, stats: SyncProgressUpdate, ctx: ApiContext
    ) -> None:
        """Track detailed analytics for sync completion with entity counts per type.

        Note: High-level sync completion is tracked by the orchestrator using business_events.
        This method only tracks detailed entity-type breakdowns for analysis.
        """
        try:
            # Track individual entity type counts for detailed analysis
            if hasattr(stats, "entities_encountered") and stats.entities_encountered:
                for entity_type, entity_count in stats.entities_encountered.items():
                    user_id = str(ctx.user.id) if ctx.user else f"api_key_{ctx.organization.id}"
                    analytics.track_event(
                        event_name="entities_synced_by_type",
                        distinct_id=user_id,
                        properties={
                            "sync_job_id": str(sync_job_id),
                            "sync_id": str(sync_id),
                            "entity_type": entity_type,
                            "entity_count": entity_count,
                            "organization_name": getattr(ctx.organization, "name", "unknown"),
                        },
                        groups={"organization": str(ctx.organization.id)},
                    )

            logger.info(f"Tracked sync completion analytics for job {sync_job_id} (sync {sync_id})")

        except Exception as e:
            logger.exception(f"Failed to track sync completion analytics: {e}")


# Singleton instance
sync_job_service = SyncJobService()
