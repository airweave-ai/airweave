from pydantic import BaseModel

from airweave.core.protocols.registry import BaseRegistryEntry


class EntityDefinitionEntry(BaseRegistryEntry):
    """Precomputed entity definition metadata."""

    entity_class_ref: type
    module_name: str  # source short_name this entity belongs to (e.g. "asana")
    entity_type: str  # "json" (always, for now)
    entity_schema: dict  # filtered Pydantic JSON schema (direct fields + breadcrumbs)


class EntityDefinitionMetadata(BaseModel):
    """API response model for entity definitions — excludes internal fields."""

    short_name: str
    name: str
    description: str | None
    class_name: str
    module_name: str
    entity_type: str
    entity_schema: dict
