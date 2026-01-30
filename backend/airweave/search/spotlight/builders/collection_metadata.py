"""Builder for SpotlightCollectionMetadata."""

from airweave.search.spotlight.external.database import SpotlightDatabaseInterface
from airweave.search.spotlight.schemas import SpotlightCollectionMetadata


class SpotlightCollectionMetadataBuilder:
    """Builds SpotlightCollectionMetadata from database."""

    def __init__(self, db: SpotlightDatabaseInterface):
        """Initialize with a database interface."""
        self.db = db

    async def build(self, collection_readable_id: str) -> SpotlightCollectionMetadata:
        """Build collection metadata."""
        # TODO: implement
        ...
