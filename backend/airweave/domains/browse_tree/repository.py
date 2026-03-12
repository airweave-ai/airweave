"""Browse tree repository — data access for NodeSelection."""

import uuid
from typing import List
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.models.node_selection import NodeSelection

from .protocols import NodeSelectionRepositoryProtocol
from .types import NodeSelectionCreate


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

    async def replace_all(
        self,
        db: AsyncSession,
        source_connection_id: UUID,
        organization_id: UUID,
        selections: List[NodeSelectionCreate],
    ) -> List[NodeSelection]:
        """Atomically replace all node selections for a source connection.

        Deletes existing selections and inserts new ones in a single transaction.
        The caller must handle commit/rollback (e.g., via UnitOfWork).
        """
        # Delete existing (scoped to organization to prevent cross-org deletion)
        del_stmt = delete(NodeSelection).where(
            NodeSelection.source_connection_id == source_connection_id,
            NodeSelection.organization_id == organization_id,
        )
        await db.execute(del_stmt)

        if not selections:
            return []

        # Insert new
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

        # Return the created rows
        return await self.get_by_source_connection(db, source_connection_id, organization_id)
