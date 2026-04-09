"""Temporal activity: delete revoked API keys past retention."""

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
                        async with db.begin_nested():
                            await db.delete(key)
                            await db.flush()
                        deleted += 1
                    except Exception as e:
                        logger.with_context(
                            key_id=str(key.id),
                            error=str(e),
                        ).error("Failed to delete revoked key", exc_info=True)
                        errors += 1
                await db.commit()
        except Exception as e:
            logger.with_context(error=str(e)).error("Revoked key cleanup failed", exc_info=True)
            raise

        logger.with_context(deleted_count=deleted, error_count=errors).info(
            "Revoked API key cleanup complete"
        )
        return {"deleted": deleted, "errors": errors}
