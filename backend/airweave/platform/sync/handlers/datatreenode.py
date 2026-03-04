"""DataTreeNode handler for metadata tree persistence.

Converts entities from a metadata-only sync into data_tree_node rows in Postgres.
This handler is only active when SyncConfig.handlers.enable_datatreenode_handler is True
(i.e., during metadata_tree() preset syncs).
"""

import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.db.session import get_db_context
from airweave.domains.browse_tree.types import DataTreeNodeCreate
from airweave.models.data_tree_node import DataTreeNode
from airweave.platform.sync.actions.entity.types import (
    EntityActionBatch,
    EntityDeleteAction,
    EntityInsertAction,
    EntityUpdateAction,
)
from airweave.platform.sync.handlers.protocol import EntityActionHandler

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.contexts.runtime import SyncRuntime


# Mapping from entity class name suffix to node_type
_ENTITY_TYPE_MAP = {
    "SiteEntity": "site",
    "ListEntity": "list",
    "FolderEntity": "folder",
    "FileEntity": "file",
    "ItemEntity": "item",
}


def _derive_node_type(entity: Any) -> str:
    """Derive node_type from entity class name."""
    class_name = entity.__class__.__name__
    for suffix, node_type in _ENTITY_TYPE_MAP.items():
        if class_name.endswith(suffix):
            return node_type
    return "item"  # fallback


def _entity_to_node(
    entity: Any,
    source_connection_id: UUID,
    organization_id: UUID,
    node_id_map: Dict[str, UUID],
) -> DataTreeNodeCreate:
    """Convert a BaseEntity to a typed DataTreeNodeCreate for upsert."""
    node_type = _derive_node_type(entity)
    source_node_id = entity.entity_id

    # Derive parent from breadcrumbs (last breadcrumb is the immediate parent)
    parent_id = None
    breadcrumbs = getattr(entity, "breadcrumbs", None) or []
    if breadcrumbs:
        parent_source_id = breadcrumbs[-1].entity_id
        parent_id = node_id_map.get(parent_source_id)

    # Extract access control
    access = getattr(entity, "access", None)
    access_viewers: Optional[List[str]] = None
    is_public = False
    if access:
        access_viewers = access.viewers if access.viewers else None
        is_public = access.is_public

    # Extract title
    title = getattr(entity, "name", None) or getattr(entity, "title", None) or source_node_id

    # Extract description
    description = getattr(entity, "description", None)

    # Extract item_count
    item_count = getattr(entity, "item_count", None)

    # Build node_metadata from extra fields
    node_metadata: Dict[str, Any] = {}
    for attr in ("url", "file_name", "server_relative_url", "base_template", "site_url"):
        val = getattr(entity, attr, None)
        if val is not None:
            node_metadata[attr] = val

    # Generate deterministic UUID for this node
    node_id = node_id_map.get(source_node_id)
    if not node_id:
        node_id = uuid.uuid4()
        node_id_map[source_node_id] = node_id

    return DataTreeNodeCreate(
        id=node_id,
        organization_id=organization_id,
        source_connection_id=source_connection_id,
        parent_id=parent_id,
        node_type=node_type,
        source_node_id=source_node_id,
        title=str(title)[:512],
        description=str(description)[:2000] if description else None,
        item_count=item_count,
        node_metadata=node_metadata or None,
        access_viewers=access_viewers,
        is_public=is_public,
    )


