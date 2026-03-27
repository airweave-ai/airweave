"""Temporal activity: expire active keys past their expiration date."""

from dataclasses import dataclass

from temporalio import activity

from airweave.core.logging import logger
from airweave.db.session import get_db_context
from airweave.domains.organizations.protocols import ApiKeyMaintenanceProtocol


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
            logger.with_context(error=str(e)).error("Past-due key expiration failed", exc_info=True)
            raise

        logger.with_context(expired_count=count).info("Past-due API key expiration complete")
        return {"expired": count}
