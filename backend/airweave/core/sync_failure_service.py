"""Service for managing sync failure tracking and health status."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.core.datetime_utils import utc_now_naive
from airweave.core.logging import logger
from airweave.platform.sync.exceptions import SyncError


class SyncFailureService:
    """Manages sync failure tracking and health status for source connections."""

    FAILURE_THRESHOLDS = {
        "AUTH": 1,  # Pause immediately on auth failure
        "VALIDATION": 3,  # Pause after 3 consecutive validation failures
        "PERMANENT": 3,  # Pause after 3 consecutive permanent failures
        "CONFIG": None,  # Never pause (engineering issue, keep retrying)
        "TRANSIENT": None,  # Never count toward threshold (infrastructure issues)
    }

    async def record_failure(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        error: SyncError,
        ctx: ApiContext,
    ) -> bool:
        """Record a sync failure and return whether schedules should be paused.

        Args:
            db: Database session
            source_connection_id: ID of the source connection that failed
            error: The sync error that occurred
            ctx: API context

        Returns:
            True if schedules should be paused, False otherwise
        """
        # Get current source connection
        source_conn = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_conn:
            logger.error(
                f"Source connection {source_connection_id} not found when recording failure"
            )
            return False

        # Check if this error type should count toward threshold
        threshold = self.FAILURE_THRESHOLDS.get(error.error_category)
        if threshold is None:
            # Don't count CONFIG or TRANSIENT errors
            logger.info(
                f"Skipping failure tracking for {error.error_category} error "
                f"(source_connection_id={source_connection_id})"
            )
            # Still update last_failure fields for visibility, but don't increment counter
            await crud.source_connection.update(
                db=db,
                db_obj=source_conn,
                obj_in={
                    "last_failure_at": utc_now_naive(),
                    "last_failure_reason": error.get_user_message(),
                    "last_failure_category": error.error_category,
                },
                ctx=ctx,
            )
            return False

        # Increment failure counter if error should count
        if error.should_deschedule:
            new_consecutive_failures = source_conn.consecutive_failures + 1
        else:
            # Don't increment if error explicitly says not to deschedule
            new_consecutive_failures = source_conn.consecutive_failures

        # Compute new health status
        new_health_status = self.compute_health_status(
            consecutive_failures=new_consecutive_failures,
            last_failure_category=error.error_category,
        )

        # Update source connection with failure details
        await crud.source_connection.update(
            db=db,
            db_obj=source_conn,
            obj_in={
                "consecutive_failures": new_consecutive_failures,
                "last_failure_at": utc_now_naive(),
                "last_failure_reason": error.get_user_message(),
                "last_failure_category": error.error_category,
                "health_status": new_health_status,
            },
            ctx=ctx,
        )

        # Check if threshold reached
        should_pause = new_consecutive_failures >= threshold

        if should_pause:
            logger.warning(
                f"Failure threshold reached for source_connection_id={source_connection_id}: "
                f"{new_consecutive_failures}/{threshold} {error.error_category} failures. "
                f"Schedules should be paused."
            )
        else:
            logger.info(
                f"Recorded failure {new_consecutive_failures}/{threshold} for "
                f"source_connection_id={source_connection_id}, category={error.error_category}"
            )

        return should_pause

    async def reset_failures(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
    ) -> None:
        """Reset failure counters after successful sync or validation.

        Args:
            db: Database session
            source_connection_id: ID of the source connection
            ctx: API context
        """
        source_conn = await crud.source_connection.get(
            db=db, id=source_connection_id, ctx=ctx
        )
        if not source_conn:
            logger.error(
                f"Source connection {source_connection_id} not found when resetting failures"
            )
            return

        # Only reset if there were failures
        if source_conn.consecutive_failures > 0:
            logger.info(
                f"Resetting failure counters for source_connection_id={source_connection_id} "
                f"(was {source_conn.consecutive_failures} failures)"
            )

            await crud.source_connection.update(
                db=db,
                db_obj=source_conn,
                obj_in={
                    "consecutive_failures": 0,
                    "last_failure_at": None,
                    "last_failure_reason": None,
                    "last_failure_category": None,
                    "health_status": "HEALTHY",
                },
                ctx=ctx,
            )

    def compute_health_status(
        self,
        consecutive_failures: int,
        last_failure_category: Optional[str],
    ) -> str:
        """Compute health status based on failure count and category.

        Args:
            consecutive_failures: Number of consecutive failures
            last_failure_category: Category of the last failure

        Returns:
            Health status string: HEALTHY, DEGRADED, BLOCKED, or REQUIRES_AUTH
        """
        # No failures = healthy
        if consecutive_failures == 0:
            return "HEALTHY"

        # AUTH failures always show REQUIRES_AUTH
        if last_failure_category == "AUTH":
            return "REQUIRES_AUTH"

        # Check if threshold reached for this category
        threshold = self.FAILURE_THRESHOLDS.get(last_failure_category or "")
        if threshold and consecutive_failures >= threshold:
            return "BLOCKED"

        # 1-2 failures (below threshold) = degraded
        return "DEGRADED"


# Singleton instance
sync_failure_service = SyncFailureService()

