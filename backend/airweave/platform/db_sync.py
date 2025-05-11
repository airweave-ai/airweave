"""Module for syncing embedding models, sources, and destinations with the database."""

import importlib
import inspect
import os
from typing import Callable, Dict, Type, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import get_type_hints

from airweave import crud, schemas
from airweave.core.logging import logger
from airweave.models.entity_definition import EntityType
from airweave.platform.destinations._base import BaseDestination
from airweave.platform.embedding_models._base import BaseEmbeddingModel
from airweave.platform.sources._base import BaseSource

sync_logger = logger.with_prefix("Platform sync: ").with_context(component="platform_sync")


def _process_module_classes(module, components: Dict[str, list[Type | Callable]]) -> None:
    """Process classes in a module and add them to the components dictionary.

    Args:
        module: The module to process
        components: Dictionary to add components to
    """
    # Scan for classes
    for _, cls in inspect.getmembers(module, inspect.isclass):
        if getattr(cls, "_is_source", False):
            components["sources"].append(cls)
        elif getattr(cls, "_is_destination", False):
            components["destinations"].append(cls)
        elif getattr(cls, "_is_embedding_model", False):
            components["embedding_models"].append(cls)


def _process_module_functions(module, components: Dict[str, list[Type | Callable]]) -> None:
    """Process functions in a module and add them to the components dictionary.

    Args:
        module: The module to process
        components: Dictionary to add components to
    """
    # Scan for transformer functions
    for _, func in inspect.getmembers(module, inspect.isfunction):
        if getattr(func, "_is_transformer", False):
            components["transformers"].append(func)


def _get_decorated_classes(directory: str) -> Dict[str, list[Type | Callable]]:
    """Scan directory for decorated classes and functions.

    Args:
        directory (str): The directory to scan.

    Returns:
        Dict[str, list[Type | Callable]]: Dictionary of decorated classes and functions by type.

    Raises:
        ImportError: If any module cannot be imported. This ensures the sync process fails if there
        are any issues.
    """
    components = {
        "sources": [],
        "destinations": [],
        "embedding_models": [],
        "transformers": [],
    }

    base_package = directory.replace("/", ".")

    for root, _, files in os.walk(directory):
        # Skip files in the root directory
        if root == directory:
            continue

        for filename in files:
            if not filename.endswith(".py") or filename.startswith("_"):
                continue

            relative_path = os.path.relpath(root, directory)
            module_path = os.path.join(relative_path, filename[:-3]).replace("/", ".")
            full_module_name = f"{base_package}.{module_path}"

            try:
                module = importlib.import_module(full_module_name)
                _process_module_classes(module, components)
                _process_module_functions(module, components)
            except ImportError as e:
                # Convert the warning into a fatal error to prevent silent failures
                error_msg = (
                    f"Failed to import {full_module_name}: {e}\n"
                    f"This is likely due to missing dependencies required by this module.\n"
                    f"If this module contains transformers, sources, or destinations, they will not"
                    f" be registered."
                )
                sync_logger.error(error_msg)
                # Re-raise the exception to fail the sync process
                raise ImportError(f"Module import failed: {full_module_name}") from e

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


