"""Protocols for browse tree domain."""

from __future__ import annotations

from typing import List, Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.domains.browse_tree.types import (
    BrowseTreeResponse,
    NodeSelectionCreate,
    NodeSelectionResponse,
)
from airweave.models.node_selection import NodeSelection


class NodeSelectionRepositoryProtocol(Protocol):
    """Data access for NodeSelection records."""

    async def get_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> List[NodeSelection]:
        """Get all node selections for a source connection."""
        ...

    async def replace_all(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
        selections: List[NodeSelectionCreate],
    ) -> List[NodeSelection]:
        """Atomically replace all node selections for a source connection."""
        ...


class BrowseTreeServiceProtocol(Protocol):
    """Business logic for browse tree operations."""

    async def get_tree(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
        parent_node_id: Optional[str] = None,
    ) -> BrowseTreeResponse:
        """Get the browse tree (lazy-loaded from source API)."""
        ...

    async def select_nodes(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        source_node_ids: List[str],
        ctx: ApiContext,
    ) -> NodeSelectionResponse:
        """Submit node selections, store on SC, and trigger targeted sync."""
        ...
