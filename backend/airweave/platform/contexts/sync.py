"""Sync context - full context for sync operations."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional
from uuid import UUID

from airweave.core.context import BaseContext

if TYPE_CHECKING:
    from airweave import schemas
    from airweave.core.guard_rail_service import GuardRailService
    from airweave.platform.destinations._base import BaseDestination
    from airweave.platform.entities._base import BaseEntity
    from airweave.platform.sources._base import BaseSource
    from airweave.platform.sync.config import SyncConfig
    from airweave.platform.sync.cursor import SyncCursor
    from airweave.platform.sync.pipeline.entity_tracker import EntityTracker
    from airweave.platform.sync.state_publisher import SyncStatePublisher


@dataclass
class SyncContext(BaseContext):
    """Everything needed for a sync run.

    Inherits organization, user, and logger from BaseContext.
    The builder overrides logger with sync-specific dimensions
    (sync_id, sync_job_id, collection_readable_id, etc.).

    Can be passed directly as ctx to CRUD operations since it IS a BaseContext.
    """

    # --- Scope ---
    sync_id: UUID = None
    sync_job_id: UUID = None
    collection_id: UUID = None
    source_connection_id: UUID = None

    # --- Source pipeline ---
    source: "BaseSource" = None
    cursor: "SyncCursor" = None

    # --- Destination pipeline ---
    destinations: List["BaseDestination"] = field(default_factory=list)
    entity_map: Dict[type["BaseEntity"], UUID] = field(default_factory=dict)

    # --- Tracking ---
    entity_tracker: "EntityTracker" = None
    state_publisher: "SyncStatePublisher" = None
    guard_rail: "GuardRailService" = None

    # --- Batch config ---
    batch_size: int = 64
    max_batch_latency_ms: int = 200
    force_full_sync: bool = False

    # --- Schema objects (frequently accessed by pipeline) ---
    sync: "schemas.Sync" = None
    sync_job: "schemas.SyncJob" = None
    collection: "schemas.Collection" = None
    connection: "schemas.Connection" = None

    # --- Execution config ---
    execution_config: Optional["SyncConfig"] = None

    # --- Convenience ---

    @property
    def organization_id(self) -> UUID:
        """Organization ID from inherited BaseContext."""
        return self.organization.id

    @property
    def source_instance(self) -> "BaseSource":
        """Alias for source (used by orchestrator)."""
        return self.source

    @property
    def destination_list(self) -> List["BaseDestination"]:
        """Alias for destinations list."""
        return self.destinations

    @property
    def should_batch(self) -> bool:
        """Whether batching is enabled (always True for now)."""
        return True

    @property
    def ctx(self) -> "BaseContext":
        """Self-reference for backwards compat during migration.

        Code that does sync_context.ctx can continue to work.
        Will be removed once all callsites are updated.
        """
        return self