async def _sync_embedding_models(db: AsyncSession, models: list[Type[BaseEmbeddingModel]]) -> None:
    """Sync embedding models with the database.

    Args:
        db (AsyncSession): Database session
        models (list[Type[BaseEmbeddingModel]]): List of embedding model classes
    """
    sync_logger.info("Syncing embedding models to database.")

    model_definitions = []
    for model_class in models:
        model_def = schemas.EmbeddingModelCreate(
            name=model_class._name,
            short_name=model_class._short_name,
            class_name=model_class.__name__,
            description=model_class.__doc__,
            provider=model_class._provider,
            model_name=model_class._model_name,
            model_version=model_class._model_version,
            auth_type=model_class._auth_type,
            auth_config_class=model_class._auth_config_class,
        )
        model_definitions.append(model_def)

    await crud.embedding_model.sync(db, model_definitions)
    sync_logger.info(f"Synced {len(model_definitions)} embedding models to database.")


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
        for f in os.listdir("airweave/platform/entities")
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

                # Create entity definition
                entity_def = schemas.EntityDefinitionCreate(
                    name=name,
                    description=cls.__doc__ or f"Data from {name}",
                    type=EntityType.JSON,
                    entity_schema=cls.model_json_schema(),  # Get the actual schema
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

    source_definitions = []
    for source_class in sources:
        # Get the source's short name (e.g., "slack" for SlackSource)
        source_module_name = source_class._short_name

        # Get entity IDs for this module
        output_entity_ids = []
        if source_module_name in module_entity_map:
            output_entity_ids = [
                UUID(id) for id in module_entity_map[source_module_name].get("entity_ids", [])
            ]

        source_def = schemas.SourceCreate(
            name=source_class._name,
            description=source_class.__doc__,
            auth_type=source_class._auth_type,
            auth_config_class=source_class._auth_config_class,
            short_name=source_class._short_name,
            class_name=source_class.__name__,
            output_entity_definition_ids=output_entity_ids,
            labels=getattr(source_class, "_labels", []),
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
            name=dest_class._name,
            description=dest_class.__doc__,
            short_name=dest_class._short_name,
            class_name=dest_class.__name__,
            auth_type=dest_class._auth_type,
            auth_config_class=dest_class._auth_config_class,
            labels=getattr(dest_class, "_labels", []),
        )
        destination_definitions.append(dest_def)

    await crud.destination.sync(db, destination_definitions)
    sync_logger.info(f"Synced {len(destination_definitions)} destinations to database.")


def _get_type_names(type_hint) -> list[str]:
    """Extract type names from a type hint, handling Union types correctly.

    Args:
        type_hint: The type hint to extract names from

    Returns:
        list[str]: List of type names
    """
    # Handle Union types (both typing.Union and types.UnionType (|))
    if hasattr(type_hint, "__origin__"):
        if type_hint.__origin__ is Union or str(type_hint.__origin__) == "typing.Union":
            return [t.__name__ for t in type_hint.__args__]
        if str(type_hint.__origin__) == "|":  # Python 3.10+ Union type
            return [t.__name__ for t in type_hint.__args__]
        if type_hint.__origin__ is list:
            # For list types, process the inner type
            return _get_type_names(type_hint.__args__[0])
        # Handle other generic types
        return [type_hint.__args__[0].__name__]

    # Handle UnionType at the base level (Python 3.10+ |)
    if str(type(type_hint)) == "<class 'types.UnionType'>":
        return [t.__name__ for t in type_hint.__args__]

    # Handle simple types
    return [type_hint.__name__]


def _build_entity_mappings(module_entity_map: Dict[str, dict]) -> tuple[dict, dict]:
    """Build mappings from class names and entity names to entity IDs.

    Args:
        module_entity_map: Mapping of module names to their entity details

    Returns:
        tuple: (entity_class_to_id_map, entity_name_to_id_map)
    """
    # Create a reverse mapping from class name to entity ID
    entity_class_to_id_map = {}
    # Create a mapping from entity name to entity ID
    entity_name_to_id_map = {}

    for module_info in module_entity_map.values():
        for i, name in enumerate(module_info.get("entity_names", [])):
            if i < len(module_info.get("entity_ids", [])):
                if name not in entity_name_to_id_map:
                    entity_name_to_id_map[name] = []
                entity_name_to_id_map[name].append(module_info["entity_ids"][i])

        for i, class_name in enumerate(module_info.get("entity_classes", [])):
            entity_name = module_info["entity_names"][i]
            # Find the entity ID for this class
            for entity_id in module_info.get("entity_ids", []):
                if (
                    entity_name
                    == module_info["entity_names"][module_info["entity_classes"].index(class_name)]
                ):
                    if class_name not in entity_class_to_id_map:
                        entity_class_to_id_map[class_name] = []
                    entity_class_to_id_map[class_name].append(entity_id)

    return entity_class_to_id_map, entity_name_to_id_map


def _create_transformer_definition(
    transformer_func: Callable, entity_name_to_id_map: dict
) -> schemas.TransformerCreate:
    """Create a transformer definition from a transformer function.

    Args:
        transformer_func: The transformer function
        entity_name_to_id_map: Mapping from entity names to entity IDs

    Returns:
        schemas.TransformerCreate: The transformer definition
    """
    # Get type hints for input/output
    type_hints = get_type_hints(transformer_func)

    # Get input type from first parameter
    first_param = next(iter(inspect.signature(transformer_func).parameters.values()))
    input_type = type_hints[first_param.name]
    input_type_name = input_type.__name__

    # Base types from _base.py are special cases
    base_types = [
        "BaseEntity",
        "ChunkEntity",
        "ParentEntity",
        "FileEntity",
        "PolymorphicEntity",
        "CodeFileEntity",
    ]
    # For input types
    input_entity_ids = []
    if input_type_name in entity_name_to_id_map:
        input_entity_ids = [UUID(id) for id in entity_name_to_id_map[input_type_name]]
    elif input_type_name in base_types:
        # For base types, we don't require entity IDs since they're not directly registered
        # as entity definitions (they're abstract base classes)
        sync_logger.info(
            f"Transformer {transformer_func._name} uses base type {input_type_name} as input"
        )
    else:
        raise ValueError(
            f"Transformer {transformer_func._name} has unknown input type {input_type_name}"
        )

    # Get output types from return annotation
    return_type = type_hints["return"]
    output_types = _get_type_names(return_type)

    # For output types
    output_entity_ids = []
    for type_name in output_types:
        if type_name in entity_name_to_id_map:
            output_entity_ids.extend([UUID(id) for id in entity_name_to_id_map[type_name]])
        elif type_name in base_types:
            # For base types, don't add entity IDs but don't error either
            sync_logger.info(
                f"Transformer {transformer_func._name} uses base type {type_name} as output"
            )
        else:
            raise ValueError(
                f"Transformer {transformer_func._name} has unknown output type {type_name}"
            )

    return schemas.TransformerCreate(
        name=transformer_func._name,
        description=transformer_func.__doc__,
        method_name=transformer_func.__name__,
        module_name=transformer_func.__module__,
        auth_type=getattr(transformer_func, "_auth_type", None),
        auth_config_class=getattr(transformer_func, "_auth_config_class", None),
        config_schema=getattr(transformer_func, "_config_schema", {}),
        input_entity_definition_ids=input_entity_ids,
        output_entity_definition_ids=output_entity_ids,
    )


async def _sync_transformers(
    db: AsyncSession, transformers: list[Callable], module_entity_map: Dict[str, dict]
) -> None:
    """Sync transformers with the database.

    Args:
        db (AsyncSession): Database session
        transformers (list[Callable]): List of transformer functions
        module_entity_map (Dict[str, dict]): Mapping of module names to their entity details
    """
    sync_logger.info("Syncing transformers to database.")

    # Build entity mappings
    _, entity_name_to_id_map = _build_entity_mappings(module_entity_map)

    # Create transformer definitions
    transformer_definitions = [
        _create_transformer_definition(func, entity_name_to_id_map) for func in transformers
    ]

    await crud.transformer.sync(db, transformer_definitions, unique_field="method_name")
    sync_logger.info(f"Synced {len(transformer_definitions)} transformers to database.")


async def sync_platform_components(platform_dir: str, db: AsyncSession) -> None:
    """Sync all platform components with the database.

    Args:
        platform_dir (str): Directory containing platform components
        db (AsyncSession): Database session

    Raises:
        Exception: If any part of the sync process fails, with detailed error messages to help
        diagnose the issue
    """
    sync_logger.info("Starting platform components sync...")

    try:
        components = _get_decorated_classes(platform_dir)
        c = components

        # Log component counts to help diagnose issues
        sync_logger.info(
            f"Found {len(c['sources'])} sources, {len(c['destinations'])} destinations, "
            f"{len(c['embedding_models'])} embedding models, {len(c['transformers'])} transformers."
        )

        # First sync entities to get their IDs
        module_entity_map = await _sync_entity_definitions(db)

        await _sync_embedding_models(db, components["embedding_models"])
        await _sync_sources(db, components["sources"], module_entity_map)
        await _sync_destinations(db, components["destinations"])
        await _sync_transformers(db, components["transformers"], module_entity_map)

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
