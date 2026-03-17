"""Protocols for the ARF (Airweave Raw Format) domain.

ArfServiceProtocol covers the write path (capture during sync).
ArfReaderProtocol covers the read path (replay / inspection).
"""

from typing import Any, AsyncGenerator, Dict, List, Optional, Protocol

from airweave.domains.arf.types import SyncManifest
from airweave.domains.sync_pipeline.contexts import SyncContext
from airweave.domains.sync_pipeline.contexts.runtime import SyncRuntime
from airweave.platform.entities._base import BaseEntity


class ArfServiceProtocol(Protocol):
    """Write-path contract for ARF entity capture."""

    async def upsert_manifest(
        self,
        sync_context: SyncContext,
        runtime: SyncRuntime,
        vector_size: int,
        embedding_model_name: str,
    ) -> None:
        """Create or update the sync manifest."""
        ...

    async def upsert_entities(self, entities: List[BaseEntity], sync_context: SyncContext) -> int:
        """Store or update entities. Returns count stored."""
        ...

    async def delete_entities(self, entity_ids: List[str], sync_context: SyncContext) -> int:
        """Delete entities by ID. Returns count deleted."""
        ...

    async def cleanup_stale_entities(self, sync_context: SyncContext, runtime: SyncRuntime) -> int:
        """Remove entities not seen during current sync."""
        ...

    async def get_entity_count(self, sync_id: str) -> int:
        """Count entities in an ARF store."""
        ...

    async def sync_exists(self, sync_id: str) -> bool:
        """Check whether an ARF store exists for a sync."""
        ...

    async def delete_sync(self, sync_id: str) -> bool:
        """Delete the entire ARF store for a sync."""
        ...

    async def get_manifest(self, sync_id: str) -> Optional[SyncManifest]:
        """Retrieve the manifest for a sync."""
        ...

    async def get_replay_stats(self, sync_id: str) -> Dict[str, Any]:
        """Return replay statistics for a sync's ARF store."""
        ...


class ArfReaderProtocol(Protocol):
    """Read-path contract for ARF entity replay."""

    async def validate(self) -> bool:
        """Check that ARF data exists and is readable."""
        ...

    async def read_manifest(self) -> Dict[str, Any]:
        """Read the manifest dict."""
        ...

    async def get_entity_count(self) -> int:
        """Count entity files."""
        ...

    async def iter_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Iterate over reconstructed entities."""
        ...

    def cleanup(self) -> None:
        """Clean up temp files created during replay."""
        ...
