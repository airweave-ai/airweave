"""Module for syncing embedding models, sources, destinations, and auth providers."""

import importlib
import inspect
import os
import re
from pathlib import Path
from typing import Callable, Dict, Type

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud, schemas
from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.models.entity_definition import EntityType
from airweave.platform.auth_providers._base import BaseAuthProvider
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.sources._base import BaseSource

# Compute platform directory from this file's location (works regardless of cwd)
PLATFORM_DIR = Path(__file__).parent

sync_logger = logger.with_prefix("Platform sync: ").with_context(component="platform_sync")


def _extract_template_variables(template_string: str) -> set[str]:
    """Extract variable names from a template string like 'https://{instance_url}/path'.

    Args:
        template_string: String containing {variable} placeholders

    Returns:
        Set of variable names found in the template

    Example:
        >>> _extract_template_variables("https://{instance_url}/oauth/{version}")
        {'instance_url', 'version'}
    """
    # Find all {variable} patterns
    pattern = r"\{(\w+)\}"
    matches = re.findall(pattern, template_string)
    return set(matches)


def _validate_source_template_config(source_class: Type[BaseSource]) -> None:
    """Validate that source's YAML template variables match config class RequiredTemplateConfigs.

    Args:
        source_class: Source class to validate

    Raises:
        ValueError: If template variables don't match auth-required config fields
    """
    short_name = source_class.short_name
    config_class_name = source_class.config_class

    # Skip if no config class
    if not config_class_name:
        return

    # Load integration settings to check for templates
    try:
        from airweave.platform.auth.settings import integration_settings

        oauth_settings = integration_settings.get_settings(short_name)

        # Skip if no OAuth settings or no templates
        if not oauth_settings:
            return

        if not getattr(oauth_settings, "url_template", False):
            return  # No templates, nothing to validate

        # Extract template variables from URLs
        url_vars = _extract_template_variables(oauth_settings.url)
        backend_url_vars = set()
        if getattr(oauth_settings, "backend_url_template", False):
            backend_url_vars = _extract_template_variables(oauth_settings.backend_url)

        # Combine all required template variables
        all_template_vars = url_vars | backend_url_vars

        if not all_template_vars:
            sync_logger.warning(
                f"Source '{short_name}' has url_template=true but no template variables found"
            )
            return

        # Load config class and get template config fields
        from airweave.platform.locator import resource_locator

        config_class = resource_locator.get_config(config_class_name)
        template_config_fields = set(config_class.get_template_config_fields())

        # Validate: every template variable must have a matching RequiredTemplateConfig
        missing_in_config = all_template_vars - template_config_fields
        if missing_in_config:
            raise ValueError(
                f"Source '{short_name}' template validation failed:\n"
                f"  YAML template variables: {sorted(all_template_vars)}\n"
                f"  Config template fields: {sorted(template_config_fields)}\n"
                f"  Missing in config class: {sorted(missing_in_config)}\n\n"
                f"Fix: Add to {config_class_name}:\n"
                + "\n".join(
                    [
                        f"    {var}: str = RequiredTemplateConfig("
                        f'title="{var.replace("_", " ").title()}")'
                        for var in sorted(missing_in_config)
                    ]
                )
            )

        # Warn if config has extra template fields not in YAML template
        extra_in_config = template_config_fields - all_template_vars
        if extra_in_config:
            sync_logger.warning(
                f"Source '{short_name}' has template config fields not used in YAML: "
                f"{sorted(extra_in_config)}. These may be for direct auth or API calls."
            )

        # Success!
        sync_logger.info(
            f"✅ Template validation passed for '{short_name}': "
            f"YAML variables {sorted(all_template_vars)} match config fields"
        )

    except ValueError:
        # Re-raise validation errors
        raise
    except Exception as e:
        # Log but don't fail sync for validation errors (backward compatibility)
        sync_logger.warning(
            f"Could not validate templates for '{short_name}': {e}. "
            f"This is non-fatal but templates may not work correctly."
        )


