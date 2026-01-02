"""Replay source - reads entities from ARF storage for replay operations.

Enables replaying raw entities from ARF to new destinations without
hitting the source again. Used for migration workflows.
"""

from typing import AsyncGenerator

from airweave.core.logging import ContextualLogger
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.raw_data import raw_data_service


class ARFReplaySource(BaseSource):
    """Pseudo-source that reads entities from ARF storage.

    This allows reusing the SyncOrchestrator pipeline for replay operations.
    Instead of fetching from an external API, it iterates over the ARF store.
    """

    _name = "ARF Replay"
    _short_name = "arf_replay"
    _auth_type = None

    def __init__(self, sync_id: str, logger: ContextualLogger):
        """Initialize ARF replay source.

        Args:
            sync_id: Sync ID to replay from
            logger: Contextual logger
        """
        self._sync_id = sync_id
        self.logger = logger

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from ARF store.

        Yields:
            BaseEntity instances reconstructed from ARF
        """
        self.logger.info(f"Starting ARF replay for sync {self._sync_id}")
        count = 0

        async for entity in raw_data_service.iter_entities_for_replay(self._sync_id):
            count += 1
            if count % 100 == 0:
                self.logger.debug(f"Replayed {count} entities from ARF")
            yield entity

        self.logger.info(f"ARF replay completed: {count} entities yielded")
