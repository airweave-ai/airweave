"""Temporal activities for API key cleanup and maintenance.

Activities:
- CleanupRevokedKeysActivity: delete revoked keys past 90-day retention
- ExpirePastDueKeysActivity: transition active keys past expiration to expired
- PruneUsageLogActivity: delete usage log entries older than 90 days
"""

from dataclasses import dataclass

from temporalio import activity

from airweave.core.logging import logger
from airweave.db.session import get_db_context
from airweave.domains.organizations.protocols import ApiKeyMaintenanceProtocol


@dataclass
class CleanupRevokedKeysActivity:
    """Delete revoked API keys past the 90-day retention period."""

    api_key_repo: ApiKeyMaintenanceProtocol

    @activity.defn(name="cleanup_revoked_keys_activity")
    async def run(self) -> dict[str, int]:
        """Remove revoked keys past their retention period.

        Usage log entries survive via SET NULL on the FK.

        Returns:
            Counts of deleted and errored keys.
        """
        logger.info("Starting revoked API key cleanup")

        deleted = 0
        errors = 0
        try:
            async with get_db_context() as db:
                keys = await self.api_key_repo.get_revoked_keys_older_than(
                    db,
                    max_age_days=90,
                )
                for key in keys:
                    try:
                        await db.delete(key)
                        await db.flush()
                        deleted += 1
                    except Exception as e:
                        logger.error(
                            "Failed to delete revoked key",
                            key_id=str(key.id),
                            error=str(e),
                            exc_info=True,
                        )
                        errors += 1
                await db.commit()
        except Exception as e:
            logger.error("Revoked key cleanup failed", error=str(e), exc_info=True)
            raise

        logger.info("Revoked API key cleanup complete", deleted_count=deleted, error_count=errors)
        return {"deleted": deleted, "errors": errors}


@dataclass
class ExpirePastDueKeysActivity:
    """Transition active keys past their expiration date to expired status."""

    api_key_repo: ApiKeyMaintenanceProtocol

    @activity.defn(name="expire_past_due_keys_activity")
    async def run(self) -> dict[str, int]:
        """Expire active keys past their expiration date.

        Returns:
            Count of keys transitioned to expired.
        """
        logger.info("Starting past-due API key expiration")

        try:
            async with get_db_context() as db:
                count = await self.api_key_repo.expire_past_due_keys(db)
                await db.commit()
        except Exception as e:
            logger.error("Past-due key expiration failed", error=str(e), exc_info=True)
            raise

        logger.info("Past-due API key expiration complete", expired_count=count)
        return {"expired": count}


@dataclass
class PruneUsageLogActivity:
    """Delete usage log entries older than 90 days."""

    api_key_repo: ApiKeyMaintenanceProtocol

    @activity.defn(name="prune_usage_log_activity")
    async def run(self) -> dict[str, int]:
        """Prune old usage log entries.

        Returns:
            Count of log entries deleted.
        """
        logger.info("Starting usage log pruning")

        try:
            async with get_db_context() as db:
                count = await self.api_key_repo.prune_usage_log(db, max_age_days=90)
                await db.commit()
        except Exception as e:
            logger.error("Usage log pruning failed", error=str(e), exc_info=True)
            raise

        logger.info("Usage log pruning complete", deleted_count=count)
        return {"pruned": count}
