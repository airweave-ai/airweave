"""Temporal activity for marking a sync job as cancelled."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from temporalio import activity

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.core.shared_models import SyncJobStatus
from airweave.domains.syncs.protocols import SyncJobServiceProtocol


@dataclass
class MarkSyncJobCancelledActivity:
    """Mark a sync job as CANCELLED.

    Used when workflow cancels before activity starts.
    """

    sync_job_service: SyncJobServiceProtocol

    @activity.defn(name="mark_sync_job_cancelled_activity")
    async def run(
        self,
        sync_job_id: str,
        ctx_dict: Dict[str, Any],
        reason: Optional[str] = None,
        when_iso: Optional[str] = None,
    ) -> None:
        """Mark the given sync job as CANCELLED."""
        organization = schemas.Organization(**ctx_dict["organization"])
        ctx = BaseContext(organization=organization)
        ctx.logger = ctx.logger.with_context(sync_job_id=sync_job_id)

        failed_at: Optional[datetime] = None
        if when_iso:
            try:
                failed_at = datetime.fromisoformat(when_iso)
            except Exception:
                failed_at = None

        ctx.logger.debug(
            f"[WORKFLOW] Marking sync job {sync_job_id} as CANCELLED (pre-activity): {reason or ''}"
        )

        try:
            await self.sync_job_service.update_status(
                sync_job_id=UUID(sync_job_id),
                status=SyncJobStatus.CANCELLED,
                ctx=ctx,  # type: ignore[arg-type]
                error=reason,
                failed_at=failed_at,
            )
            ctx.logger.debug(f"[WORKFLOW] Updated job {sync_job_id} to CANCELLED")
        except Exception as e:
            ctx.logger.error(f"Failed to update job {sync_job_id} to CANCELLED: {e}")
            raise
