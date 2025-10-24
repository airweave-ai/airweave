"""Airtable entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base_legacy import ChunkEntity, FileEntity


class AirtableUserEntity(ChunkEntity):
    """The authenticated user (from /meta/whoami endpoint)."""

    user_id: str = Field(..., description="Airtable user ID")
    email: Optional[str] = AirweaveField(None, description="User email address", embeddable=True)
    scopes: Optional[List[str]] = AirweaveField(
        default=None, description="OAuth scopes granted to the token", embeddable=True
    )


class AirtableBaseEntity(ChunkEntity):
    """Metadata for an Airtable base."""

    base_id: str = Field(..., description="Airtable base ID (e.g., appXXXXXXX)")
    name: str = AirweaveField(..., description="Base name", embeddable=True)
    permission_level: Optional[str] = AirweaveField(
        None, description="Permission level for this base", embeddable=True
    )
    url: Optional[str] = Field(None, description="URL to open the base in Airtable")


class AirtableTableEntity(ChunkEntity):
    """Metadata for an Airtable table (schema-level info)."""

    table_id: str = Field(..., description="Airtable table ID (e.g., tblXXXXXXX)")
    base_id: str = Field(..., description="Parent base ID")
    name: str = AirweaveField(..., description="Table name", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="Table description, if any", embeddable=True
    )
    fields_schema: Optional[List[Dict[str, Any]]] = AirweaveField(
        default=None, description="List of field definitions from the schema API", embeddable=True
    )
    primary_field_name: Optional[str] = AirweaveField(
        None, description="Name of the primary field", embeddable=True
    )
    view_count: Optional[int] = Field(None, description="Number of views in this table")


class AirtableRecordEntity(ChunkEntity):
    """One Airtable record (row) as a searchable chunk."""

    record_id: str = Field(..., description="Record ID")
    base_id: str = Field(..., description="Parent base ID")
    table_id: str = Field(..., description="Parent table ID")
    table_name: Optional[str] = AirweaveField(
        None, description="Parent table name", embeddable=True
    )
    fields: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Raw Airtable fields map", embeddable=True
    )
    created_time: Optional[datetime] = AirweaveField(
        None,
        description="Record creation timestamp",
        embeddable=True,
        is_created_at=True,
    )


class AirtableCommentEntity(ChunkEntity):
    """A comment on an Airtable record."""

    comment_id: str = Field(..., description="Comment ID")
    record_id: str = Field(..., description="Parent record ID")
    base_id: str = Field(..., description="Parent base ID")
    table_id: str = Field(..., description="Parent table ID")
    text: str = AirweaveField(..., description="Comment text", embeddable=True)
    author_id: Optional[str] = Field(None, description="Author user ID")
    author_email: Optional[str] = AirweaveField(
        None, description="Author email address", embeddable=True
    )
    author_name: Optional[str] = AirweaveField(
        None, description="Author display name", embeddable=True
    )
    created_time: Optional[datetime] = AirweaveField(
        None,
        description="Comment creation timestamp",
        embeddable=True,
        is_created_at=True,
    )
    last_updated_time: Optional[datetime] = AirweaveField(
        None,
        description="Comment last updated timestamp",
        embeddable=True,
        is_updated_at=True,
    )


class AirtableAttachmentEntity(FileEntity):
    """Attachment file from an Airtable record."""

    base_id: str = Field(..., description="Base ID")
    table_id: str = Field(..., description="Table ID")
    table_name: Optional[str] = AirweaveField(None, description="Table name", embeddable=True)
    record_id: str = Field(..., description="Record ID")
    field_name: str = AirweaveField(
        ..., description="Field name that contains this attachment", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="Attachment creation timestamp",
        embeddable=True,
        is_created_at=True,
    )
