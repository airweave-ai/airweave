"""Module for sync context."""

from typing import Optional
from uuid import UUID

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.logging import ContextualLogger
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.cursor import SyncCursor
from airweave.platform.sync.pubsub import SyncEntityStateTracker, SyncProgress


class SyncContext:
    """Context container for a sync.

    Contains all the necessary components for a sync:
    - source - the source instance
    - destinations - the destination instances
    - sync - the main sync object
    - sync job - the sync job that is created for the sync
    - progress - the progress tracker, interfaces with PubSub
    - cursor - the cursor for the sync
    - collection - the collection that the sync is for
    - connection - the source connection that the sync is for
    - guard rail - the guard rail service
    - logger - contextual logger with sync job metadata

    Concurrency / batching controls:
    - should_batch - if True, use micro-batched pipeline; if False, process per-entity (legacy)
    - batch_size - max parents per micro-batch (default 64)
    - max_batch_latency_ms - max time to wait before flushing a non-full batch (default 200ms)
    """

    source: BaseSource
    destinations: list[BaseDestination]
    sync: schemas.Sync
    sync_job: schemas.SyncJob
    progress: SyncProgress
    entity_state_tracker: Optional[SyncEntityStateTracker]
    cursor: SyncCursor
    collection: schemas.Collection
    connection: schemas.Connection
    entity_map: dict[type[BaseEntity], UUID]
    ctx: ApiContext
    guard_rail: GuardRailService
    logger: ContextualLogger

    force_full_sync: bool = False
    # Whether any destination supports keyword (sparse) indexing. Set once before run.
    has_keyword_index: bool = False

    # batching knobs (read by SyncOrchestrator at init)
    should_batch: bool = True
    batch_size: int = 64
    max_batch_latency_ms: int = 200

    def __init__(
        self,
        source: BaseSource,
        destinations: list[BaseDestination],
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        progress: SyncProgress,
        entity_state_tracker: Optional[SyncEntityStateTracker],
        cursor: SyncCursor,
        collection: schemas.Collection,
        connection: schemas.Connection,
        entity_map: dict[type[BaseEntity], UUID],
        ctx: ApiContext,
        guard_rail: GuardRailService,
        logger: ContextualLogger,
        force_full_sync: bool = False,
        # Micro-batching controls
        should_batch: bool = True,
        batch_size: int = 64,
        max_batch_latency_ms: int = 200,
        has_keyword_index: bool = False,
    ):
        """Initialize the sync context."""
        self.source = source
        self.destinations = destinations
        self.sync = sync
        self.sync_job = sync_job
        self.progress = progress
        self.entity_state_tracker = entity_state_tracker
        self.cursor = cursor
        self.collection = collection
        self.connection = connection
        self.entity_map = entity_map
        self.ctx = ctx
        self.guard_rail = guard_rail
        self.logger = logger
        self.force_full_sync = force_full_sync

        # Concurrency / batching knobs
        self.should_batch = should_batch
        self.batch_size = batch_size
        self.max_batch_latency_ms = max_batch_latency_ms
        # Destination capabilities (precomputed)
        self.has_keyword_index = has_keyword_index
