from airweave.core.protocols.registry import BaseRegistryEntry


class EntityDefinitionEntry(BaseRegistryEntry):
    """Precomputed entity definition metadata."""

    entity_class_ref: type
    module_name: str  # source short_name this entity belongs to (e.g. "asana")
