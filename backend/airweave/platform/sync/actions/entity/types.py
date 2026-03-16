"""Entity-specific action types for entity sync pipeline.

Extends generic action types with entity-specific fields like
entity_definition_short_name, db_id, chunk_entities, and existing_map.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
from uuid import UUID

if TYPE_CHECKING:
    from airweave import models
    from airweave.platform.entities._base import BaseEntity


# =============================================================================
# Entity Action Types
# =============================================================================


@dataclass
class EntityInsertAction:
    """Entity should be inserted (new entity, not in database)."""

    entity: "BaseEntity"
    entity_definition_short_name: str
    chunk_entities: List["BaseEntity"] = field(default_factory=list)

    @property
    def entity_id(self) -> str:
        """Get the entity ID."""
        return self.entity.entity_id

    @property
    def entity_type(self) -> str:
        """Get the entity type name."""
        return self.entity.__class__.__name__


@dataclass
class EntityUpdateAction:
    """Entity should be updated (hash changed from stored value)."""

    entity: "BaseEntity"
    entity_definition_short_name: str
    db_id: UUID  # Existing database record ID
    chunk_entities: List["BaseEntity"] = field(default_factory=list)

    @property
    def entity_id(self) -> str:
        """Get the entity ID."""
        return self.entity.entity_id

    @property
    def entity_type(self) -> str:
        """Get the entity type name."""
        return self.entity.__class__.__name__


@dataclass
class EntityDeleteAction:
    """Entity should be deleted (DeletionEntity from source)."""

    entity: "BaseEntity"
    entity_definition_short_name: str
    db_id: Optional[UUID] = None  # May not exist in DB if never synced

    @property
    def entity_id(self) -> str:
        """Get the entity ID."""
        return self.entity.entity_id

    @property
    def entity_type(self) -> str:
        """Get the entity type name."""
        return self.entity.__class__.__name__


@dataclass
class EntityKeepAction:
    """Entity is unchanged (hash matches stored value)."""

    entity: "BaseEntity"
    entity_definition_short_name: str

    @property
    def entity_id(self) -> str:
        """Get the entity ID."""
        return self.entity.entity_id

    @property
    def entity_type(self) -> str:
        """Get the entity type name."""
        return self.entity.__class__.__name__


# =============================================================================
# Entity Action Batch
# =============================================================================


@dataclass
class EntityActionBatch:
    """Container for a batch of resolved entity actions."""

    inserts: List[EntityInsertAction] = field(default_factory=list)
    updates: List[EntityUpdateAction] = field(default_factory=list)
    deletes: List[EntityDeleteAction] = field(default_factory=list)
    keeps: List[EntityKeepAction] = field(default_factory=list)

    # Map of (entity_id, entity_definition_short_name) -> DB entity for lookups
    existing_map: Dict[Tuple[str, str], "models.Entity"] = field(default_factory=dict)

    @property
    def has_mutations(self) -> bool:
        """Check if batch has any mutation actions."""
        return bool(self.inserts or self.updates or self.deletes)

    @property
    def mutation_count(self) -> int:
        """Get total count of mutation actions."""
        return len(self.inserts) + len(self.updates) + len(self.deletes)

    @property
    def total_count(self) -> int:
        """Get total count of all actions including KEEP."""
        return self.mutation_count + len(self.keeps)

    def summary(self) -> str:
        """Get a summary string of the batch."""
        parts = []
        if self.inserts:
            parts.append(f"{len(self.inserts)} inserts")
        if self.updates:
            parts.append(f"{len(self.updates)} updates")
        if self.deletes:
            parts.append(f"{len(self.deletes)} deletes")
        if self.keeps:
            parts.append(f"{len(self.keeps)} keeps")
        return ", ".join(parts) if parts else "empty"

    def get_entities_to_process(self) -> List["BaseEntity"]:
        """Get entities that need content processing (INSERT + UPDATE)."""
        entities = []
        for insert_action in self.inserts:
            entities.append(insert_action.entity)
        for update_action in self.updates:
            entities.append(update_action.entity)
        return entities
