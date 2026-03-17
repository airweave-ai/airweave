"""ARF (Airweave Raw Format) value types.

Defines the manifest schema and serialization metadata used for
entity capture and replay.
"""

from dataclasses import dataclass
from typing import List, Optional

from pydantic import BaseModel, Field


class SyncManifest(BaseModel):
    """Manifest for a sync's ARF data store.

    Stored at: raw/{sync_id}/manifest.json

    Entity and file counts are computed on-demand via get_entity_count()
    to avoid inconsistencies from incremental updates.
    """

    sync_id: str
    source_short_name: str
    collection_id: str
    collection_readable_id: str
    organization_id: str
    created_at: str
    updated_at: str
    sync_jobs: List[str] = Field(default_factory=list)
    vector_size: Optional[int] = None
    embedding_model_name: Optional[str] = None


@dataclass(frozen=True, slots=True)
class EntitySerializationMeta:
    """Metadata attached to each serialized entity for reconstruction."""

    entity_class: str
    entity_module: str
    captured_at: str
    stored_file: Optional[str] = None