class DataTreeNodeHandler(EntityActionHandler):
    """Converts entities to DataTreeNode rows in Postgres.

    Only active during metadata_tree() syncs. Receives entity actions
    and upserts them as data_tree_node rows.
    """

    @property
    def name(self) -> str:
        """Return handler name."""
        return "datatreenode"

    async def handle_batch(
        self,
        batch: EntityActionBatch,
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Handle a full action batch — upsert inserts + updates, delete deletes."""
        if not batch.has_mutations:
            return

        async with get_db_context() as db:
            if batch.inserts or batch.updates:
                entities = [a.entity for a in batch.inserts] + [a.entity for a in batch.updates]
                await self._bulk_upsert(entities, sync_context, db)
            if batch.deletes:
                await self._do_deletes(batch.deletes, sync_context, db)
            await db.commit()

        total = len(batch.inserts) + len(batch.updates)
        sync_context.logger.debug(f"[DataTreeNode] Upserted {total}, deleted {len(batch.deletes)}")

    async def handle_inserts(
        self,
        actions: List[EntityInsertAction],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Upsert inserted entities as data_tree_node rows."""
        if not actions:
            return
        async with get_db_context() as db:
            await self._bulk_upsert([a.entity for a in actions], sync_context, db)
            await db.commit()

    async def handle_updates(
        self,
        actions: List[EntityUpdateAction],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Upsert updated entities as data_tree_node rows."""
        if not actions:
            return
        async with get_db_context() as db:
            await self._bulk_upsert([a.entity for a in actions], sync_context, db)
            await db.commit()

    async def handle_deletes(
        self,
        actions: List[EntityDeleteAction],
        sync_context: "SyncContext",
    ) -> None:
        """Delete data_tree_node rows matching deleted entities."""
        if not actions:
            return
        async with get_db_context() as db:
            await self._do_deletes(actions, sync_context, db)
            await db.commit()

    async def handle_orphan_cleanup(
        self,
        orphan_entity_ids: List[str],
        sync_context: "SyncContext",
    ) -> None:
        """Delete orphaned data_tree_node rows by source_node_id."""
        if not orphan_entity_ids:
            return

        sync_context.logger.info(f"[DataTreeNode] Cleaning {len(orphan_entity_ids)} orphan nodes")

        source_connection_id = sync_context.source_connection_id
        async with get_db_context() as db:
            stmt = delete(DataTreeNode).where(
                DataTreeNode.source_connection_id == source_connection_id,
                DataTreeNode.source_node_id.in_(orphan_entity_ids),
            )
            await db.execute(stmt)
            await db.commit()

    # -------------------------------------------------------------------------
    # Private
    # -------------------------------------------------------------------------

    async def _bulk_upsert(
        self,
        entities: List[Any],
        sync_context: "SyncContext",
        db: AsyncSession,
    ) -> None:
        """Bulk upsert entities as data_tree_node rows."""
        if not entities:
            return

        source_connection_id = sync_context.source_connection_id
        organization_id = sync_context.organization_id

        # Pre-load existing nodes so parent resolution works across batches.
        # We query all source_node_ids that appear as parent references in this batch.
        parent_source_ids: set[str] = set()
        for entity in entities:
            breadcrumbs = getattr(entity, "breadcrumbs", None) or []
            if breadcrumbs:
                parent_source_ids.add(breadcrumbs[-1].entity_id)

        node_id_map: Dict[str, UUID] = {}
        if parent_source_ids:
            stmt = select(DataTreeNode.source_node_id, DataTreeNode.id).where(
                DataTreeNode.source_connection_id == source_connection_id,
                DataTreeNode.source_node_id.in_(list(parent_source_ids)),
            )
            result = await db.execute(stmt)
            for row in result.all():
                node_id_map[row[0]] = row[1]

        nodes: List[DataTreeNodeCreate] = []
        for entity in entities:
            try:
                node = _entity_to_node(entity, source_connection_id, organization_id, node_id_map)
                nodes.append(node)
            except Exception as e:
                sync_context.logger.warning(
                    f"[DataTreeNode] Skipping entity {getattr(entity, 'entity_id', '?')}: {e}"
                )

        if not nodes:
            return

        # Use PostgreSQL ON CONFLICT upsert
        upsert_stmt = pg_insert(DataTreeNode).values([n.model_dump() for n in nodes])
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=["source_connection_id", "source_node_id"],
            set_={
                "title": upsert_stmt.excluded.title,
                "description": upsert_stmt.excluded.description,
                "node_type": upsert_stmt.excluded.node_type,
                "parent_id": upsert_stmt.excluded.parent_id,
                "item_count": upsert_stmt.excluded.item_count,
                "node_metadata": upsert_stmt.excluded.node_metadata,
                "access_viewers": upsert_stmt.excluded.access_viewers,
                "is_public": upsert_stmt.excluded.is_public,
                "modified_at": text("now()"),
            },
        )
        await db.execute(upsert_stmt)

    async def _do_deletes(
        self,
        actions: List[EntityDeleteAction],
        sync_context: "SyncContext",
        db: AsyncSession,
    ) -> None:
        """Delete data_tree_node rows matching the deleted entities."""
        entity_ids = [a.entity_id for a in actions]
        if not entity_ids:
            return

        stmt = delete(DataTreeNode).where(
            DataTreeNode.source_connection_id == sync_context.source_connection_id,
            DataTreeNode.source_node_id.in_(entity_ids),
        )
        await db.execute(stmt)