def _process_module_classes(module, components: Dict[str, list[Type | Callable]]) -> None:
    """Process classes in a module and add them to the components dictionary.

    Args:
        module: The module to process
        components: Dictionary to add components to
    """
    # Scan for classes
    for _, cls in inspect.getmembers(module, inspect.isclass):
        if getattr(cls, "is_source", False):
            components["sources"].append(cls)
        elif getattr(cls, "is_destination", False):
            components["destinations"].append(cls)
        elif getattr(cls, "is_auth_provider", False):
            components["auth_providers"].append(cls)


# NOTE: Transformers were removed - chunking now happens in entity_pipeline.py
# using CodeChunker and SemanticChunker, not decorator-based transformers


def _get_decorated_classes() -> Dict[str, list[Type | Callable]]:
    """Scan platform directory for decorated classes and functions.

    Returns:
        Dict[str, list[Type | Callable]]: Dictionary of decorated classes and functions by type.

    Raises:
        ImportError: If any module cannot be imported. This ensures the sync process fails if there
        are any issues.
    """
    components = {
        "sources": [],
        "destinations": [],
        "auth_providers": [],
    }

    base_package = "airweave.platform"

    for root, dirs, files in os.walk(PLATFORM_DIR):
        dirs[:] = [d for d in dirs if d != "tests"]
        # Skip files in the root directory
        if Path(root) == PLATFORM_DIR:
            continue

        for filename in files:
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            relative_path = os.path.relpath(root, PLATFORM_DIR)
            module_path = os.path.join(relative_path, filename[:-3]).replace("/", ".")
            full_module_name = f"{base_package}.{module_path}"

            try:
                module = importlib.import_module(full_module_name)
                _process_module_classes(module, components)
            except ImportError as e:
                # Convert the warning into a fatal error to prevent silent failures
                error_msg = (
                    f"Failed to import {full_module_name}: {e}\n"
                    f"This is likely due to missing dependencies required by this module.\n"
                    f"If this module contains transformers, sources, destinations, "
                    f"or auth providers, they will not be registered."
                )
                sync_logger.error(error_msg)
                # Re-raise the exception to fail the sync process
                raise ImportError(f"Module import failed: {full_module_name}") from e

    # Filter out internal sources when ENABLE_INTERNAL_SOURCES is False.
    # This uses the `internal=True` flag from the @source decorator as the single source of truth.
    if not settings.ENABLE_INTERNAL_SOURCES:
        internal_sources = [s for s in components["sources"] if s.is_internal()]
        if internal_sources:
            sync_logger.debug(
                f"Skipping {len(internal_sources)} internal source(s) "
                f"({', '.join(s.short_name for s in internal_sources)}) "
                "(set ENABLE_INTERNAL_SOURCES=true to enable)"
            )
        components["sources"] = [s for s in components["sources"] if not s.is_internal()]

    return components


def _validate_entity_class_fields(cls: Type, name: str, module_name: str) -> None:
    """Validate that all fields in an entity class use Pydantic Fields with descriptions.

    Args:
        cls: The entity class to validate
        name: The name of the entity class
        module_name: The name of the module containing the entity class

    Raises:
        ValueError: If any field is not defined using Pydantic Field with a description
    """
    # We need to check the actual class annotations, not inherited ones
    if hasattr(cls, "__annotations__"):
        direct_annotations = cls.__annotations__

        # Get all fields from the class and only validate those in direct_annotations
        for field_name, field_info in cls.model_fields.items():
            # Skip internal fields that start with underscores
            if field_name.startswith("_"):
                continue

            # Skip fields that are not directly defined in this class
            if field_name not in direct_annotations:
                continue

            # Check that the field is defined using Pydantic Field
            if not hasattr(field_info, "description") or not field_info.description:
                raise ValueError(
                    f"Entity '{name}' in module '{module_name}' has field '{field_name}' "
                    f"without a Pydantic Field description. All entity fields must use "
                    f"Field with a description parameter."
                )


