"""Module for sync context."""

from typing import Optional
from uuid import UUID

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.guard_rail_service import GuardRailService
from airweave.core.logging import ContextualLogger
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.embedding_models._base import BaseEmbeddingModel
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.cursor import SyncCursor
from airweave.platform.sync.pubsub import SyncProgress
from airweave.platform.sync.router import SyncDAGRouter


class SyncContext:
    """Context container for a sync.

    Contains all the necessary components for a sync:
    - source - the source instance
    - destinations - the destination instances
    - embedding model - the embedding model used for the sync
    - keyword indexing model - the keyword indexing model used for the sync
    - transformers - a dictionary of transformer callables
    - sync - the main sync object
    - sync job - the sync job that is created for the sync
    - dag - the DAG that is created for the sync
    - progress - the progress tracker, interfaces with PubSub
    - router - the DAG router
    - cursor - the cursor for the sync
    - collection - the collection that the sync is for
    - source connection - the source connection that the sync is for
    - guard rail - the guard rail service
    - white label (optional)
    - logger - contextual logger with sync job metadata
    - batch_size - max number of parents to process per micro-batch (default 64)
    - max_batch_latency_ms - max time to wait before flushing a non-full batch (default 200ms)
    """

    source: BaseSource
    destinations: list[BaseDestination]
    embedding_model: BaseEmbeddingModel
    keyword_indexing_model: BaseEmbeddingModel
    transformers: dict[str, callable]
    sync: schemas.Sync
    sync_job: schemas.SyncJob
    dag: schemas.SyncDag
    progress: SyncProgress
    router: SyncDAGRouter
    cursor: SyncCursor
    collection: schemas.Collection
    source_connection: schemas.Connection
    entity_map: dict[type[BaseEntity], UUID]
    ctx: ApiContext
    guard_rail: GuardRailService
    logger: ContextualLogger

    white_label: Optional[schemas.WhiteLabel] = None
    force_full_sync: bool = False

    # New: batching knobs (read by SyncOrchestrator at init)
    batch_size: int = 64
    max_batch_latency_ms: int = 200

    def __init__(
        self,
        source: BaseSource,
        destinations: list[BaseDestination],
        embedding_model: BaseEmbeddingModel,
        keyword_indexing_model: BaseEmbeddingModel,
        transformers: dict[str, callable],
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        dag: schemas.SyncDag,
        progress: SyncProgress,
        router: SyncDAGRouter,
        cursor: SyncCursor,
        collection: schemas.Collection,
        source_connection: schemas.Connection,
        entity_map: dict[type[BaseEntity], UUID],
        ctx: ApiContext,
        guard_rail: GuardRailService,
        logger: ContextualLogger,
        white_label: Optional[schemas.WhiteLabel] = None,
        force_full_sync: bool = False,
        # New optional args for micro-batching
        batch_size: int = 64,
        max_batch_latency_ms: int = 500,
    ):
        """Initialize the sync context."""
        self.source = source
        self.destinations = destinations
        self.embedding_model = embedding_model
        self.keyword_indexing_model = keyword_indexing_model
        self.transformers = transformers
        self.sync = sync
        self.sync_job = sync_job
        self.dag = dag
        self.progress = progress
        self.router = router
        self.cursor = cursor
        self.collection = collection
        self.source_connection = source_connection
        self.entity_map = entity_map
        self.ctx = ctx
        self.guard_rail = guard_rail
        self.white_label = white_label
        self.logger = logger
        self.force_full_sync = force_full_sync

        # New: micro-batching knobs
        self.batch_size = batch_size
        self.max_batch_latency_ms = max_batch_latency_ms
