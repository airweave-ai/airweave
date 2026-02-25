"""Textual representation builder for entities."""

import asyncio
import os
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from airweave.core.shared_models import AirweaveFieldFlag
from airweave.platform.entities._base import BaseEntity, CodeFileEntity, FileEntity, WebEntity
from airweave.platform.sync.exceptions import EntityProcessingError, SyncFailureError
from airweave.platform.sync.file_types import SUPPORTED_FILE_EXTENSIONS

if TYPE_CHECKING:
    from airweave.platform.contexts import SyncContext
    from airweave.platform.contexts.runtime import SyncRuntime


class TextualRepresentationBuilder:
    """Builds textual representations for entities.

    Handles:
    - Building metadata sections with entity info and embeddable fields
    - Routing entities to appropriate content converters
    - Batch conversion orchestration
    """

    # Default batch size for converters without specific config
    DEFAULT_CONVERTER_BATCH_SIZE = 10

    # ------------------------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------------------------

    async def build_for_batch(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> List[BaseEntity]:
        """Build textual_representation for all entities in batch.

        Args:
            entities: Entities to build representations for
            sync_context: Sync context with logger
            runtime: Sync runtime with live services

        Returns:
            List of entities that succeeded (failed ones removed)

        Note:
            Modifies entities in-place, setting textual_representation.
            Failed entities are removed and counted as skipped.
        """
        source_name = sync_context.source_short_name

        # Step 1: Build metadata section for all entities
        await self._build_metadata_for_all(entities, source_name)

        # Step 2: Partition entities by converter
        converter_groups, failed_entities = self._partition_by_converter(entities, sync_context)

        # Step 3: Convert each partition
        additional_failures = await self._convert_partitions(converter_groups, sync_context)
        failed_entities.extend(additional_failures)

        # Step 4: Handle failures
        await self._handle_conversion_failures(entities, failed_entities, sync_context, runtime)

        return entities

    # ------------------------------------------------------------------------------------
    # Metadata Building
    # ------------------------------------------------------------------------------------

    async def _build_metadata_for_all(self, entities: List[BaseEntity], source_name: str) -> None:
        """Build metadata section for all entities.

        Args:
            entities: Entities to build metadata for
            source_name: Name of the source connector

        Note:
            CodeFileEntity is exempt because code is self-documenting.
        """

        async def build_metadata(entity: BaseEntity):
            metadata = self.build_metadata_section(entity, source_name)
            if not metadata and not isinstance(entity, CodeFileEntity):
                raise EntityProcessingError(f"Empty metadata for {entity.entity_id}")
            entity.textual_representation = metadata

        await asyncio.gather(*[build_metadata(e) for e in entities])

    def build_metadata_section(self, entity: BaseEntity, source_name: str) -> str:
        """Build metadata section for any entity type.

        This method is public to allow federated search sources to build
        textual representations without going through the full sync pipeline.

        For CodeFileEntity, returns empty string - code is self-documenting.

        Args:
            entity: Entity to build metadata for
            source_name: Name of the source (e.g., "slack", "github")

        Returns:
            Markdown formatted metadata section
        """
        # Skip metadata for code files - AST chunking works better on raw code
        if isinstance(entity, CodeFileEntity):
            return ""

        entity_type = entity.__class__.__name__
        lines = [
            "# Metadata",
            "",
            f"**Source**: {source_name}",
            f"**Type**: {entity_type}",
            f"**Name**: {entity.name}",
        ]

        # Add breadcrumb path if present
        if entity.breadcrumbs and len(entity.breadcrumbs) > 0:
            path_str = self._format_breadcrumb_path(entity.breadcrumbs)
            lines.append(f"**Path**: {path_str}")

        # Add embeddable fields
        embeddable_fields = self._extract_embeddable_fields(entity)
        if embeddable_fields:
            lines.append("")
            lines.append(self._format_embeddable_fields_as_markdown(embeddable_fields))

        return "\n".join(lines)

    def _format_breadcrumb_path(self, breadcrumbs: list) -> str:
        """Format breadcrumb path for display.

        Args:
            breadcrumbs: List of breadcrumb objects with entity_type and name

        Returns:
            Formatted path string like "Type: Name → Type: Name"
        """
        path_parts = []
        for bc in breadcrumbs:
            clean_type = self._clean_entity_type_name(bc.entity_type)
            path_parts.append(f"{clean_type}: {bc.name}")
        return " → ".join(path_parts)

    def _clean_entity_type_name(self, entity_type: str) -> str:
        """Clean entity type name for display.

        Removes "Entity" suffix and source prefix.

        Args:
            entity_type: Raw entity type name like "AsanaProjectEntity"

        Returns:
            Cleaned name like "Project"
        """
        clean_type = entity_type

        # Remove "Entity" suffix
        if clean_type.endswith("Entity"):
            clean_type = clean_type[:-6]

        # Remove source prefix (e.g., "Asana", "Jira", "GitHub")
        for i in range(1, len(clean_type)):
            if clean_type[i].isupper():
                clean_type = clean_type[i:]
                break

        return clean_type

    # ------------------------------------------------------------------------------------
    # Field Extraction and Formatting
    # ------------------------------------------------------------------------------------

    def _extract_embeddable_fields(self, entity: BaseEntity) -> Dict[str, Any]:
        """Extract fields marked with embeddable=True.

        Args:
            entity: Entity to extract fields from

        Returns:
            Dict mapping field names to their values
        """
        fields = {}
        flag_key = (
            AirweaveFieldFlag.EMBEDDABLE.value
            if hasattr(AirweaveFieldFlag.EMBEDDABLE, "value")
            else AirweaveFieldFlag.EMBEDDABLE
        )

        for field_name, field_info in entity.__class__.model_fields.items():
            json_extra = field_info.json_schema_extra
            if json_extra and isinstance(json_extra, dict):
                if json_extra.get(flag_key):
                    value = getattr(entity, field_name, None)
                    if value is not None:
                        fields[field_name] = value

        return fields

    def _format_embeddable_fields_as_markdown(self, fields: Dict[str, Any]) -> str:
        """Convert embeddable fields dict to markdown.

        Args:
            fields: Dict of field names to values

        Returns:
            Markdown formatted string
        """
        lines = []
        for field_name, value in fields.items():
            label = field_name.replace("_", " ").title()
            formatted_value = self._format_value(value)
            lines.append(f"**{label}**: {formatted_value}")
        return "\n".join(lines)

    def _format_value(self, value: Any) -> str:
        """Format value for markdown - NO TRUNCATION.

        Args:
            value: Value to format

        Returns:
            Formatted string representation
        """
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    # ------------------------------------------------------------------------------------
    # Converter Routing
    # ------------------------------------------------------------------------------------

    def _partition_by_converter(
        self,
        entities: List[BaseEntity],
        sync_context: "SyncContext",
    ) -> Tuple[Dict[Any, List[Tuple[BaseEntity, str]]], List[BaseEntity]]:
        """Partition entities by their converter type.

        Args:
            entities: Entities to partition
            sync_context: Sync context for logging

        Returns:
            Tuple of (converter_groups, failed_entities) where:
            - converter_groups: Dict mapping converter to (entity, key) tuples
            - failed_entities: Entities that failed to get converter
        """
        failed_entities = []
        converter_groups: Dict[Any, List[Tuple[BaseEntity, str]]] = {}

        for entity in entities:
            try:
                converter, key = self._get_converter_and_key(entity)
                if converter is None:
                    # Entity type doesn't need content conversion
                    continue
                if converter not in converter_groups:
                    converter_groups[converter] = []
                converter_groups[converter].append((entity, key))
            except EntityProcessingError as e:
                sync_context.logger.warning(
                    f"Skipping {entity.__class__.__name__}[{entity.entity_id}]: {e}"
                )
                failed_entities.append(entity)

        return converter_groups, failed_entities

    def _get_converter_and_key(self, entity: BaseEntity) -> Tuple[Any, Optional[str]]:
        """Get the appropriate converter and key for an entity.

        Args:
            entity: The entity to get converter for

        Returns:
            Tuple of (converter, key) where:
            - converter: The converter module/instance to use
            - key: The key to pass to convert_batch

        Raises:
            EntityProcessingError: If entity type is not supported or missing required fields
        """
        from airweave.platform import converters

        # WebEntity: use web_converter with crawl_url
        if isinstance(entity, WebEntity):
            if not entity.crawl_url:
                raise EntityProcessingError(f"WebEntity {entity.entity_id} missing crawl_url")
            return converters.web_converter, entity.crawl_url

        # FileEntity: use file-type specific converter with local_path
        if isinstance(entity, FileEntity):
            if not entity.local_path:
                raise EntityProcessingError(f"FileEntity {entity.entity_id} missing local_path")
            converter = self._determine_converter_for_file(entity.local_path)
            return converter, entity.local_path

        # Other entity types don't need content conversion
        return None, None

    def _determine_converter_for_file(self, file_path: str) -> Any:
        """Determine converter module based on file extension.

        Args:
            file_path: Path to the file

        Returns:
            Converter module with convert_batch function

        Raises:
            EntityProcessingError: If file type is not supported
        """
        from airweave.platform import converters

        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        if ext not in SUPPORTED_FILE_EXTENSIONS:
            raise EntityProcessingError(f"Unsupported file type: {ext}")

        converter_map = {
            # Documents - Text extraction + Mistral OCR fallback
            ".pdf": converters.pdf_converter,
            ".docx": converters.docx_converter,
            ".pptx": converters.pptx_converter,
            # Mistral OCR - Images
            ".jpg": converters.mistral_converter,
            ".jpeg": converters.mistral_converter,
            ".png": converters.mistral_converter,
            # XLSX - local extraction
            ".xlsx": converters.xlsx_converter,
            # HTML
            ".html": converters.html_converter,
            ".htm": converters.html_converter,
            # Text files
            ".txt": converters.txt_converter,
            ".json": converters.txt_converter,
            ".xml": converters.txt_converter,
            ".md": converters.txt_converter,
            ".yaml": converters.txt_converter,
            ".yml": converters.txt_converter,
            ".toml": converters.txt_converter,
            # Code file extensions
            ".py": converters.code_converter,
            ".js": converters.code_converter,
            ".ts": converters.code_converter,
            ".tsx": converters.code_converter,
            ".jsx": converters.code_converter,
            ".java": converters.code_converter,
            ".cpp": converters.code_converter,
            ".c": converters.code_converter,
            ".h": converters.code_converter,
            ".hpp": converters.code_converter,
            ".go": converters.code_converter,
            ".rs": converters.code_converter,
            ".rb": converters.code_converter,
            ".php": converters.code_converter,
            ".swift": converters.code_converter,
            ".kt": converters.code_converter,
            ".kts": converters.code_converter,
            ".tf": converters.code_converter,
            ".tfvars": converters.code_converter,
        }

        converter = converter_map.get(ext)
        if not converter:
            raise EntityProcessingError(f"Unsupported file type: {ext}")

        return converter

    # ------------------------------------------------------------------------------------
    # Conversion Execution
    # ------------------------------------------------------------------------------------

    async def _convert_partitions(
        self,
        converter_groups: Dict[Any, List[Tuple[BaseEntity, str]]],
        sync_context: "SyncContext",
    ) -> List[BaseEntity]:
        """Execute batch conversion for each converter group.

        Args:
            converter_groups: Dict mapping converter to (entity, key) tuples
            sync_context: Sync context for logging

        Returns:
            List of entities that failed conversion
        """
        failed_entities = []

        for converter, entity_key_pairs in converter_groups.items():
            batch_size = getattr(converter, "BATCH_SIZE", self.DEFAULT_CONVERTER_BATCH_SIZE)

            for i in range(0, len(entity_key_pairs), batch_size):
                sub_batch = entity_key_pairs[i : i + batch_size]
                failures = await self._convert_sub_batch(converter, sub_batch, sync_context)
                failed_entities.extend(failures)

        return failed_entities

    async def _convert_sub_batch(
        self,
        converter: Any,
        sub_batch: List[Tuple[BaseEntity, str]],
        sync_context: "SyncContext",
    ) -> List[BaseEntity]:
        """Convert a sub-batch of entities using the given converter.

        Args:
            converter: Converter module to use
            sub_batch: List of (entity, key) tuples
            sync_context: Sync context for logging

        Returns:
            List of entities that failed conversion
        """
        failed_entities = []
        keys = [key for _, key in sub_batch]

        try:
            # Batch convert returns Dict[key, text_content]
            results = await converter.convert_batch(keys)

            # Append content to each entity
            for entity, key in sub_batch:
                text_content = results.get(key)

                if not text_content:
                    sync_context.logger.warning(
                        f"Conversion returned no content for "
                        f"{entity.__class__.__name__}[{entity.entity_id}] "
                        f"at {key} - entity will be skipped"
                    )
                    failed_entities.append(entity)
                    continue

                entity.textual_representation += f"\n\n# Content\n\n{text_content}"

        except SyncFailureError:
            # Infrastructure failure - propagate to fail entire sync
            raise
        except EntityProcessingError as e:
            # Recoverable converter issue - skip sub-batch
            converter_name = converter.__class__.__name__
            sync_context.logger.warning(
                f"Batch conversion skipped for {converter_name} sub-batch: {e}"
            )
            failed_entities.extend([entity for entity, _ in sub_batch])
        except Exception as e:
            # Unexpected errors - mark sub-batch as failed but continue
            converter_name = converter.__class__.__name__
            sync_context.logger.error(
                f"Batch conversion failed for {converter_name} sub-batch: {e}",
                exc_info=True,
            )
            failed_entities.extend([entity for entity, _ in sub_batch])

        return failed_entities

    # ------------------------------------------------------------------------------------
    # Failure Handling
    # ------------------------------------------------------------------------------------

    async def _handle_conversion_failures(
        self,
        entities: List[BaseEntity],
        failed_entities: List[BaseEntity],
        sync_context: "SyncContext",
        runtime: "SyncRuntime",
    ) -> None:
        """Remove failed entities and update progress.

        Args:
            entities: Original entity list (modified in-place)
            failed_entities: Entities that failed conversion
            sync_context: Sync context for progress tracking
            runtime: Sync runtime with live services
        """
        if not failed_entities:
            return

        for entity in failed_entities:
            if entity in entities:
                entities.remove(entity)

        await runtime.entity_tracker.record_skipped(len(failed_entities))
        sync_context.logger.warning(
            f"Removed {len(failed_entities)} entities that failed conversion"
        )


# Singleton instance
text_builder = TextualRepresentationBuilder()
