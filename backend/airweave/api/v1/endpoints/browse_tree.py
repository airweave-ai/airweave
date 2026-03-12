"""Browse tree API endpoints for lazy-loaded source browsing and node selection."""

from typing import List, Optional
from uuid import UUID

from fastapi import Depends, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api import deps
from airweave.api.context import ApiContext
from airweave.api.deps import Inject
from airweave.api.router import TrailingSlashRouter
from airweave.db.session import get_db
from airweave.domains.browse_tree.protocols import (
    BrowseTreeServiceProtocol,
    NodeSelectionRepositoryProtocol,
)
from airweave.domains.browse_tree.types import (
    BrowseTreeResponse,
    NodeSelectionData,
    NodeSelectionRequest,
    NodeSelectionResponse,
)

router = TrailingSlashRouter()


@router.get(
    "/{source_connection_id}/browse-tree/selections",
    response_model=List[NodeSelectionData],
)
async def get_selections(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(..., description="Source connection ID"),
    ctx: ApiContext = Depends(deps.get_context),
    selection_repo: NodeSelectionRepositoryProtocol = Inject(NodeSelectionRepositoryProtocol),
) -> List[NodeSelectionData]:
    """Get existing node selections for a source connection."""
    rows = await selection_repo.get_by_source_connection(
        db, source_connection_id, ctx.organization.id
    )
    return [
        NodeSelectionData(
            source_node_id=r.source_node_id,
            node_type=r.node_type,
            node_title=r.node_title,
            node_metadata=r.node_metadata,
        )
        for r in rows
    ]


@router.get(
    "/{source_connection_id}/browse-tree",
    response_model=BrowseTreeResponse,
)
async def get_browse_tree(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(..., description="Source connection ID"),
    parent_node_id: Optional[str] = Query(None, description="Parent node ID for lazy loading"),
    ctx: ApiContext = Depends(deps.get_context),
    browse_tree_service: BrowseTreeServiceProtocol = Inject(BrowseTreeServiceProtocol),
) -> BrowseTreeResponse:
    """Get the browse tree for a source connection (lazy-loaded from source API)."""
    return await browse_tree_service.get_tree(
        db=db,
        source_connection_id=source_connection_id,
        ctx=ctx,
        parent_node_id=parent_node_id,
    )


@router.post(
    "/{source_connection_id}/browse-tree/select",
    response_model=NodeSelectionResponse,
)
async def select_nodes(
    *,
    db: AsyncSession = Depends(get_db),
    source_connection_id: UUID = Path(..., description="Source connection ID"),
    body: NodeSelectionRequest,
    ctx: ApiContext = Depends(deps.get_context),
    browse_tree_service: BrowseTreeServiceProtocol = Inject(BrowseTreeServiceProtocol),
) -> NodeSelectionResponse:
    """Submit node selections and trigger targeted sync.

    Stores NodeSelection rows on the source connection and auto-triggers
    a targeted content sync.
    """
    return await browse_tree_service.select_nodes(
        db=db,
        source_connection_id=source_connection_id,
        source_node_ids=body.source_node_ids,
        ctx=ctx,
    )
