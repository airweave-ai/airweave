"""Sync context - full context for sync operations."""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from airweave.platform.contexts.batch import BatchContext
from airweave.platform.contexts.destinations import DestinationsContext
from airweave.platform.contexts.infra import InfraContext
from airweave.platform.contexts.scope import ScopeContext
from airweave.platform.contexts.source import SourceContext
from airweave.platform.contexts.tracking import TrackingContext

if TYPE_CHECKING:
    from airweave import schemas
    from airweave.platform.sync.config import SyncConfig


@dataclass
class SyncContext:
    """Full context for sync operations.

    Composes all sub-contexts at depth 1. Each sub-context represents
    a disjoint concern that can be built independently.

    Sub-contexts:
    - scope: Scopes the operation (sync_id, collection_id, organization_id)
    - infra: Core infrastructure (ctx, logger)
    - source: Source pipeline (source instance, cursor)
    - destinations: Destination pipeline (destinations, entity_map)
    - tracking: Progress tracking (entity_tracker, state_publisher, guard_rail)
    - batch: Batch processing settings

    Schema objects are kept at top level for convenience.
    """

    # Composed contexts (depth 1)
    scope: ScopeContext
    infra: InfraContext
    source: SourceContext
    destinations: DestinationsContext
    tracking: TrackingContext
    batch: BatchContext

    # Schema objects (frequently accessed)
    sync: "schemas.Sync"
    sync_job: "schemas.SyncJob"
    collection: "schemas.Collection"
    connection: "schemas.Connection"

    # Execution config
    execution_config: Optional["SyncConfig"] = None

    # -------------------------------------------------------------------------
    # HandlerContext Protocol Implementation
    # -------------------------------------------------------------------------

    @property
    def sync_id(self):
        """Sync ID for scoping operations."""
        return self.scope.sync_id

    @property
    def collection_id(self):
        """Collection ID for scoping operations."""
        return self.scope.collection_id

    @property
    def organization_id(self):
        """Organization ID for access control."""
        return self.scope.organization_id

    @property
    def source_connection_id(self):
        """User-facing source connection ID."""
        return self.scope.source_connection_id

    @property
    def logger(self):
        """Logger for operations."""
        return self.infra.logger

    @property
    def ctx(self):
        """API context for CRUD operations."""
        return self.infra.ctx

    # -------------------------------------------------------------------------
    # Convenience Accessors (common access patterns)
    # -------------------------------------------------------------------------

    @property
    def entity_map(self):
        """Shortcut to destinations.entity_map."""
        return self.destinations.entity_map

    @property
    def cursor(self):
        """Shortcut to source.cursor."""
        return self.source.cursor

    @property
    def source_instance(self):
        """Shortcut to source.source (the actual BaseSource instance)."""
        return self.source.source

    @property
    def destination_list(self):
        """Shortcut to destinations.destinations (the list of BaseDestination)."""
        return self.destinations.destinations

    @property
    def entity_tracker(self):
        """Shortcut to tracking.entity_tracker."""
        return self.tracking.entity_tracker

    @property
    def state_publisher(self):
        """Shortcut to tracking.state_publisher."""
        return self.tracking.state_publisher

    @property
    def guard_rail(self):
        """Shortcut to tracking.guard_rail."""
        return self.tracking.guard_rail

    @property
    def force_full_sync(self):
        """Shortcut to batch.force_full_sync."""
        return self.batch.force_full_sync

    @property
    def should_batch(self):
        """Shortcut to batch.should_batch."""
        return self.batch.should_batch

    @property
    def batch_size(self):
        """Shortcut to batch.batch_size."""
        return self.batch.batch_size

    @property
    def max_batch_latency_ms(self):
        """Shortcut to batch.max_batch_latency_ms."""
        return self.batch.max_batch_latency_ms