def _get_entity_schema_with_direct_fields_only(cls: Type) -> dict:
    """Get the JSON schema for an entity class including only direct fields and breadcrumbs.

    Args:
        cls: The entity class

    Returns:
        dict: JSON schema with only direct fields and breadcrumbs
    """
    # Get the full schema
    full_schema = cls.model_json_schema()

    # Get direct annotations (fields defined directly in this class)
    direct_annotations = getattr(cls, "__annotations__", {})

    # Fields to always include
    always_include = {"breadcrumbs"}

    # Fields to always exclude (system metadata and internal fields)
    always_exclude = {
        "airweave_system_metadata",  # System tracking, not business data
        "textual_representation",  # Generated during pipeline, not source field
        "entity_id",  # Set by source connector, not business data
    }

    # Build the filtered schema
    filtered_schema = {
        "type": "object",
        "title": full_schema.get("title", cls.__name__),
        "description": full_schema.get("description", ""),
        "properties": {},
        "required": [],
    }

    # Add properties that are either direct fields or in always_include
    if "properties" in full_schema:
        for field_name, field_schema in full_schema["properties"].items():
            # Skip excluded fields
            if field_name in always_exclude:
                continue

            # Include if it's a direct field or in always_include
            if field_name in direct_annotations or field_name in always_include:
                filtered_schema["properties"][field_name] = field_schema

                # Add to required if it was required in the original schema
                if "required" in full_schema and field_name in full_schema["required"]:
                    filtered_schema["required"].append(field_name)

    # If there are definitions in the schema (for nested models), include them
    if "$defs" in full_schema:
        filtered_schema["$defs"] = full_schema["$defs"]

    return filtered_schema


# NOTE: Embedding models sync removed - embeddings now handled by
# DenseEmbedder and SparseEmbedder in platform/embedders/, not decorator-based models


async def _sync_entity_definitions(db: AsyncSession) -> Dict[str, dict]:
    """Sync entity definitions with the database based on chunk classes.

    Args:
        db (AsyncSession): Database session

    Returns:
        Dict[str, dict]: Mapping of module names to their entity details:
            - entity_ids: list[str] - UUIDs of entity definitions for this module
            - entity_classes: list[str] - Full class names of the entities in this module
    """
    sync_logger.info("Syncing entity definitions to database.")

    # Get all Python files in the entities directory that aren't base or init files
    entity_files = [
        f
        for f in os.listdir(PLATFORM_DIR / "entities")
        if f.endswith(".py") and not f.startswith("__")
    ]

    from airweave.platform.entities._base import BaseEntity

    entity_definitions = []
    entity_registry = {}  # Track all entities system-wide
    module_registry = {}  # Track entities by module

    for entity_file in entity_files:
        module_name = entity_file[:-3]  # Remove .py extension
        # Initialize module entry if not exists
        if module_name not in module_registry:
            module_registry[module_name] = {
                "entity_classes": [],
                "entity_names": [],
            }

        # Import the module to get its chunk classes
        full_module_name = f"airweave.platform.entities.{module_name}"
        module = importlib.import_module(full_module_name)

        # Find all chunk classes (subclasses of BaseEntity) in the module
        for name, cls in inspect.getmembers(module, inspect.isclass):
            # Check if it's a subclass of BaseEntity (or any class from _base.py)
            # AND the class is actually defined in this module (not imported)
            if (
                issubclass(cls, BaseEntity)
                and cls.__module__
                != "airweave.platform.entities._base"  # Exclude all classes from _base.py
                and cls.__module__ == full_module_name
            ):
                if name in entity_registry:
                    raise ValueError(
                        f"Duplicate entity name '{name}' found in {full_module_name}. "
                        f"Already registered from {entity_registry[name]['module']}"
                    )

                # Validate that all fields in the class use Pydantic Field with descriptions
                _validate_entity_class_fields(cls, name, module_name)

                # Register the entity
                entity_registry[name] = {
                    "class_name": f"{cls.__module__}.{cls.__name__}",
                    "module": module_name,
                }

                # Add to module registry
                module_registry[module_name]["entity_classes"].append(
                    f"{cls.__module__}.{cls.__name__}"
                )
                module_registry[module_name]["entity_names"].append(name)

                # Create entity definition with filtered schema
                entity_def = schemas.EntityDefinitionCreate(
                    name=name,
                    description=cls.__doc__ or f"Data from {name}",
                    type=EntityType.JSON,
                    entity_schema=_get_entity_schema_with_direct_fields_only(
                        cls
                    ),  # Get filtered schema
                    module_name=module_name,
                    class_name=cls.__name__,
                )
                entity_definitions.append(entity_def)

    # Sync entities
    await crud.entity_definition.sync(db, entity_definitions, unique_field="name")

    # Get all entities to build the mapping
    all_entities = await crud.entity_definition.get_all(db)

    # Create a mapping of entity names to their IDs
    entity_id_map = {e.name: str(e.id) for e in all_entities}

    # Add entity IDs to the module registry
    for module_name, module_info in module_registry.items():
        entity_ids = [
            entity_id_map[name] for name in module_info["entity_names"] if name in entity_id_map
        ]
        module_registry[module_name]["entity_ids"] = entity_ids

    sync_logger.info(f"Synced {len(entity_definitions)} entity definitions to database.")
    return module_registry


