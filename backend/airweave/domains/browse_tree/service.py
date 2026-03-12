"""Browse tree service — business logic for lazy-loaded browse tree and node selection."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.browse_tree.protocols import (
    BrowseTreeServiceProtocol,
    NodeSelectionRepositoryProtocol,
)
from airweave.domains.browse_tree.types import (
    BrowseNode,
    BrowseTreeResponse,
    NodeSelectionCreate,
    NodeSelectionResponse,
)
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.sources.protocols import SourceLifecycleServiceProtocol
from airweave.domains.syncs.protocols import SyncJobRepositoryProtocol, SyncRepositoryProtocol
from airweave.domains.temporal.protocols import TemporalWorkflowServiceProtocol
from airweave.platform.sync.config import SyncConfig
from airweave.schemas.sync_job import SyncJobCreate, SyncJobStatus


class BrowseTreeService(BrowseTreeServiceProtocol):
    """Domain service for browse tree operations.

    Uses SourceLifecycleService to instantiate a source and call get_browse_children()
    for lazy-loaded tree browsing from the source API.
    """

    def __init__(  # noqa: D107
        self,
        selection_repo: NodeSelectionRepositoryProtocol,
        sc_repo: SourceConnectionRepositoryProtocol,
        source_lifecycle: SourceLifecycleServiceProtocol,
        sync_repo: SyncRepositoryProtocol,
        sync_job_repo: SyncJobRepositoryProtocol,
        collection_repo: CollectionRepositoryProtocol,
        conn_repo: ConnectionRepositoryProtocol,
        temporal_workflow_service: Optional[TemporalWorkflowServiceProtocol] = None,
    ) -> None:
        self._selection_repo = selection_repo
        self._sc_repo = sc_repo
        self._source_lifecycle = source_lifecycle
        self._sync_repo = sync_repo
        self._sync_job_repo = sync_job_repo
        self._collection_repo = collection_repo
        self._conn_repo = conn_repo
        self._temporal_service = temporal_workflow_service

    async def _dispatch_sync(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        config: SyncConfig,
        sync_type: str,
        ctx: ApiContext,
    ) -> UUID:
        """Load SC context, create a SyncJob with the given config, and dispatch to Temporal."""
        sc = await self._sc_repo.get(db, source_connection_id, ctx)
        if not sc:
            raise NotFoundException(f"Source connection {source_connection_id} not found")

        if not sc.sync_id:
            raise NotFoundException(f"Source connection {source_connection_id} has no sync")

        # Eagerly capture values before UnitOfWork expires the ORM object
        sc_sync_id = sc.sync_id
        sc_readable_collection_id = sc.readable_collection_id
        sc_connection_id = sc.connection_id

        sync_schema = await self._sync_repo.get(db, sc_sync_id, ctx)
        if not sync_schema:
            raise NotFoundException(f"Sync {sc_sync_id} not found")

        collection_obj = await self._collection_repo.get_by_readable_id(
            db,
            readable_id=sc_readable_collection_id,  # type: ignore[arg-type]
            ctx=ctx,
        )
        if not collection_obj:
            raise NotFoundException(f"Collection {sc_readable_collection_id} not found")

        collection_schema = schemas.CollectionRecord.model_validate(
            collection_obj, from_attributes=True
        )

        connection_obj = await self._conn_repo.get(db, sc_connection_id, ctx)  # type: ignore[arg-type]
        if not connection_obj:
            raise NotFoundException("Connection not found for source connection")

        connection_schema = schemas.Connection.model_validate(connection_obj, from_attributes=True)

        sync_job_create = SyncJobCreate(
            sync_id=sc_sync_id,
            status=SyncJobStatus.PENDING,
            sync_config=config,
            sync_metadata={"type": sync_type},
        )

        async with UnitOfWork(db) as uow:
            sync_job_obj = await self._sync_job_repo.create(
                db,
                obj_in=sync_job_create,
                ctx=ctx,
                uow=uow,
            )
            await uow.commit()
            await uow.session.refresh(sync_job_obj)

        sync_job_schema = schemas.SyncJob.model_validate(sync_job_obj, from_attributes=True)

        ctx.logger.info(
            f"Dispatching {sync_type} sync job {sync_job_schema.id} for SC {source_connection_id}"
        )
        if self._temporal_service is None:
            raise RuntimeError("Cannot dispatch sync: temporal workflow service is not configured")
        await self._temporal_service.run_source_connection_workflow(
            sync=sync_schema,
            sync_job=sync_job_schema,
            collection=collection_schema,
            connection=connection_schema,
            ctx=ctx,
        )

        return sync_job_schema.id

    async def get_tree(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
        parent_node_id: Optional[str] = None,
    ) -> BrowseTreeResponse:
        """Instantiate source, call get_browse_children(), return response."""
        try:
            source = await self._source_lifecycle.create(db, source_connection_id, ctx)
        except NotFoundException:
            raise
        except Exception as exc:
            ctx.logger.error(
                f"Failed to initialize source for browse tree (SC {source_connection_id}): {exc}"
            )
            raise

        if not getattr(source, "supports_browse_tree", False):
            raise NotFoundException(
                f"Source {source.__class__.__name__} does not support browse tree"
            )

        nodes: List[BrowseNode] = await source.get_browse_children(parent_node_id)

        return BrowseTreeResponse(
            nodes=nodes,
            parent_node_id=parent_node_id,
            total=len(nodes),
        )

    async def select_nodes(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        source_node_ids: List[str],
        ctx: ApiContext,
    ) -> NodeSelectionResponse:
        """Store selections on SC, trigger targeted sync.

        1. Instantiate source to resolve full node metadata from source_node_ids
        2. Atomically replace existing selections with new ones (single transaction)
        3. Dispatch targeted sync on same SC
        """
        sc = await self._sc_repo.get(db, source_connection_id, ctx)
        if not sc:
            raise NotFoundException(f"Source connection {source_connection_id} not found")

        # Instantiate source to resolve full metadata from node IDs.
        # The source owns the node ID encoding, so it can extract all metadata fields
        # (including base_template, item_count, etc.) that were embedded during browsing.
        source = await self._source_lifecycle.create(db, source_connection_id, ctx)

        if not getattr(source, "supports_browse_tree", False):
            raise NotFoundException(
                f"Source {source.__class__.__name__} does not support browse tree"
            )

        # Let the source parse node IDs into selections with full metadata
        selections: List[NodeSelectionCreate] = []
        for node_id in source_node_ids:
            node_type, node_metadata = source.parse_browse_node_id(node_id)
            selections.append(
                NodeSelectionCreate(
                    source_node_id=node_id,
                    node_type=node_type,
                    node_title=None,
                    node_metadata=node_metadata,
                )
            )

        # Atomically replace selections in a single transaction
        async with UnitOfWork(db) as uow:
            created = await self._selection_repo.replace_all(
                db=db,
                source_connection_id=source_connection_id,
                organization_id=ctx.organization.id,
                selections=selections,
            )
            await uow.commit()

        sync_job_id = await self._dispatch_sync(
            db,
            source_connection_id,
            SyncConfig(),
            "sync",
            ctx,
        )

        return NodeSelectionResponse(
            source_connection_id=source_connection_id,
            selections_count=len(created),
            sync_job_id=sync_job_id,
        )
