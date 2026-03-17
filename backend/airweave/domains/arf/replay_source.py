"""ARF Replay source for automatic replay from ARF storage.

Internal source (NOT decorated, NOT registered) injected by SourceContextBuilder
when execution_config.behavior.replay_from_arf=True.

Unlike SnapshotSource (user-facing for evals), this source:
- Is automatically created by the builder
- Uses the sync's existing ARF data (no path config needed)
- Is never exposed via the API
"""

from typing import AsyncGenerator, Optional
from uuid import UUID

from airweave.core.logging import ContextualLogger
from airweave.domains.arf.reader import ArfReader
from airweave.domains.storage.protocols import StorageBackend
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource


class ArfReplaySource(BaseSource):
    """Internal source for replaying entities from ARF storage.

    Masquerades as the original source so entities appear to come from
    the original source (short_name passed from builder/DB).
    """

    source_name = "ARF Replay"
    short_name = "arf_replay"

    def __init__(  # noqa: D107
        self,
        sync_id: UUID,
        storage: StorageBackend,
        logger: Optional[ContextualLogger] = None,
        restore_files: bool = True,
        original_short_name: Optional[str] = None,
    ) -> None:
        super().__init__()
        self.sync_id = sync_id
        self._storage = storage
        self._logger = logger
        self.restore_files = restore_files
        self._reader: Optional[ArfReader] = None

        if original_short_name:
            self.short_name = original_short_name
            self.source_name = f"ARF Replay ({original_short_name})"

    @property
    def reader(self) -> ArfReader:
        """Get or create ARF reader."""
        if self._reader is None:
            self._reader = ArfReader(
                sync_id=self.sync_id,
                storage=self._storage,
                logger=self.logger,
                restore_files=self.restore_files,
            )
        return self._reader

    @classmethod
    async def create(
        cls,
        sync_id: UUID,
        storage: StorageBackend,
        logger: Optional[ContextualLogger] = None,
        restore_files: bool = True,
        original_short_name: Optional[str] = None,
    ) -> "ArfReplaySource":
        """Factory method to create a configured ArfReplaySource."""
        return cls(
            sync_id=sync_id,
            storage=storage,
            logger=logger,
            restore_files=restore_files,
            original_short_name=original_short_name,
        )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from ARF storage."""
        self.logger.info(f"ARF Replay: Reading entities from sync {self.sync_id}")
        async for entity in self.reader.iter_entities():
            yield entity

    async def validate(self) -> bool:
        """Validate that ARF data exists for this sync."""
        return await self.reader.validate()

    def cleanup(self) -> None:
        """Clean up temp files."""
        if self._reader:
            self._reader.cleanup()