async def _sync_sources(
    db: AsyncSession, sources: list[Type[BaseSource]], module_entity_map: Dict[str, dict]
) -> None:
    """Sync sources with the database.

    Args:
    -----
        db (AsyncSession): Database session
        sources (list[Type[BaseSource]]): List of source classes
        module_entity_map (Dict[str, dict]): Mapping of module names to entity definitions
    """
    sync_logger.info("Syncing sources to database.")

    # Filter out internal sources if ENABLE_INTERNAL_SOURCES is False.
    # Uses the `internal=True` flag from the @source decorator as the single source of truth.
    filtered_sources = sources
    if not settings.ENABLE_INTERNAL_SOURCES:
        filtered_sources = [s for s in sources if not s.is_internal()]
        skipped_count = len(sources) - len(filtered_sources)
        if skipped_count > 0:
            sync_logger.info(
                f"Skipping {skipped_count} internal source(s) "
                "(set ENABLE_INTERNAL_SOURCES=true to enable)"
            )

    source_definitions = []
    for source_class in filtered_sources:
        # Get the source's short name (e.g., "slack" for SlackSource)
        source_module_name = source_class.short_name

        # NEW: Validate template configuration if source has templates
        try:
            _validate_source_template_config(source_class)
        except ValueError:
            # Template validation failures are critical - fail the sync
            sync_logger.error(f"Template validation failed for {source_module_name}")
            raise

        # Get entity definition short names for this module
        output_entity_definitions = []
        if source_module_name in module_entity_map:
            output_entity_definitions = module_entity_map[source_module_name].get(
                "entity_names", []
            )

        # Convert oauth_type enum to string if present
        oauth_type = getattr(source_class, "oauth_type", None)
        if oauth_type:
            oauth_type = oauth_type.value if hasattr(oauth_type, "value") else oauth_type

        # Convert rate_limit_level enum to string if present
        rate_limit_level = getattr(source_class, "rate_limit_level", None)
        if rate_limit_level:
            rate_limit_level = (
                rate_limit_level.value if hasattr(rate_limit_level, "value") else rate_limit_level
            )

        source_def = schemas.SourceCreate(
            name=source_class.source_name,
            description=source_class.__doc__,
            auth_methods=[m.value for m in getattr(source_class, "auth_methods", [])],
            oauth_type=oauth_type,
            requires_byoc=getattr(source_class, "requires_byoc", False),
            auth_config_class=getattr(source_class.auth_config_class, "__name__", None),
            config_class=getattr(source_class.config_class, "__name__", None),
            short_name=source_class.short_name,
            class_name=source_class.__name__,
            output_entity_definitions=output_entity_definitions,
            labels=getattr(source_class, "labels", []),
            supports_continuous=getattr(source_class, "supports_continuous", False),
            federated_search=getattr(source_class, "federated_search", False),
            supports_temporal_relevance=getattr(source_class, "supports_temporal_relevance", True),
            supports_access_control=getattr(source_class, "supports_access_control", False),
            rate_limit_level=rate_limit_level,
            feature_flag=getattr(source_class, "feature_flag", None),
        )
        source_definitions.append(source_def)

    await crud.source.sync(db, source_definitions)
    sync_logger.info(f"Synced {len(source_definitions)} sources to database.")


