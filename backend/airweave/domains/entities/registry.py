"""Entity definition registry — in-memory registry built once at startup."""

import re
from typing import Type

from airweave.core.logging import logger
from airweave.domains.entities.protocols import EntityDefinitionRegistryProtocol
from airweave.domains.entities.types import EntityDefinitionEntry
from airweave.platform.entities import ENTITIES_BY_SOURCE

registry_logger = logger.with_prefix("EntityDefinitionRegistry: ").with_context(
    component="entity_definition_registry"
)


def _to_snake_case(name: str) -> str:
    """Convert PascalCase class name to snake_case (e.g. AsanaTaskEntity -> asana_task_entity)."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "_", name).lower()


def _get_entity_schema_with_direct_fields_only(cls: Type) -> dict:
    """Get the JSON schema for an entity class including only direct fields and breadcrumbs.

    Filters the full Pydantic model_json_schema() to only include fields that
    are directly defined on this class (not inherited), plus always-include fields,
    minus system/internal fields.
    """
    full_schema = cls.model_json_schema()
    direct_annotations = getattr(cls, "__annotations__", {})

    always_include = {"breadcrumbs"}
    always_exclude = {
        "airweave_system_metadata",
        "textual_representation",
        "entity_id",
    }

    filtered_schema = {
        "type": "object",
        "title": full_schema.get("title", cls.__name__),
        "description": full_schema.get("description", ""),
        "properties": {},
        "required": [],
    }

    if "properties" in full_schema:
        for field_name, field_schema in full_schema["properties"].items():
            if field_name in always_exclude:
                continue
            if field_name in direct_annotations or field_name in always_include:
                filtered_schema["properties"][field_name] = field_schema
                if "required" in full_schema and field_name in full_schema["required"]:
                    filtered_schema["required"].append(field_name)

    if "$defs" in full_schema:
        filtered_schema["$defs"] = full_schema["$defs"]

    return filtered_schema


class EntityDefinitionRegistry(EntityDefinitionRegistryProtocol):
    """In-memory entity definition registry, built from ENTITIES_BY_SOURCE."""

    def __init__(self) -> None:
        """Initialize the entity definition registry."""
        self._entries: dict[str, EntityDefinitionEntry] = {}
        self._by_source: dict[str, list[EntityDefinitionEntry]] = {}

    def get(self, short_name: str) -> EntityDefinitionEntry:
        """Get an entity definition entry by short name.

        Args:
            short_name: The snake_case identifier (e.g., "asana_task_entity").

        Returns:
            The entity definition entry.

        Raises:
            KeyError: If no entity with the given short name is registered.
        """
        return self._entries[short_name]

    def list_all(self) -> list[EntityDefinitionEntry]:
        """List all registered entity definition entries."""
        return list(self._entries.values())

    def list_for_source(self, source_short_name: str) -> list[EntityDefinitionEntry]:
        """List all entity definitions for a given source.

        Args:
            source_short_name: The source short name (e.g., "asana").

        Returns:
            All entity definition entries for the source, or empty list if none.
        """
        return self._by_source.get(source_short_name, [])

    def build(self) -> None:
        """Build the registry from ENTITIES_BY_SOURCE.

        Iterates the explicit registration dict, creates entries, and builds
        the by-source index for fast lookups.

        Called once at startup. After this, all lookups are dict reads.
        """
        for module_name, entity_classes in ENTITIES_BY_SOURCE.items():
            source_entries = []

            for entity_cls in entity_classes:
                class_name = entity_cls.__name__
                short_name = _to_snake_case(class_name)

                entry = EntityDefinitionEntry(
                    short_name=short_name,
                    name=class_name,
                    description=entity_cls.__doc__,
                    class_name=class_name,
                    entity_class_ref=entity_cls,
                    module_name=module_name,
                    entity_type="json",
                    entity_schema=_get_entity_schema_with_direct_fields_only(entity_cls),
                )

                self._entries[short_name] = entry
                source_entries.append(entry)

            self._by_source[module_name] = source_entries

        registry_logger.info(
            f"Built registry with {len(self._entries)} entity definitions "
            f"across {len(self._by_source)} sources."
        )
