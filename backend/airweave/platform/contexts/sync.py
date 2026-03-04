"""Sync context - frozen data for sync operations."""

from dataclasses import dataclass, field
from typing import Dict, Optional
from uuid import UUID

from airweave import schemas
from airweave.core.context import BaseContext
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sync.config.base import SyncConfig


@dataclass
class SyncContext(BaseContext):
    """Frozen data describing a sync run.

    Sibling to ApiContext — inherits organization and logger from BaseContext.
    Contains only IDs, schema objects, config, and lookups. No live services.

    Live services (source, cursor, destinations, trackers) live in SyncRuntime.

    Can be passed as ctx to CRUD operations since it IS a BaseContext.
    """

    # --- Scope IDs ---
    sync_id: UUID
    sync_job_id: UUID
    collection_id: UUID
    source_connection_id: UUID

    # --- Schema objects ---
    sync: schemas.Sync
    sync_job: schemas.SyncJob
    collection: schemas.CollectionRecord
    connection: schemas.Connection

    # --- Config ---
    execution_config: Optional[SyncConfig] = None
    force_full_sync: bool = False
    batch_size: int = 64
    max_batch_latency_ms: int = 200

    # --- Lookups ---
    entity_map: Dict[type[BaseEntity], UUID] = field(default_factory=dict)

    # --- Derived data (extracted from source at build time) ---
    source_short_name: str = ""

    # --- Convenience ---

    @property
    def organization_id(self) -> UUID:
        """Organization ID from inherited BaseContext."""
        return self.organization.id

    @property
    def should_batch(self) -> bool:
        """Whether batching is enabled (always True for now)."""
        return True
