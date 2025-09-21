"""Airtable entity schemas (read-only)."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity


class AirtableBaseEntity(ChunkEntity):
    """Metadata for an Airtable base."""

    base_id: str = Field(..., description="Airtable base ID")
    name: Optional[str] = Field(None, description="Base name")
    permission_level: Optional[str] = Field(None, description="Permission level for this base")
    url: Optional[str] = Field(None, description="Convenience URL to open the base")
    content: Optional[str] = Field(None, description="Canonical text for search (name/description)")


class AirtableTableEntity(ChunkEntity):
    """Metadata for an Airtable table (schema-level info)."""

    table_id: str = Field(..., description="Airtable table ID")
    base_id: str = Field(..., description="Parent base ID")
    name: str = Field(..., description="Table name")
    description: Optional[str] = Field(None, description="Table description, if any")
    fields_schema: Optional[List[Dict[str, Any]]] = Field(
        default=None, description="List of field definitions from the schema API"
    )
    content: Optional[str] = Field(None, description="Canonical text for search (name/description)")


class AirtableRecordEntity(ChunkEntity):
    """One Airtable record (row) as a searchable chunk."""

    record_id: str = Field(..., description="Record ID")
    base_id: str = Field(..., description="Parent base ID")
    table_id: str = Field(..., description="Parent table ID")
    table_name: Optional[str] = Field(None, description="Parent table name")
    fields: Dict[str, Any] = Field(default_factory=dict, description="Raw Airtable fields map")
    created_time: Optional[datetime] = Field(None, description="Record createdTime")
    content: Optional[str] = Field(
        None,
        description="Canonical text synthesized from the record fields for search/embedding",
    )


class AirtableAttachmentEntity(FileEntity):
    """Attachment file from an Airtable record (downloaded via expiring URL)."""

    file_id: str = Field(..., description="Attachment ID (also entity_id)")
    name: str = Field(..., description="Attachment filename")
    mime_type: Optional[str] = Field(None, description="MIME type")
    size: Optional[int] = Field(None, description="Size in bytes")
    download_url: str = Field(..., description="Ephemeral download URL from Airtable attachment")
    base_id: str = Field(..., description="Base ID")
    table_id: str = Field(..., description="Table ID")
    table_name: Optional[str] = Field(None, description="Table name")
    record_id: str = Field(..., description="Record ID")
    field_name: str = Field(..., description="Field name that contains this attachment")
