"""Temporal activities for API key cleanup and maintenance.

Activities:
- CleanupRevokedKeysActivity: delete revoked keys past 90-day retention
- ExpirePastDueKeysActivity: transition active keys past expiration to expired
- PruneUsageLogActivity: delete usage log entries older than 90 days
"""

from dataclasses import dataclass

from temporalio import activity

from airweave import crud
from airweave.core.logging import logger
from airweave.db.session import get_db_context


@dataclass
class CleanupRevokedKeysActivity:
    """Delete revoked API keys past the 90-day retention period."""

    @activity.defn(name="cleanup_revoked_keys_activity")
    async def run(self) -> int:
        """Remove revoked keys past their retention period.

        Usage log entries survive via SET NULL on the FK.

        Returns:
            Number of keys deleted.
        """
        logger.info("Starting revoked API key cleanup")

        deleted = 0
        try:
            async with get_db_context() as db:
                keys = await crud.api_key.get_revoked_keys_older_than(
                    db, max_age_days=90,
                )
                for key in keys:
                    try:
                        await db.delete(key)
                        deleted += 1
                    except Exception as e:
                        logger.error(
                            f"Failed to delete revoked key {key.id}: {e}",
                            exc_info=True,
                        )
                await db.commit()
        except Exception as e:
            logger.error(f"Revoked key cleanup failed: {e}", exc_info=True)
            raise

        logger.info(f"Revoked API key cleanup complete: {deleted} keys deleted")
        return deleted


@dataclass
class ExpirePastDueKeysActivity:
    """Transition active keys past their expiration date to expired status."""

    @activity.defn(name="expire_past_due_keys_activity")
    async def run(self) -> int:
        """Expire active keys past their expiration date.

        Returns:
            Number of keys transitioned to expired.
        """
        logger.info("Starting past-due API key expiration")

        try:
            async with get_db_context() as db:
                count = await crud.api_key.expire_past_due_keys(db)
                await db.commit()
        except Exception as e:
            logger.error(f"Past-due key expiration failed: {e}", exc_info=True)
            raise

        logger.info(f"Past-due API key expiration complete: {count} keys expired")
        return count


@dataclass
class PruneUsageLogActivity:
    """Delete usage log entries older than 90 days."""

    @activity.defn(name="prune_usage_log_activity")
    async def run(self) -> int:
        """Prune old usage log entries.

        Returns:
            Number of log entries deleted.
        """
        logger.info("Starting usage log pruning")

        try:
            async with get_db_context() as db:
                count = await crud.api_key.prune_usage_log(db, max_age_days=90)
                await db.commit()
        except Exception as e:
            logger.error(f"Usage log pruning failed: {e}", exc_info=True)
            raise

        logger.info(f"Usage log pruning complete: {count} entries deleted")
        return count
