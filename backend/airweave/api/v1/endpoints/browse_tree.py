"""Browse tree API endpoints for metadata tree browsing and node selection."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.db.session import get_db
from airweave.domains.browse_tree.protocols import BrowseTreeServiceProtocol
from airweave.domains.browse_tree.types import (
    AclSyncResponse,
    BrowseTreeResponse,
    MetadataSyncResponse,
    NodeSelectionRequest,
    NodeSelectionResponse,
)

# Admin router — mounted under /admin/source-connections
admin_router = TrailingSlashRouter()

# User router — mounted under /source-connections
router = TrailingSlashRouter()


# -------------------------------------------------------------------------
# Admin Endpoints
# -------------------------------------------------------------------------


@admin_router.post(
    "/{source_connection_id}/sync-metadata",
    response_model=MetadataSyncResponse,
)
async def trigger_metadata_sync(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(..., description="Admin's source connection ID"),
    ctx: ApiContext = Depends(deps.get_context),
    browse_tree_service: BrowseTreeServiceProtocol = Inject(BrowseTreeServiceProtocol),
) -> MetadataSyncResponse:
    """Trigger a metadata-only sync on a source connection.

    Creates a sync job that fetches entity metadata + ACLs without downloading
    file content. Results are stored as data_tree_node rows for browse tree display.
    """
    return await browse_tree_service.trigger_metadata_sync(
        db=db,
        source_connection_id=source_connection_id,
        ctx=ctx,
    )


@admin_router.post(
    "/{source_connection_id}/sync-acl",
    response_model=AclSyncResponse,
)
async def trigger_acl_sync(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(..., description="Admin's source connection ID"),
    ctx: ApiContext = Depends(deps.get_context),
    browse_tree_service: BrowseTreeServiceProtocol = Inject(BrowseTreeServiceProtocol),
) -> AclSyncResponse:
    """Trigger an ACL-only sync on a source connection.

    Syncs group memberships and access control data without processing entities.
    Results are stored as access_control_membership rows for browse tree filtering.
    """
    return await browse_tree_service.trigger_acl_sync(
        db=db,
        source_connection_id=source_connection_id,
        ctx=ctx,
    )


@admin_router.get(
    "/{source_connection_id}/browse-tree",
    response_model=BrowseTreeResponse,
)
async def get_admin_browse_tree(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(..., description="Admin's source connection ID"),
    parent_id: Optional[UUID] = Query(None, description="Parent node ID for lazy loading"),
    ctx: ApiContext = Depends(deps.get_context),
    browse_tree_service: BrowseTreeServiceProtocol = Inject(BrowseTreeServiceProtocol),
) -> BrowseTreeResponse:
    """Get the full browse tree for a source connection (admin, unfiltered)."""
    return await browse_tree_service.get_tree(
        db=db,
        source_connection_id=source_connection_id,
        ctx=ctx,
        parent_id=parent_id,
    )


# -------------------------------------------------------------------------
# User Endpoints
# -------------------------------------------------------------------------


@router.get(
    "/{source_connection_id}/browse-tree",
    response_model=BrowseTreeResponse,
)
async def get_user_browse_tree(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(..., description="Source connection ID"),
    parent_id: Optional[UUID] = Query(None, description="Parent node ID for lazy loading"),
    user_principal: Optional[str] = Query(
        None, description="User principal for access filtering (e.g., 'john@acme.com')"
    ),
    ctx: ApiContext = Depends(deps.get_context),
    browse_tree_service: BrowseTreeServiceProtocol = Inject(BrowseTreeServiceProtocol),
) -> BrowseTreeResponse:
    """Get the access-filtered browse tree for a source connection.

    If user_principal is provided, resolves their group memberships and filters
    nodes where access_viewers overlaps with the user's principals.
    """
    return await browse_tree_service.get_tree(
        db=db,
        source_connection_id=source_connection_id,
        ctx=ctx,
        parent_id=parent_id,
        user_principal=user_principal,
    )


@router.post(
    "/{source_connection_id}/browse-tree/select",
    response_model=NodeSelectionResponse,
)
async def select_nodes(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(..., description="User's source connection ID"),
    body: NodeSelectionRequest,
    ctx: ApiContext = Depends(deps.get_context),
    browse_tree_service: BrowseTreeServiceProtocol = Inject(BrowseTreeServiceProtocol),
) -> NodeSelectionResponse:
    """Submit node selections and trigger targeted sync.

    Looks up tree nodes on the admin's source connection, stores NodeSelection
    rows on the user's source connection, and auto-triggers a targeted content sync.
    """
    return await browse_tree_service.select_nodes(
        db=db,
        source_connection_id=source_connection_id,
        admin_source_connection_id=body.admin_source_connection_id,
        source_node_ids=body.source_node_ids,
        ctx=ctx,
    )
