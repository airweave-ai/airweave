"""Browse tree repository — data access for DataTreeNode and NodeSelection."""

import uuid
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.models.data_tree_node import DataTreeNode
from airweave.models.node_selection import NodeSelection

from .protocols import BrowseTreeRepositoryProtocol, NodeSelectionRepositoryProtocol
from .types import NodeSelectionCreate


class BrowseTreeRepository(BrowseTreeRepositoryProtocol):
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
        """Get child nodes, optionally filtered by user access principals.

        Uses PostgreSQL ?| operator for JSONB array overlap when filtering by principals.
        """
        stmt = select(DataTreeNode).where(
            DataTreeNode.source_connection_id == source_connection_id,
            DataTreeNode.organization_id == organization_id,
        )

        if parent_id is None:
            stmt = stmt.where(DataTreeNode.parent_id.is_(None))
        else:
            stmt = stmt.where(DataTreeNode.parent_id == parent_id)

        # Access filtering: show nodes where user has access OR node is public
        if user_principals:
            principals_array = "{" + ",".join(f'"{p}"' for p in user_principals) + "}"
            access_filter = DataTreeNode.access_viewers.op("?|")(
                text(f"'{principals_array}'::text[]")
            )
            if include_public:
                stmt = stmt.where((access_filter) | (DataTreeNode.is_public.is_(True)))
            else:
                stmt = stmt.where(access_filter)

        stmt = stmt.order_by(DataTreeNode.node_type, DataTreeNode.title)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_node_by_source_node_id(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        source_node_id: str,
    ) -> Optional[DataTreeNode]:
        """Get a single node by source_node_id."""
        stmt = select(DataTreeNode).where(
            DataTreeNode.source_connection_id == source_connection_id,
            DataTreeNode.source_node_id == source_node_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_nodes_by_source_node_ids(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        source_node_ids: List[str],
    ) -> List[DataTreeNode]:
        """Get multiple nodes by their source_node_ids."""
        stmt = select(DataTreeNode).where(
            DataTreeNode.source_connection_id == source_connection_id,
            DataTreeNode.source_node_id.in_(source_node_ids),
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
    ) -> int:
        """Delete all nodes for a source connection."""
        stmt = delete(DataTreeNode).where(DataTreeNode.source_connection_id == source_connection_id)
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount or 0  # type: ignore[attr-defined]

    async def has_children(
        self,
        db: AsyncSession,
        node_id: UUID,
    ) -> bool:
        """Check if a node has children."""
        stmt = (
            select(func.count()).select_from(DataTreeNode).where(DataTreeNode.parent_id == node_id)
        )
        result = await db.execute(stmt)
        return result.scalar_one() > 0

    async def get_children_existence_map(
        self,
        db: AsyncSession,
        node_ids: List[UUID],
    ) -> Dict[UUID, bool]:
        """Get a map of node_id -> has_children for multiple nodes at once."""
        if not node_ids:
            return {}

        stmt = (
            select(DataTreeNode.parent_id, func.count())
            .where(DataTreeNode.parent_id.in_(node_ids))
            .group_by(DataTreeNode.parent_id)
        )
        result = await db.execute(stmt)
        has_children_set = {row[0] for row in result.all()}
        return {nid: nid in has_children_set for nid in node_ids}


class NodeSelectionRepository(NodeSelectionRepositoryProtocol):
    """Data access for NodeSelection records."""

    async def get_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
    ) -> List[NodeSelection]:
        """Get all node selections for a source connection."""
        stmt = select(NodeSelection).where(
            NodeSelection.source_connection_id == source_connection_id,
            NodeSelection.organization_id == organization_id,
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def bulk_create(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
        selections: List[NodeSelectionCreate],
    ) -> List[NodeSelection]:
        """Create multiple node selections (upsert on conflict)."""
        if not selections:
            return []

        rows = [
            {
                "id": uuid.uuid4(),
                "organization_id": organization_id,
                "source_connection_id": source_connection_id,
                "source_node_id": s.source_node_id,
                "node_type": s.node_type,
                "node_title": s.node_title,
                "node_metadata": s.node_metadata,
            }
            for s in selections
        ]

        stmt = pg_insert(NodeSelection).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["source_connection_id", "source_node_id"],
            set_={
                "node_type": stmt.excluded.node_type,
                "node_title": stmt.excluded.node_title,
                "node_metadata": stmt.excluded.node_metadata,
            },
        )
        await db.execute(stmt)
        await db.commit()

        # Return the created/updated rows
        return await self.get_by_source_connection(db, source_connection_id, organization_id)

    async def delete_by_source_connection(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
    ) -> int:
        """Delete all node selections for a source connection."""
        stmt = delete(NodeSelection).where(
            NodeSelection.source_connection_id == source_connection_id
        )
        result = await db.execute(stmt)
        await db.commit()
        return result.rowcount or 0  # type: ignore[attr-defined]
