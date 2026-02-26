"""Entity transformer - converts Airweave entities to Vespa documents.

Pure transformation logic with no I/O dependencies.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional
from uuid import UUID

from airweave.core.logging import ContextualLogger
from airweave.core.logging import logger as default_logger
from airweave.platform.destinations.vespa.types import VespaDocument
from airweave.platform.entities._base import (
    AirweaveSystemMetadata,
    BaseEntity,
    CodeFileEntity,
    EmailEntity,
    FileEntity,
    WebEntity,
)


def _sanitize_for_vespa(text: str) -> str:
    """Sanitize text for Vespa by removing illegal characters.

    Vespa strictly rejects:
    1. Control characters (code points < 32) except \n (0x0A), \r (0x0D), \t (0x09)
    2. Unicode noncharacters (U+FDD0..U+FDEF, U+FFFE, U+FFFF, and plane pairs)

    Common culprits:
    - Control: 0x00 (null), 0x01 (SOH), 0x0B (vertical tab)
    - Nonchars: 0xFDDC, 0xFFFE, 0xFFFF

    Args:
        text: Raw text that may contain illegal characters

    Returns:
        Sanitized text safe for Vespa
    """
    if not text:
        return text

    # Remove ASCII control characters (except \n, \r, \t) and Unicode noncharacters
    # U+FDD0..U+FDEF: 32 noncharacters
    # U+FFFE, U+FFFF and pairs in all planes (U+1FFFE, U+1FFFF, ..., U+10FFFE, U+10FFFF)
    return re.sub(
        r"[\x00-\x08\x0B\x0C\x0E-\x1F\uFDD0-\uFDEF\uFFFE\uFFFF]|"
        r"[\U0001FFFE\U0001FFFF\U0002FFFE\U0002FFFF\U0003FFFE\U0003FFFF"
        r"\U0004FFFE\U0004FFFF\U0005FFFE\U0005FFFF\U0006FFFE\U0006FFFF"
        r"\U0007FFFE\U0007FFFF\U0008FFFE\U0008FFFF\U0009FFFE\U0009FFFF"
        r"\U000AFFFE\U000AFFFF\U000BFFFE\U000BFFFF\U000CFFFE\U000CFFFF"
        r"\U000DFFFE\U000DFFFF\U000EFFFE\U000EFFFF\U000FFFFE\U000FFFFF"
        r"\U0010FFFE\U0010FFFF]",
        "",
        text,
    )


def _validate_text_quality(text: str, entity_id: str) -> Optional[str]:
    """Validate text doesn't contain excessive Unicode replacement characters.

    Vespa rejects text with >25% replacement chars or >5000 total. Detect this
    earlier to provide better error messages.

    Args:
        text: Text to validate
        entity_id: Entity ID for error messages

    Returns:
        Error message if validation fails, None if OK

    Raises:
        ValueError: If text contains excessive replacement characters
    """
    if not text:
        return None

    # Count Unicode replacement characters (U+FFFD)
    replacement_count = text.count("\ufffd")

    if replacement_count == 0:
        return None

    text_length = len(text)
    replacement_ratio = replacement_count / text_length if text_length > 0 else 0

    # Vespa thresholds: max 5000 chars OR 25% ratio
    MAX_REPLACEMENT_CHARS = 5000
    MAX_REPLACEMENT_RATIO = 0.25

    if replacement_count > MAX_REPLACEMENT_CHARS or replacement_ratio > MAX_REPLACEMENT_RATIO:
        return (
            f"Text contains {replacement_count} Unicode replacement characters "
            f"({replacement_ratio:.1%} of {text_length} chars). This indicates "
            f"corrupted or binary data incorrectly processed as text. "
            f"File may have encoding issues or be a binary file misidentified as text."
        )

    return None


def _get_system_metadata_fields() -> set[str]:
    """Get system metadata fields from AirweaveSystemMetadata class.

    Derives the field set dynamically from AirweaveSystemMetadata.model_fields,
    ensuring this stays in sync with the entity definitions (single source of truth).
    """
    fields = set(AirweaveSystemMetadata.model_fields.keys())
    fields.add("airweave_system_metadata")
    fields.add("collection_id")
    return fields


def _get_schema_fields_for_entity(entity: BaseEntity) -> set[str]:
    """Get all fields that have Vespa schema columns (not payload) for an entity.

    This derives the field list dynamically from the entity class hierarchy,
    making the entity class definitions the single source of truth.
    """
    fields = set(BaseEntity.model_fields.keys())
    fields |= _get_system_metadata_fields()

    if isinstance(entity, WebEntity):
        fields |= set(WebEntity.model_fields.keys()) - set(BaseEntity.model_fields.keys())
    if isinstance(entity, FileEntity):
        fields |= set(FileEntity.model_fields.keys()) - set(BaseEntity.model_fields.keys())
    if isinstance(entity, CodeFileEntity):
        fields |= set(CodeFileEntity.model_fields.keys()) - set(FileEntity.model_fields.keys())

    return fields


class EntityTransformer:
    """Transforms BaseEntity objects to VespaDocument format.

    This class encapsulates all the logic for converting Airweave's internal
    entity representation to Vespa's document format. It handles:

    - Base field extraction (entity_id, name, timestamps, etc.)
    - System metadata flattening (airweave_system_metadata_* prefix)
    - Type-specific fields (WebEntity, FileEntity, CodeFileEntity)
    - Access control fields (is_public, viewers)
    - Embedding fields (dense_embedding tensor)
    - Payload field (extra fields as JSON)
    """

    def __init__(
        self,
        collection_id: Optional[UUID] = None,
        logger: Optional[ContextualLogger] = None,
    ):
        """Initialize the entity transformer.

        Args:
            collection_id: SQL collection UUID for multi-tenant filtering
            logger: Optional logger for debug/warning messages
        """
        self.collection_id = collection_id
        self._logger = logger or default_logger

    def transform(self, entity: BaseEntity) -> VespaDocument:
        """Transform a single entity to Vespa document format.

        Args:
            entity: The entity to transform

        Returns:
            VespaDocument with schema, id, and fields
        """
        entity_type = self._get_entity_type(entity)
        schema = self._get_vespa_schema(entity)
        doc_id = f"{entity_type}_{entity.entity_id}"

        # Build fields from various sources
        fields = self._build_base_fields(entity)
        self._add_system_metadata_fields(fields, entity, entity_type)
        self._add_type_specific_fields(fields, entity)
        self._add_access_control_fields(fields, entity)
        self._add_embedding_fields(fields, entity)
        self._add_payload_field(fields, entity)

        # Remove None values from top-level fields
        fields = {k: v for k, v in fields.items() if v is not None}

        return VespaDocument(schema=schema, id=doc_id, fields=fields)

    def transform_batch(self, entities: List[BaseEntity]) -> Dict[str, List[VespaDocument]]:
        """Transform entities and group by Vespa schema.

        Args:
            entities: List of entities to transform

        Returns:
            Dict mapping schema name to list of VespaDocuments
        """
        docs_by_schema: Dict[str, List[VespaDocument]] = defaultdict(list)

        for entity in entities:
            try:
                doc = self.transform(entity)
                docs_by_schema[doc.schema_name].append(doc)

                # Debug logging
                has_dense = "dense_embedding" in doc.fields
                self._logger.debug(
                    f"[EntityTransformer] Transformed {entity.entity_id} → "
                    f"has_dense_emb={has_dense}"
                )
            except Exception as e:
                self._logger.error(f"Failed to transform entity {entity.entity_id}: {e}")

        return dict(docs_by_schema)

    def _get_entity_type(self, entity: BaseEntity) -> str:
        """Get entity type from metadata or class name."""
        if entity.airweave_system_metadata and entity.airweave_system_metadata.entity_type:
            return entity.airweave_system_metadata.entity_type
        return entity.__class__.__name__

    def _get_vespa_schema(self, entity: BaseEntity) -> str:
        """Determine the Vespa schema name for an entity."""
        if isinstance(entity, CodeFileEntity):
            return "code_file_entity"
        elif isinstance(entity, EmailEntity):
            return "email_entity"
        elif isinstance(entity, FileEntity):
            return "file_entity"
        elif isinstance(entity, WebEntity):
            return "web_entity"
        else:
            return "base_entity"

    def _build_base_fields(self, entity: BaseEntity) -> Dict[str, Any]:
        """Build base fields dict from entity."""
        fields: Dict[str, Any] = {
            "entity_id": entity.entity_id,
            "name": entity.name,
        }
        if entity.breadcrumbs:
            fields["breadcrumbs"] = [b.model_dump() for b in entity.breadcrumbs]
        if entity.created_at:
            fields["created_at"] = int(entity.created_at.timestamp())
        if entity.updated_at:
            fields["updated_at"] = int(entity.updated_at.timestamp())
        if entity.textual_representation:
            # Validate text quality before sanitization
            validation_error = _validate_text_quality(
                entity.textual_representation, entity.entity_id
            )
            if validation_error:
                self._logger.error(
                    f"[VespaTransformer] Text quality validation failed for "
                    f"{entity.entity_id} ({entity.name}): {validation_error}"
                )
                raise ValueError(validation_error)

            # Sanitize text to remove control characters that Vespa rejects
            sanitized = _sanitize_for_vespa(entity.textual_representation)

            # Log if we removed control characters
            if len(sanitized) != len(entity.textual_representation):
                removed = len(entity.textual_representation) - len(sanitized)
                self._logger.debug(
                    f"[VespaTransformer] Removed {removed} control characters from "
                    f"{entity.entity_id} (type: {entity.__class__.__name__})"
                )

            fields["textual_representation"] = sanitized
        return fields

    def _add_system_metadata_fields(
        self, fields: Dict[str, Any], entity: BaseEntity, entity_type: str
    ) -> None:
        """Add flattened system metadata fields with airweave_system_metadata_ prefix."""
        meta_fields = self._build_system_metadata(entity)

        if self.collection_id:
            meta_fields["collection_id"] = str(self.collection_id)

        meta_fields.setdefault("entity_type", entity_type)
        if "original_entity_id" not in meta_fields and entity.entity_id:
            meta_fields["original_entity_id"] = entity.entity_id

        for key, value in meta_fields.items():
            if value is not None:
                fields[f"airweave_system_metadata_{key}"] = value

    def _build_system_metadata(self, entity: BaseEntity) -> Dict[str, Any]:
        """Extract system metadata from entity."""
        meta_fields: Dict[str, Any] = {}
        meta = entity.airweave_system_metadata
        if not meta:
            return meta_fields

        attr_mappings = [
            ("entity_type", "entity_type", None),
            ("sync_id", "sync_id", str),
            ("sync_job_id", "sync_job_id", str),
            ("hash", "hash", None),
            ("original_entity_id", "original_entity_id", None),
            ("source_name", "source_name", None),
            ("chunk_index", "chunk_index", None),
        ]

        for attr, field_name, transform in attr_mappings:
            value = getattr(meta, attr, None)
            if value is not None:
                meta_fields[field_name] = transform(value) if transform else value

        return meta_fields

    def _add_type_specific_fields(self, fields: Dict[str, Any], entity: BaseEntity) -> None:
        """Add fields specific to entity subtype (WebEntity, FileEntity, etc.)."""
        if isinstance(entity, WebEntity):
            fields["crawl_url"] = entity.crawl_url
        elif isinstance(entity, CodeFileEntity):
            fields["repo_name"] = entity.repo_name
            fields["path_in_repo"] = entity.path_in_repo
            fields["repo_owner"] = entity.repo_owner
            fields["language"] = entity.language
            fields["commit_id"] = entity.commit_id
        elif isinstance(entity, FileEntity):
            fields["url"] = entity.url
            fields["size"] = entity.size
            fields["file_type"] = entity.file_type
            if entity.mime_type:
                fields["mime_type"] = entity.mime_type
            if entity.local_path:
                fields["local_path"] = entity.local_path

    def _add_access_control_fields(self, fields: Dict[str, Any], entity: BaseEntity) -> None:
        """Add access control fields.

        Always sets access control fields with appropriate defaults:
        - AC-enabled sources: Use the actual ACL values from entity.access
        - Non-AC sources: Set is_public=True so entities are visible to everyone
        """
        access = getattr(entity, "access", None)
        if access is not None:
            fields["access_is_public"] = access.is_public
            fields["access_viewers"] = access.viewers if access.viewers else []
        else:
            fields["access_is_public"] = True
            fields["access_viewers"] = []

    def _add_embedding_fields(self, fields: Dict[str, Any], entity: BaseEntity) -> None:
        """Add pre-computed embeddings from airweave_system_metadata.

        ChunkEmbedProcessor populates each chunk entity with:
        - airweave_system_metadata.dense_embedding: 3072-dim float32 embedding
        - airweave_system_metadata.sparse_embedding: FastEmbed BM25 sparse vector

        Vespa auto-converts float32 to bfloat16 for dense embedding storage.
        """
        meta = entity.airweave_system_metadata
        if meta is None:
            self._logger.warning(
                f"[EntityTransformer] Entity {entity.entity_id} has NO system metadata!"
            )
            return

        # Dense embedding (3072-dim for neural search)
        dense_emb = meta.dense_embedding
        if dense_emb is not None and isinstance(dense_emb, list) and len(dense_emb) > 0:
            fields["dense_embedding"] = {"values": dense_emb}
            self._logger.debug(
                f"[EntityTransformer] Added dense_embedding with {len(dense_emb)} dims"
            )
        else:
            self._logger.warning(
                f"[EntityTransformer] Entity {entity.entity_id}: No valid dense_embedding"
            )

        # Sparse embedding (FastEmbed BM25 for keyword scoring)
        sparse_emb = meta.sparse_embedding
        if sparse_emb is not None:
            sparse_tensor = self._convert_sparse_to_vespa_tensor(sparse_emb, entity.entity_id)
            if sparse_tensor:
                fields["sparse_embedding"] = sparse_tensor
                self._logger.debug(
                    f"[EntityTransformer] Added sparse_embedding with "
                    f"{len(sparse_tensor.get('cells', []))} tokens"
                )
        else:
            self._logger.warning(
                f"[EntityTransformer] Entity {entity.entity_id}: No sparse_embedding"
            )

    def _convert_sparse_to_vespa_tensor(
        self, sparse_emb: Any, entity_id: str
    ) -> Optional[Dict[str, Any]]:
        """Convert FastEmbed SparseEmbedding to Vespa mapped tensor format.

        FastEmbed SparseEmbedding has:
        - indices: numpy.ndarray[int] - token IDs
        - values: numpy.ndarray[float] - token weights

        Vespa mapped tensor format:
        - {"cells": [{"address": {"token": "123"}, "value": 0.5}, ...]}

        We use token IDs as strings since we don't need actual token text.
        This works because Vespa just needs consistent keys for matching.
        """
        try:
            # Get indices and values from sparse embedding
            if hasattr(sparse_emb, "indices") and hasattr(sparse_emb, "values"):
                indices = sparse_emb.indices
                values = sparse_emb.values
            elif isinstance(sparse_emb, dict):
                indices = sparse_emb.get("indices", [])
                values = sparse_emb.get("values", [])
            else:
                self._logger.warning(
                    f"[EntityTransformer] Entity {entity_id}: Unknown sparse embedding format"
                )
                return None

            # Convert numpy arrays to Python lists (FastEmbed returns numpy arrays)
            if hasattr(indices, "tolist"):
                indices = indices.tolist()
            if hasattr(values, "tolist"):
                values = values.tolist()

            # Check for empty after conversion
            if not indices or not values:
                return None

            # Convert to Vespa cells format
            cells = []
            for idx, val in zip(indices, values, strict=False):
                cells.append({"address": {"token": str(idx)}, "value": float(val)})

            return {"cells": cells}

        except Exception as e:
            self._logger.warning(
                f"[EntityTransformer] Failed to convert sparse embedding for {entity_id}: {e}"
            )
            return None

    def _add_payload_field(self, fields: Dict[str, Any], entity: BaseEntity) -> None:
        """Extract extra fields into payload JSON."""
        schema_fields = _get_schema_fields_for_entity(entity)
        # Exclude airweave_system_metadata from dump to avoid serializing numpy arrays
        # (sparse_embedding contains FastEmbed SparseEmbedding with numpy arrays)
        entity_dict = entity.model_dump(mode="json", exclude={"airweave_system_metadata"})
        payload = {k: v for k, v in entity_dict.items() if k not in schema_fields}
        if payload:
            fields["payload"] = json.dumps(payload)
