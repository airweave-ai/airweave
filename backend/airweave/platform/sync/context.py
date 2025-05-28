"""Module for sync context."""

from typing import Optional
from uuid import UUID

from airweave import schemas
from airweave.core.logging import _ContextualLogger
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.embedding_models._base import BaseEmbeddingModel
from airweave.platform.entities._base import BaseEntity
from airweave.platform.sources._base import BaseSource
from airweave.platform.sync.pubsub import SyncProgress
from airweave.platform.sync.router import SyncDAGRouter


class SyncContext:
    """Context container for a sync.

    Contains all the necessary components for a sync:
    - source - the source instance
    - destinations - the destination instances
    - embedding model - the embedding model used for the sync
    - transformers - a dictionary of transformer callables
    - sync - the main sync object
    - sync job - the sync job that is created for the sync
    - dag - the DAG that is created for the sync
    - progress - the progress tracker, interfaces with PubSub
    - router - the DAG router
    - collection - the collection that the sync is for
    - source connection - the source connection that the sync is for
    - white label (optional)
    - logger - contextual logger with sync job metadata
    """

    source: BaseSource
    destinations: list[BaseDestination]
    embedding_model: BaseEmbeddingModel
    transformers: dict[str, callable]
    sync: schemas.Sync
    sync_job: schemas.SyncJob
    dag: schemas.SyncDag
    progress: SyncProgress
    router: SyncDAGRouter
    collection: schemas.Collection
    source_connection: schemas.Connection
    entity_map: dict[type[BaseEntity], UUID]
    current_user: schemas.User
    logger: _ContextualLogger

    white_label: Optional[schemas.WhiteLabel] = None

    def __init__(
        self,
        source: BaseSource,
        destinations: list[BaseDestination],
        embedding_model: BaseEmbeddingModel,
        transformers: dict[str, callable],
        sync: schemas.Sync,
        sync_job: schemas.SyncJob,
        dag: schemas.SyncDag,
        progress: SyncProgress,
        router: SyncDAGRouter,
        collection: schemas.Collection,
        source_connection: schemas.Connection,
        entity_map: dict[type[BaseEntity], UUID],
        current_user: schemas.User,
        logger: _ContextualLogger,
        white_label: Optional[schemas.WhiteLabel] = None,
    ):
        """Initialize the sync context."""
        self.source = source
        self.destinations = destinations
        self.embedding_model = embedding_model
        self.transformers = transformers
        self.sync = sync
        self.sync_job = sync_job
        self.dag = dag
        self.progress = progress
        self.router = router
        self.collection = collection
        self.source_connection = source_connection
        self.entity_map = entity_map
        self.current_user = current_user
        self.white_label = white_label
        self.logger = logger
