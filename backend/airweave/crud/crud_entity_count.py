"""CRUD operations for entity counts."""

from typing import List
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.crud._base_organization import CRUDBaseOrganization
from airweave.models.entity_count import EntityCount
from airweave.schemas.entity_count import (
    EntityCountCreate,
    EntityCountUpdate,
    EntityCountWithDefinition,
)


def _short_name_to_display_name(short_name: str) -> str:
    """Convert snake_case short_name to PascalCase display name."""
    return "".join(word.capitalize() for word in short_name.split("_"))


class CRUDEntityCount(CRUDBaseOrganization[EntityCount, EntityCountCreate, EntityCountUpdate]):
    """CRUD operations for entity counts."""

    async def get_counts_per_sync_and_type(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> List[EntityCountWithDefinition]:
        """Get entity counts for a sync with entity definition details.

        Reads directly from entity_count (no JOIN). Name/type are derived
        from short_name + registry when available.

        Args:
            db: Database session
            sync_id: ID of the sync

        Returns:
            List of EntityCountWithDefinition objects
        """
        stmt = (
            select(EntityCount)
            .where(EntityCount.sync_id == sync_id)
            .order_by(EntityCount.entity_definition_short_name)
        )

        result = await db.execute(stmt)
        rows = list(result.scalars().all())

        registry_meta = self._get_registry_metadata()

        return [
            EntityCountWithDefinition(
                count=row.count,
                entity_definition_short_name=row.entity_definition_short_name,
                entity_definition_name=registry_meta.get(row.entity_definition_short_name, {}).get(
                    "name", _short_name_to_display_name(row.entity_definition_short_name)
                ),
                entity_definition_type=registry_meta.get(row.entity_definition_short_name, {}).get(
                    "type", "json"
                ),
                entity_definition_description=registry_meta.get(
                    row.entity_definition_short_name, {}
                ).get("description"),
                modified_at=row.modified_at,
            )
            for row in rows
        ]

    @staticmethod
    def _get_registry_metadata() -> dict:
        """Return {short_name: {name, type, description}} from the entity definition registry."""
        # [code blue] todo: remove container import
        from airweave.core.container import container as app_container

        return {
            entry.short_name: {
                "name": entry.name,
                "type": "json",
                "description": entry.description,
            }
            for entry in app_container.entity_definition_registry.list_all()
        }

    async def get_by_sync_id(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> List[EntityCount]:
        """Get all entity counts for a specific sync."""
        stmt = select(EntityCount).where(EntityCount.sync_id == sync_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_total_count_by_sync(
        self,
        db: AsyncSession,
        sync_id: UUID,
    ) -> int:
        """Get total entity count across all types for a sync."""
        from sqlalchemy import func

        stmt = select(func.sum(EntityCount.count)).where(EntityCount.sync_id == sync_id)
        result = await db.execute(stmt)
        total = result.scalar_one_or_none()
        return total or 0


entity_count = CRUDEntityCount(EntityCount, track_user=False)
