"""Elasticsearch entity schemas."""

from typing import Any, Dict, Optional

from pydantic import ConfigDict, Field

from airweave.platform.entities._base import ChunkEntity


class ElasticsearchIndexEntity(ChunkEntity):
    """Schema for Elasticsearch index entities."""

    model_config = ConfigDict(extra="forbid")

    index: str = Field(..., description="Name of the Elasticsearch index")
    health: Optional[str] = Field(None, description="Health status of the index")
    status: Optional[str] = Field(None, description="Status of the index")
    docs_count: Optional[int] = Field(None, description="Number of documents in the index")
    docs_deleted: Optional[int] = Field(None, description="Number of deleted documents in index")
    store_size: Optional[str] = Field(None, description="Store size of the index")


class ElasticsearchDocumentEntity(ChunkEntity):
    """Schema for Elasticsearch document entities."""

    model_config = ConfigDict(extra="forbid")

    index: str = Field(..., description="Name of the index this document belongs to")
    doc_id: str = Field(..., description="Document ID")
    source: Dict[str, Any] = Field(..., description="Source document content")
