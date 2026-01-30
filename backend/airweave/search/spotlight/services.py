"""Services container for spotlight search.

This is the composition root - where external dependencies are wired together.
"""

from airweave.api.context import ApiContext
from airweave.search.spotlight.config import DatabaseImpl, config
from airweave.search.spotlight.external.database import SpotlightDatabaseInterface


class SpotlightServices:
    """Container for external dependencies."""

    def __init__(self, db: SpotlightDatabaseInterface):
        """Initialize with external dependencies."""
        self.db = db

    @classmethod
    async def create(cls, ctx: ApiContext) -> "SpotlightServices":
        """Create services based on config."""
        db = await cls._create_db(ctx)
        return cls(db=db)

    @staticmethod
    async def _create_db(ctx: ApiContext) -> SpotlightDatabaseInterface:
        """Create database based on config."""
        if config.DATABASE_IMPL == DatabaseImpl.POSTGRESQL:
            from airweave.search.spotlight.external.database.postgresql import (
                PostgreSQLSpotlightDatabase,
            )

            return await PostgreSQLSpotlightDatabase.create(ctx)

        raise ValueError(f"Unknown database implementation: {config.DATABASE_IMPL}")
