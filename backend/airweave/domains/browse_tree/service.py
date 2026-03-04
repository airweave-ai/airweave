"""Browse tree service — business logic for metadata tree browsing and node selection."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import schemas
from airweave.api.context import ApiContext
from airweave.core.exceptions import NotFoundException
from airweave.core.temporal_service import temporal_service
from airweave.db.unit_of_work import UnitOfWork
from airweave.domains.browse_tree.protocols import (
    BrowseTreeRepositoryProtocol,
    BrowseTreeServiceProtocol,
    NodeSelectionRepositoryProtocol,
)
from airweave.domains.browse_tree.types import (
    AclSyncResponse,
    BrowseTreeResponse,
    DataTreeNodeResponse,
    MetadataSyncResponse,
    NodeSelectionCreate,
    NodeSelectionResponse,
)
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.connections.protocols import ConnectionRepositoryProtocol
from airweave.domains.source_connections.protocols import SourceConnectionRepositoryProtocol
from airweave.domains.syncs.protocols import SyncJobRepositoryProtocol, SyncRepositoryProtocol
from airweave.platform.access_control.broker import access_broker
from airweave.platform.sync.config import SyncConfig
from airweave.schemas.sync_job import SyncJobCreate, SyncJobStatus


class BrowseTreeService(BrowseTreeServiceProtocol):
    """Domain service for browse tree operations."""

    def __init__(  # noqa: D107
        self,
        tree_repo: BrowseTreeRepositoryProtocol,
        selection_repo: NodeSelectionRepositoryProtocol,
        sc_repo: SourceConnectionRepositoryProtocol,
        sync_repo: SyncRepositoryProtocol,
        sync_job_repo: SyncJobRepositoryProtocol,
        collection_repo: CollectionRepositoryProtocol,
        conn_repo: ConnectionRepositoryProtocol,
    ) -> None:
        self._tree_repo = tree_repo
        self._selection_repo = selection_repo
        self._sc_repo = sc_repo
        self._sync_repo = sync_repo
        self._sync_job_repo = sync_job_repo
        self._collection_repo = collection_repo
        self._conn_repo = conn_repo

    async def trigger_metadata_sync(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
    ) -> MetadataSyncResponse:
        """Trigger a metadata-only sync on a source connection.

        Creates a sync job with SyncConfig.metadata_tree() and dispatches
        to Temporal for execution. The sync will yield entities with metadata
        + ACLs but skip file downloads and all expensive processing.
        """
        sync_job_id = await self._dispatch_sync(
            db,
            source_connection_id,
            SyncConfig.metadata_tree(),
            "metadata_tree",
            ctx,
        )
        return MetadataSyncResponse(sync_job_id=sync_job_id)

    async def trigger_acl_sync(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
    ) -> AclSyncResponse:
        """Trigger an ACL-only sync on a source connection.

        Creates a sync job with SyncConfig.acl_only() and dispatches to Temporal.
        Skips entity processing entirely, only runs the access control pipeline
        to populate access_control_membership rows.
        """
        sync_job_id = await self._dispatch_sync(
            db,
            source_connection_id,
            SyncConfig.acl_only(),
            "acl_only",
            ctx,
        )
        return AclSyncResponse(sync_job_id=sync_job_id)

    async def _dispatch_sync(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        config: SyncConfig,
        sync_type: str,
        ctx: ApiContext,
    ) -> UUID:
        """Load SC context, create a SyncJob with the given config, and dispatch to Temporal.

        Returns the sync_job_id.
        """
        sc = await self._sc_repo.get(db, source_connection_id, ctx)
        if not sc:
            raise NotFoundException(f"Source connection {source_connection_id} not found")

        if not sc.sync_id:
            raise NotFoundException(f"Source connection {source_connection_id} has no sync")

        sync_schema = await self._sync_repo.get(db, sc.sync_id, ctx)
        if not sync_schema:
            raise NotFoundException(f"Sync {sc.sync_id} not found")

        sync_job_create = SyncJobCreate(
            sync_id=sc.sync_id,
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

        collection_obj = await self._collection_repo.get_by_readable_id(
            db,
            readable_id=sc.readable_collection_id,  # type: ignore[arg-type]
            ctx=ctx,
        )
        if not collection_obj:
            raise NotFoundException(f"Collection {sc.readable_collection_id} not found")

        collection_schema = schemas.CollectionRecord.model_validate(
            collection_obj, from_attributes=True
        )

        connection_obj = await self._conn_repo.get(db, sc.connection_id, ctx)  # type: ignore[arg-type]
        if not connection_obj:
            raise NotFoundException("Connection not found for source connection")

        connection_schema = schemas.Connection.model_validate(connection_obj, from_attributes=True)

        ctx.logger.info(
            f"Dispatching {sync_type} sync job {sync_job_schema.id} for SC {source_connection_id}"
        )
        await temporal_service.run_source_connection_workflow(
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
        parent_id: Optional[UUID] = None,
        user_principal: Optional[str] = None,
    ) -> BrowseTreeResponse:
        """Get the browse tree, optionally filtered by user access.

        If user_principal is provided, resolves their group memberships
        and filters nodes by access_viewers overlap.
        """
        # Resolve user principals for access filtering
        user_principals = None
        if user_principal:
            access_context = await access_broker.resolve_access_context(
                db=db,
                user_principal=user_principal,
                organization_id=ctx.organization.id,
            )
            # all_principals returns Set[str]; convert to List[str] for the repo query
            user_principals = list(access_context.all_principals)

        nodes = await self._tree_repo.get_children(
            db=db,
            source_connection_id=source_connection_id,
            organization_id=ctx.organization.id,
            parent_id=parent_id,
            user_principals=user_principals,
        )

        # Batch check which nodes have children
        node_ids: list[UUID] = [n.id for n in nodes]  # type: ignore[misc]
        children_map = await self._tree_repo.get_children_existence_map(db, node_ids)

        response_nodes = [
            DataTreeNodeResponse(
                id=n.id,  # type: ignore[arg-type]
                source_connection_id=n.source_connection_id,
                parent_id=n.parent_id,
                node_type=n.node_type,
                source_node_id=n.source_node_id,
                title=n.title,
                description=n.description,
                item_count=n.item_count,
                node_metadata=n.node_metadata,
                is_public=n.is_public,
                has_children=children_map.get(n.id, False),  # type: ignore[call-overload]
            )
            for n in nodes
        ]

        return BrowseTreeResponse(
            nodes=response_nodes,
            parent_id=parent_id,
            total=len(response_nodes),
        )

    async def select_nodes(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        admin_source_connection_id: UUID,
        source_node_ids: List[str],
        ctx: ApiContext,
    ) -> NodeSelectionResponse:
        """Submit node selections, store on user SC, and auto-trigger targeted sync.

        Looks up tree nodes on the admin SC (where DataTreeNode rows live),
        stores NodeSelection rows on the user's SC, then dispatches a targeted
        content sync on the user's SC.
        """
        # Verify user SC exists
        user_sc = await self._sc_repo.get(db, source_connection_id, ctx)
        if not user_sc:
            raise NotFoundException(f"Source connection {source_connection_id} not found")

        # Look up tree nodes using ADMIN SC ID (tree nodes are keyed to admin SC)
        tree_nodes = await self._tree_repo.get_nodes_by_source_node_ids(
            db=db,
            source_connection_id=admin_source_connection_id,
            source_node_ids=source_node_ids,
        )
        if not tree_nodes:
            raise NotFoundException("No matching tree nodes found for the given source_node_ids")

        selections = [
            NodeSelectionCreate(
                source_node_id=node.source_node_id,
                node_type=node.node_type,
                node_title=node.title,
                node_metadata=node.node_metadata,
            )
            for node in tree_nodes
        ]

        # Replace existing selections on user SC
        await self._selection_repo.delete_by_source_connection(db, source_connection_id)
        created = await self._selection_repo.bulk_create(
            db=db,
            source_connection_id=source_connection_id,
            organization_id=ctx.organization.id,
            selections=selections,
        )

        # Auto-trigger targeted content sync on user SC
        sync_job_id = await self._dispatch_sync(
            db,
            source_connection_id,
            SyncConfig.default(),
            "targeted_content",
            ctx,
        )

        return NodeSelectionResponse(
            source_connection_id=source_connection_id,
            selections_count=len(created),
            sync_job_id=sync_job_id,
        )
