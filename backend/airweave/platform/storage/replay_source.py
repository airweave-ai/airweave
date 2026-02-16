"""ARF Replay source for automatic replay from ARF storage.

This is an INTERNAL source that is NOT decorated and NOT registered.
It gets injected by SourceContextBuilder when execution_config.behavior.replay_from_arf=True.

Unlike SnapshotSource (which is user-facing for evals), this source:
- Is automatically created by the builder
- Uses the sync's existing ARF data (no path config needed)
- Is never exposed via the API
"""

from typing import TYPE_CHECKING, AsyncGenerator, Optional
from uuid import UUID

from airweave.core.logging import ContextualLogger
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.storage.arf_reader import ArfReader
from airweave.platform.storage.protocol import StorageBackend

if TYPE_CHECKING:
    pass


class ArfReplaySource(BaseSource):
    """Internal source for replaying entities from ARF storage.

    This source is NOT decorated - it's not a registered source.
    It's created internally when execution_config.behavior.replay_from_arf=True.

    It masquerades as the original source (short_name passed from builder/DB),
    so entities appear to come from the original source.
    """

    # Fallback attributes (overridden per-instance from manifest)
    source_name = "ARF Replay"
    short_name = "arf_replay"

    def __init__(
        self,
        sync_id: UUID,
        storage: Optional[StorageBackend] = None,
        logger: Optional[ContextualLogger] = None,
        restore_files: bool = True,
        original_short_name: Optional[str] = None,
    ):
        """Initialize ARF replay source.

        Args:
            sync_id: Sync ID to replay ARF data from
            storage: Storage backend (uses singleton if not provided)
            logger: Logger instance
            restore_files: Whether to restore file attachments
            original_short_name: Original source short_name (from builder/DB)
        """
        super().__init__()
        self.sync_id = sync_id
        self._storage = storage
        self._logger = logger
        self.restore_files = restore_files
        self._reader: Optional[ArfReader] = None

        # Masquerade as original source if known
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
        storage: Optional[StorageBackend] = None,
        logger: Optional[ContextualLogger] = None,
        restore_files: bool = True,
        original_short_name: Optional[str] = None,
    ) -> "ArfReplaySource":
        """Create ARF replay source.

        Args:
            sync_id: Sync ID to replay from
            storage: Storage backend
            logger: Logger instance
            restore_files: Whether to restore files
            original_short_name: Original source short_name (from builder/DB)

        Returns:
            Configured ArfReplaySource that masquerades as original source
        """
        return cls(
            sync_id=sync_id,
            storage=storage,
            logger=logger,
            restore_files=restore_files,
            original_short_name=original_short_name,
        )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from ARF storage.

        Yields:
            Reconstructed BaseEntity instances
        """
        self.logger.info(f"🔄 ARF Replay: Reading entities from sync {self.sync_id}")

        async for entity in self.reader.iter_entities():
            yield entity

    async def validate(self) -> bool:
        """Validate that ARF data exists for this sync."""
        return await self.reader.validate()

    def cleanup(self) -> None:
        """Clean up temp files."""
        if self._reader:
            self._reader.cleanup()
