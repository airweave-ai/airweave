"""No-op processor for storage destinations."""

from typing import TYPE_CHECKING, List

from airweave.platform.entities._base import BaseEntity
from airweave.platform.sync.processors.protocol import ContentProcessor

if TYPE_CHECKING:
    from airweave.platform.sync.context import SyncContext


class RawProcessor(ContentProcessor):
    """Processor that passes entities through unchanged.

    Used by storage destinations that don't need any content processing.
    """

    async def process(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> List[BaseEntity]:
        """Pass entities through unchanged."""
        sync_context.logger.debug(f"Passing through {len(entities)} entities")
        return entities
