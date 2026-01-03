"""ARF (Airweave Raw Format) schemas.

Pydantic models for ARF data structures.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class SyncManifest(BaseModel):
    """Manifest for a sync's ARF data store.

    Stored at: raw/{sync_id}/manifest.json
    """

    sync_id: str
    source_short_name: str
    collection_id: str
    collection_readable_id: str
    organization_id: str
    created_at: str
    updated_at: str
    entity_count: int = 0
    file_count: int = 0
    # Track sync jobs that have written to this store
    sync_jobs: List[str] = Field(default_factory=list)
    # Optional config reference
    vector_size: Optional[int] = None
    embedding_model_name: Optional[str] = None
