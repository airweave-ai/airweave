"""Temporal activity: prune old API key usage log entries."""

from dataclasses import dataclass

from temporalio import activity

from airweave.core.logging import logger
from airweave.db.session import get_db_context
from airweave.domains.organizations.protocols import ApiKeyMaintenanceProtocol


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
            logger.with_context(error=str(e)).error("Usage log pruning failed", exc_info=True)
            raise

        logger.with_context(deleted_count=count).info("Usage log pruning complete")
        return {"pruned": count}
