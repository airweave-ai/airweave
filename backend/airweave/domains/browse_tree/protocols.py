"""Protocols for browse tree domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.domains.browse_tree.types import (
    AclSyncResponse,
    BrowseTreeResponse,
    MetadataSyncResponse,
    NodeSelectionCreate,
    NodeSelectionResponse,
)

if TYPE_CHECKING:
    from airweave.models.data_tree_node import DataTreeNode
    from airweave.models.node_selection import NodeSelection


class BrowseTreeRepositoryProtocol(Protocol):
    """Data access for DataTreeNode records."""

    async def get_children(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
        parent_id: Optional[UUID] = None,
        user_principals: Optional[List[str]] = None,
        include_public: bool = True,
    ) -> List[DataTreeNode]:
        """Get child nodes, optionally filtered by user access principals."""
        ...

    async def get_node_by_source_node_id(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        source_node_id: str,
    ) -> Optional[DataTreeNode]:
        """Get a single node by source_node_id."""
        ...

    async def get_nodes_by_source_node_ids(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        source_node_ids: List[str],
    ) -> List[DataTreeNode]:
        """Get multiple nodes by their source_node_ids."""
        ...

    async def get_children_existence_map(
        self,
        db: AsyncSession,
        node_ids: List[UUID],
    ) -> Dict[UUID, bool]:
        """Get a map of node_id -> has_children for multiple nodes at once."""
        ...

    async def delete_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
    ) -> int:
        """Delete all nodes for a source connection (full replacement)."""
        ...


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

    async def bulk_create(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
        selections: List[NodeSelectionCreate],
    ) -> List[NodeSelection]:
        """Create multiple node selections."""
        ...

    async def delete_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
    ) -> int:
        """Delete all node selections for a source connection."""
        ...


class BrowseTreeServiceProtocol(Protocol):
    """Business logic for browse tree operations."""

    async def trigger_metadata_sync(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
    ) -> MetadataSyncResponse:
        """Trigger a metadata-only sync on an admin source connection."""
        ...

    async def trigger_acl_sync(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
    ) -> AclSyncResponse:
        """Trigger an ACL-only sync on an admin source connection."""
        ...

    async def get_tree(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        ctx: ApiContext,
        parent_id: Optional[UUID] = None,
        user_principal: Optional[str] = None,
    ) -> BrowseTreeResponse:
        """Get the browse tree, optionally filtered by user access."""
        ...

    async def select_nodes(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        admin_source_connection_id: UUID,
        source_node_ids: List[str],
        ctx: ApiContext,
    ) -> NodeSelectionResponse:
        """Submit node selections, store on user SC, and auto-trigger targeted sync."""
        ...
