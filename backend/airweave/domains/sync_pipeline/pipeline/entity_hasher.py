"""Stateless hash computation primitives for entity change detection.

Pure functions with no I/O and no side effects. Used by both
HashComputer (pipeline — adds file I/O, batching, side effects)
and SourceHashLookup (source — trial composite for download skip).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from airweave.core.shared_models import AirweaveFieldFlag
from airweave.platform.entities._base import BaseEntity, CodeFileEntity, FileEntity


def populate_derived_fields(entity: BaseEntity) -> None:
    """Copy flagged field values to entity_id, name, created_at, updated_at.

    Idempotent — skips fields that are already set. This must be called
    before hash computation to ensure the entity dict matches what the
    pipeline produces.
    """
    if not entity.entity_id:
        value = _get_flagged_field_value(entity, AirweaveFieldFlag.IS_ENTITY_ID)
        if value:
            entity.entity_id = str(value)

    if not entity.name:
        value = _get_flagged_field_value(entity, AirweaveFieldFlag.IS_NAME)
        if value:
            entity.name = str(value)

    if not entity.created_at:
        value = _get_flagged_field_value(entity, AirweaveFieldFlag.IS_CREATED_AT)
        if value is not None:
            entity.created_at = value

    if not entity.updated_at:
        value = _get_flagged_field_value(entity, AirweaveFieldFlag.IS_UPDATED_AT)
        if value is not None:
            entity.updated_at = value


def exclude_volatile_fields(entity: BaseEntity, entity_dict: dict) -> dict:
    """Remove volatile and unhashable fields from an entity dict."""
    excluded = {
        "airweave_system_metadata",
        "breadcrumbs",
        "local_path",
        "url",
    }

    for field_name, field_info in entity.__class__.model_fields.items():
        json_extra = field_info.json_schema_extra
        if json_extra and isinstance(json_extra, dict):
            flag_key = (
                AirweaveFieldFlag.UNHASHABLE.value
                if hasattr(AirweaveFieldFlag.UNHASHABLE, "value")
                else AirweaveFieldFlag.UNHASHABLE
            )
            if json_extra.get(flag_key):
                excluded.add(field_name)

    return {k: v for k, v in entity_dict.items() if k not in excluded}


def stable_serialize(obj: Any) -> Any:
    """Recursively normalize an object for deterministic JSON encoding."""
    if isinstance(obj, dict):
        return {k: stable_serialize(v) for k, v in sorted(obj.items())}
    elif isinstance(obj, (list, tuple)):
        return [stable_serialize(x) for x in obj]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)


def compute_dict_hash(content_dict: dict) -> str:
    """Stable JSON serialization of a dict → SHA256 hex digest."""
    data = stable_serialize(content_dict)
    json_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(json_str.encode()).hexdigest()


def compute_entity_hash(
    entity: BaseEntity,
    content_hash: Optional[str] = None,
) -> str:
    """Compute composite hash from entity fields + optional content_hash.

    Pure function: no I/O, no side effects. Populates derived fields
    (entity_id, name, etc.) from flagged source fields if not already
    set, then computes the same hash the pipeline would produce.

    Args:
        entity: Entity with source-time fields populated.
        content_hash: SHA256 of file bytes (for FileEntity/CodeFileEntity).
            Required for file entities; ignored for non-file entities.

    Returns:
        SHA256 hex digest of the composite hash.
    """
    populate_derived_fields(entity)

    entity_dict = entity.model_dump(mode="python", exclude_none=True)

    if isinstance(entity, (FileEntity, CodeFileEntity)) and content_hash is not None:
        entity_dict["_content_hash"] = content_hash

    content_dict = exclude_volatile_fields(entity, entity_dict)
    return compute_dict_hash(content_dict)


def _get_flagged_field_value(entity: BaseEntity, flag: AirweaveFieldFlag) -> Any:
    """Extract the value of the field marked with the given flag."""
    flag_key = flag.value if hasattr(flag, "value") else flag

    for field_name, field_info in entity.__class__.model_fields.items():
        json_extra = field_info.json_schema_extra
        if json_extra and isinstance(json_extra, dict):
            if json_extra.get(flag_key):
                return getattr(entity, field_name, None)

    return None