async def _sync_destinations(db: AsyncSession, destinations: list[Type[BaseDestination]]) -> None:
    """Sync destinations with the database.

    Args:
        db (AsyncSession): Database session
        destinations (list[Type[BaseDestination]]): List of destination classes
    """
    sync_logger.info("Syncing destinations to database.")

    destination_definitions = []
    for dest_class in destinations:
        dest_def = schemas.DestinationCreate(
            name=dest_class.destination_name,
            description=dest_class.__doc__,
            short_name=dest_class.short_name,
            class_name=dest_class.__name__,
            auth_config_class=getattr(dest_class.auth_config_class, "__name__", None),
            labels=getattr(dest_class, "labels", []),
        )
        destination_definitions.append(dest_def)

    await crud.destination.sync(db, destination_definitions)
    sync_logger.info(f"Synced {len(destination_definitions)} destinations to database.")


async def _sync_auth_providers(
    db: AsyncSession, auth_providers: list[Type[BaseAuthProvider]]
) -> None:
    """Sync auth providers with the database.

    Args:
        db (AsyncSession): Database session
        auth_providers (list[Type[BaseAuthProvider]]): List of auth provider classes
    """
    sync_logger.info("Syncing auth providers to database.")

    auth_provider_definitions = []
    for auth_provider_class in auth_providers:
        auth_config_cls = getattr(auth_provider_class, "auth_config_class", None)
        config_cls = getattr(auth_provider_class, "config_class", None)
        auth_provider_def = schemas.AuthProviderCreate(
            name=auth_provider_class.provider_name,
            short_name=auth_provider_class.short_name,
            class_name=auth_provider_class.__name__,
            description=auth_provider_class.__doc__,
            auth_config_class=getattr(auth_config_cls, "__name__", None)
            if auth_config_cls
            else None,
            config_class=getattr(config_cls, "__name__", None) if config_cls else None,
        )
        auth_provider_definitions.append(auth_provider_def)

    await crud.auth_provider.sync(db, auth_provider_definitions)
    sync_logger.info(f"Synced {len(auth_provider_definitions)} auth providers to database.")


# NOTE: Transformer sync functions removed - chunking now handled by
# CodeChunker and SemanticChunker in entity_pipeline.py, not decorator-based transformers


async def sync_platform_components(db: AsyncSession) -> None:
    """Sync all platform components with the database.

    Args:
        db (AsyncSession): Database session

    Raises:
        Exception: If any part of the sync process fails, with detailed error messages to help
        diagnose the issue
    """
    sync_logger.info("Starting platform components sync...")

    try:
        components = _get_decorated_classes()
        c = components

        # Log component counts to help diagnose issues
        sync_logger.info(
            f"Found {len(c['sources'])} sources, {len(c['destinations'])} destinations, "
            f"{len(c['auth_providers'])} auth providers."
        )

        # First sync entities to get their IDs
        module_entity_map = await _sync_entity_definitions(db)

        # Sync platform components
        await _sync_sources(db, components["sources"], module_entity_map)
        await _sync_destinations(db, components["destinations"])
        await _sync_auth_providers(db, components["auth_providers"])

        sync_logger.info("Platform components sync completed successfully.")
    except ImportError as e:
        sync_logger.error(f"Platform sync failed due to import error: {e}")
        sync_logger.error(
            "Check that all required dependencies are installed and all modules can be imported."
        )
        raise
    except Exception as e:
        sync_logger.error(f"Platform sync failed with error: {e}")
        sync_logger.error("Check for detailed error messages above to identify the specific issue.")
        raise
