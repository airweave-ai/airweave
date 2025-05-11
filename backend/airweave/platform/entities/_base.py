"""Entity schemas."""

import hashlib
import importlib
import json
import os
import sys
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Type
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, create_model


class DestinationAction(str, Enum):
    """Action for an entity."""

    INSERT = "insert"
    UPDATE = "update"
    KEEP = "keep"


class Breadcrumb(BaseModel):
    """Breadcrumb for tracking ancestry."""

    entity_id: str
    name: str
    type: str


class BaseEntity(BaseModel):
    """Base entity schema."""

    # Set in source connector
    entity_id: str = Field(
        ..., description="ID of the entity this entity represents in the source."
    )
    breadcrumbs: List[Breadcrumb] = Field(
        default_factory=list, description="List of breadcrumbs for this entity."
    )

    # Set in sync orchestrator
    db_entity_id: UUID = Field(
        default_factory=uuid4, description="Unique ID of the entity in the DB."
    )
    source_name: Optional[str] = Field(
        None, description="Name of the source this entity came from."
    )
    sync_id: Optional[UUID] = Field(None, description="ID of the sync this entity belongs to.")
    sync_job_id: Optional[UUID] = Field(
        None, description="ID of the sync job this entity belongs to."
    )
    url: Optional[str] = Field(None, description="URL to the original content, if applicable.")
    sync_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata for the sync."
    )
    white_label_user_identifier: Optional[str] = Field(
        None, description="White label user identifier."
    )
    white_label_id: Optional[UUID] = Field(None, description="White label ID.")
    white_label_name: Optional[str] = Field(None, description="White label name.")

    parent_entity_id: Optional[str] = Field(
        None, description="ID of the parent entity in the source."
    )

    vector: Optional[List[float]] = Field(None, description="Vector representation of the entity.")

    class Config:
        """Pydantic config."""

        from_attributes = True

    def hash(self) -> str:
        """Hash the entity using only content-relevant fields."""
        if getattr(self, "_hash", None):
            return self._hash

        # Define content-relevant fields (exclude metadata fields)
        metadata_fields = {
            "sync_job_id",
            "vector",
            "_hash",
            "db_entity_id",
            "source_name",
            "sync_id",
            "sync_metadata",
            "white_label_user_identifier",
            "white_label_id",
            "white_label_name",
        }

        # Get field names from the model
        all_fields = set(self.model_fields.keys())
        content_fields = all_fields - metadata_fields

        # Extract only content fields
        data = {k: v for k, v in self.model_dump().items() if k in content_fields}

        # Use stable serialization
        def stable_serialize(obj):
            if isinstance(obj, dict):
                return {k: stable_serialize(v) for k, v in sorted(obj.items())}
            elif isinstance(obj, (list, tuple)):
                return [stable_serialize(x) for x in obj]
            elif isinstance(obj, (str, int, float, bool, type(None))):
                return obj
            else:
                # Handle non-serializable types consistently
                return str(obj)

        # Create stable representation
        stable_data = stable_serialize(data)

        # Use canonical JSON encoding for consistent string representation
        json_str = json.dumps(stable_data, sort_keys=True, separators=(",", ":"))

        # Compute hash
        self._hash = hashlib.sha256(json_str.encode()).hexdigest()
        return self._hash

    def to_storage_dict(self, exclude_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert entity to a dictionary suitable for storage in vector databases.

        This method handles serialization of complex types (dicts, lists) to JSON strings,
        except for specific fields that should remain as objects (like breadcrumbs).

        Args:
            exclude_fields: Optional list of field names to exclude from serialization

        Returns:
            Dict with all fields properly serialized for storage
        """
        # Start with the full model dump
        data = self.model_dump()

        # Remove excluded fields
        if exclude_fields:
            for field in exclude_fields:
                if field in data:
                    del data[field]

        # Fields that should remain as objects and not be JSON serialized
        object_fields = {"breadcrumbs"}

        # Serialize complex types to JSON strings, except for specified object fields
        for key, value in data.items():
            if key not in object_fields and isinstance(value, (dict, list)):
                data[key] = json.dumps(value)

        return data


class ChunkEntity(BaseEntity):
    """Base class for entities that are storable and embeddable chunks of data."""

    # Default fields to exclude when creating storage dict
    default_exclude_fields: List[str] = [
        "vector",  # Exclude the vector itself from the payload
        "sync_job_id",
        "white_label_user_identifier",
        "white_label_id",
        "white_label_name",
        "sync_metadata",
        "parent_entity_id",
        "default_exclude_fields",
        "_hash",
    ]

    def to_storage_dict(self, exclude_fields: Optional[List[str]] = None) -> Dict[str, Any]:
        """Convert entity to a dictionary suitable for storage in vector databases.

        This implementation uses default exclusions to keep only the essential fields.

        Args:
            exclude_fields: Optional list of field names to exclude from serialization
                            (adds to default exclusions)

        Returns:
            Dict with minimal fields properly serialized for storage
        """
        # Combine default and provided exclusions
        all_exclusions = list(self.default_exclude_fields)
        if exclude_fields:
            all_exclusions.extend(exclude_fields)
        exclusions = list(set(all_exclusions))  # Remove duplicates

        # Use parent implementation with our combined exclusions
        return super().to_storage_dict(exclude_fields=exclusions)


class ParentEntity(BaseEntity):
    """Base class for entities that are parents of other entities."""

    pass


class PolymorphicEntity(ChunkEntity):
    """Base class for dynamically generated entities.

    This class serves as the base for entities that are created at runtime,
    particularly for database table entities where the schema is determined
    by the table structure.
    """

    __abstract__ = True
    table_name: str
    schema_name: Optional[str] = None
    primary_key_columns: List[str] = Field(default_factory=list)

    @classmethod
    def create_table_entity_class(
        cls,
        table_name: str,
        schema_name: Optional[str],
        columns: Dict[str, Any],
        primary_keys: List[str],
    ) -> Type["PolymorphicEntity"]:
        """Create a new entity class for a database table.

        Args:
            table_name: Name of the database table
            schema_name: Optional database schema name
            columns: Dictionary of column names to their types and metadata
            primary_keys: List of primary key column names

        Returns:
            A new entity class with fields matching the table structure
        """
        # Create field definitions for the new model
        fields: Dict[str, Any] = {
            "table_name": (str, Field(default=table_name)),
            "schema_name": (Optional[str], Field(default=schema_name)),
            "primary_key_columns": (List[str], Field(default_factory=lambda: primary_keys)),
        }

        # Add fields for each database column
        for col_name, col_info in columns.items():
            python_type = col_info.get("python_type", Any)
            if col_name == "id":
                col_name = "id_"
            fields[col_name] = (Optional[python_type], Field(default=None))

        # Create the new model class
        model_name = f"{table_name.title().replace('_', '')}TableEntity"
        return create_model(
            model_name,
            __base__=cls,
            **fields,
        )


# Registry to track which FileEntity subclasses have had their models created
_file_entity_models_created = set()


class FileEntity(BaseEntity):
    """Base schema for file entities."""

    file_id: str = Field(..., description="ID of the file in the source system")
    name: str = Field(..., description="Name of the file")
    mime_type: Optional[str] = Field(None, description="MIME type of the file")
    size: Optional[int] = Field(None, description="Size of the file in bytes")
    download_url: str = Field(..., description="URL to download the file")
    should_skip: bool = Field(False, description="Flag indicating if this file should be skipped")

    # File handling fields - set by file handler
    file_uuid: Optional[UUID] = Field(None, description="UUID assigned by the file manager")
    local_path: Optional[str] = Field(
        None, description="Temporary local path if file is downloaded"
    )
    checksum: Optional[str] = Field(None, description="File checksum/hash if available")
    total_size: Optional[int] = Field(None, description="Total size of the file in bytes")

    def hash(self) -> str:
        """Hash the file entity.

        For files, we try the following strategies in order:
        1. If local_path is available, compute hash from actual file contents
        2. If checksum is available, use it as part of metadata hash
        3. Fall back to parent hash method using all metadata
        """
        if getattr(self, "_hash", None):
            return self._hash

        if self.local_path:
            # If we have the actual file, compute hash from its contents
            try:
                with open(self.local_path, "rb") as f:
                    content = f.read()
                    self._hash = hashlib.sha256(content).hexdigest()
                    return self._hash
            except Exception:
                # If file read fails, fall through to next method
                pass
        else:
            raise ValueError("File has no local path")

    @classmethod
    def create_parent_chunk_models(cls) -> Tuple[Type["ParentEntity"], Type["ChunkEntity"]]:
        """Create parent and chunk entity models for this file entity.

        This method dynamically generates two models:
        1. A parent model that inherits all fields from the source FileEntity subclass
           and represents the complete file metadata from the source system
        2. A chunk model that represents a chunk of the file's content with standardized
           fields for vector/graph DB storage

        Returns:
            A tuple of (ParentEntityClass, ChunkEntityClass)
        """
        # Get the class name prefix (e.g., "AsanaFile" from "AsanaFileEntity")
        class_name_prefix = cls.__name__.replace("Entity", "")

        # For parent, get all fields from the source FileEntity subclass
        parent_fields = {
            "number_of_chunks": (
                int,
                Field(default=0, description="Number of chunks of this file"),
            ),
        }
        for name, field in cls.model_fields.items():
            parent_fields[name] = (field.annotation, field)

        parent_model = create_model(
            f"{class_name_prefix}Parent", __base__=ParentEntity, **parent_fields
        )

        # Set module name to match the source entity's module
        parent_model.__module__ = cls.__module__

        # For chunk, create standardized fields for vector/graph DB storage
        chunk_fields = {
            "md_title": (Optional[str], Field(None, description="Title or heading of the chunk")),
            "md_content": (str, Field(..., description="The actual content of the chunk")),
            "md_type": (
                str,
                Field(..., description="Type of content (e.g., paragraph, table, list)"),
            ),
            "metadata": (
                Dict[str, Any],
                Field(default_factory=dict, description="Additional metadata about the chunk"),
            ),
            "md_position": (
                Optional[int],
                Field(None, description="Position of this chunk in the document"),
            ),
            "md_parent_title": (
                Optional[str],
                Field(None, description="Title of the parent document"),
            ),
            "md_parent_url": (
                Optional[str],
                Field(None, description="URL of the parent document if available"),
            ),
        }

        chunk_model = create_model(
            f"{class_name_prefix}Chunk", __base__=ChunkEntity, **chunk_fields
        )

        # Set module name to match the source entity's module
        chunk_model.__module__ = cls.__module__

        # Add docstrings to the models
        parent_model.__doc__ = (
            f"Parent entity for {class_name_prefix} files. Generated from {cls.__name__}."
        )
        chunk_model.__doc__ = (
            f"Chunk entity for {class_name_prefix} files. Generated from {cls.__name__}."
        )

        # Register models in the module they belong to
        module = sys.modules[cls.__module__]
        setattr(module, parent_model.__name__, parent_model)
        setattr(module, chunk_model.__name__, chunk_model)

        # Mark this class as having had its models created
        _file_entity_models_created.add(cls)

        return parent_model, chunk_model


class CodeFileEntity(ChunkEntity):
    """Base schema for code file entities."""

    # Basic entity fields
    source_name: str = Field(..., description="Source name")
    name: str = Field(..., description="File name")

    # File specific fields
    file_id: str = Field(..., description="Unique ID of the file")
    mime_type: Optional[str] = Field(None, description="MIME type of the file")
    size: int = Field(..., description="Size of the file in bytes")

    # Code specific fields
    language: Optional[str] = Field(None, description="Programming language of the file")
    line_count: Optional[int] = Field(None, description="Number of lines in the file")
    path_in_repo: str = Field(..., description="Path of the file within the repository")
    last_modified: Optional[datetime] = Field(None, description="Last modification timestamp")
    commit_id: Optional[str] = Field(None, description="Last commit ID that modified this file")
    repo_name: str = Field(..., description="Name of the repository containing this file")
    repo_owner: str = Field(..., description="Owner of the repository")

    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata about the file"
    )

    summary: Optional[str] = Field(None, description="Summary of the file")

    # Content and navigation
    url: str = Field(..., description="URL to view the file")
    content: Optional[str] = Field(None, description="File content if available")
    breadcrumbs: List[Breadcrumb] = Field(
        default_factory=list, description="Breadcrumb navigation path"
    )


def ensure_file_entity_models():
    """Ensure that all FileEntity subclasses have their parent and chunk models created.

    This function can be called at runtime to make sure all FileEntity subclasses
    have had their parent and chunk models created and registered in their modules.
    """
    # First, proactively import all entity modules
    entity_files = [
        f
        for f in os.listdir("airweave/platform/entities")
        if f.endswith(".py") and not f.startswith("__")
    ]

    for entity_file in entity_files:
        module_name = entity_file[:-3]  # Remove .py extension
        full_module_name = f"airweave.platform.entities.{module_name}"
        try:
            importlib.import_module(full_module_name)
        except Exception as e:
            print(f"Error importing entity module {full_module_name}: {e}")

    # Now check all loaded modules for FileEntity subclasses
    for _, module in list(sys.modules.items()):
        # Skip modules that don't have __dict__ attribute
        if not hasattr(module, "__dict__"):
            continue

        if not module.__name__.startswith("airweave.platform"):
            continue

        # Look for FileEntity subclasses in the module
        for _, cls in list(module.__dict__.items()):
            # Check if it's a class and a subclass of FileEntity (but not FileEntity itself)
            if (
                isinstance(cls, type)
                and issubclass(cls, FileEntity)
                and cls is not FileEntity
                and cls not in _file_entity_models_created
            ):
                try:
                    # Create parent and chunk models
                    parent_model, chunk_model = cls.create_parent_chunk_models()
                    print(
                        "Runtime: Auto-generated parent and chunk models for "
                        f"{cls.__name__} in {cls.__module__}"
                    )
                except Exception as e:
                    print(f"Runtime: Error creating models for {cls.__name__}: {e}")
