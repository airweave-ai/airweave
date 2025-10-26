"""Airtable entity schemas."""

from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


class AirtableUserEntity(BaseEntity):
    """The authenticated user (from /meta/whoami endpoint)."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (the user ID)
    # - breadcrumbs (empty - user is top-level)
    # - name (from email or user ID)
    # - created_at (None - user doesn't have creation timestamp)
    # - updated_at (None - user doesn't have update timestamp)

    # API fields
    email: Optional[str] = AirweaveField(None, description="User email address", embeddable=True)
    scopes: Optional[List[str]] = AirweaveField(
        default=None, description="OAuth scopes granted to the token", embeddable=False
    )


class AirtableBaseEntity(BaseEntity):
    """Metadata for an Airtable base."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (the base ID)
    # - breadcrumbs (empty - bases are top-level)
    # - name (from base name)
    # - created_at (None - bases don't have creation timestamp in API)
    # - updated_at (None - bases don't have update timestamp in API)

    # API fields
    permission_level: Optional[str] = AirweaveField(
        None, description="Permission level for this base", embeddable=False
    )
    url: Optional[str] = AirweaveField(
        None, description="URL to open the base in Airtable", embeddable=False
    )


class AirtableTableEntity(BaseEntity):
    """Metadata for an Airtable table (schema-level info)."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (the table ID)
    # - breadcrumbs (base breadcrumb)
    # - name (from table name)
    # - created_at (None - tables don't have creation timestamp in API)
    # - updated_at (None - tables don't have update timestamp in API)

    # API fields
    base_id: str = AirweaveField(..., description="Parent base ID", embeddable=False)
    description: Optional[str] = AirweaveField(
        None, description="Table description, if any", embeddable=True
    )
    fields_schema: Optional[List[Dict[str, Any]]] = AirweaveField(
        default=None, description="List of field definitions from the schema API", embeddable=True
    )
    primary_field_name: Optional[str] = AirweaveField(
        None, description="Name of the primary field", embeddable=True
    )
    view_count: Optional[int] = AirweaveField(
        None, description="Number of views in this table", embeddable=False
    )


class AirtableRecordEntity(BaseEntity):
    """One Airtable record (row) as a searchable chunk."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (the record ID)
    # - breadcrumbs (base and table breadcrumbs)
    # - name (from primary field or record ID)
    # - created_at (from created_time)
    # - updated_at (None - records don't have update timestamp in API)

    # API fields
    base_id: str = AirweaveField(..., description="Parent base ID", embeddable=False)
    table_id: str = AirweaveField(..., description="Parent table ID", embeddable=False)
    table_name: Optional[str] = AirweaveField(
        None, description="Parent table name", embeddable=True
    )
    fields: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Raw Airtable fields map", embeddable=True
    )


class AirtableCommentEntity(BaseEntity):
    """A comment on an Airtable record."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (the comment ID)
    # - breadcrumbs (base, table, and record breadcrumbs)
    # - name (comment preview or comment ID)
    # - created_at (from created_time)
    # - updated_at (from last_updated_time)

    # API fields
    record_id: str = AirweaveField(..., description="Parent record ID", embeddable=False)
    base_id: str = AirweaveField(..., description="Parent base ID", embeddable=False)
    table_id: str = AirweaveField(..., description="Parent table ID", embeddable=False)
    text: str = AirweaveField(..., description="Comment text", embeddable=True)
    author_id: Optional[str] = AirweaveField(None, description="Author user ID", embeddable=False)
    author_email: Optional[str] = AirweaveField(
        None, description="Author email address", embeddable=True
    )
    author_name: Optional[str] = AirweaveField(
        None, description="Author display name", embeddable=True
    )


class AirtableAttachmentEntity(FileEntity):
    """Attachment file from an Airtable record.

    Reference:
        https://airtable.com/developers/web/api/field-model#multipleattachment
    """

    # Base fields are inherited from BaseEntity:
    # - entity_id (attachment ID or composite key)
    # - breadcrumbs (base, table, and record breadcrumbs)
    # - name (filename)
    # - created_at (None - attachments don't have timestamps in API)
    # - updated_at (None - attachments don't have timestamps in API)

    # File fields are inherited from FileEntity:
    # - url (attachment URL)
    # - size (file size in bytes)
    # - file_type (determined from mime_type)
    # - mime_type
    # - local_path (set after download)

    # API fields (Airtable-specific)
    base_id: str = AirweaveField(..., description="Base ID", embeddable=False)
    table_id: str = AirweaveField(..., description="Table ID", embeddable=False)
    table_name: Optional[str] = AirweaveField(None, description="Table name", embeddable=True)
    record_id: str = AirweaveField(..., description="Record ID", embeddable=False)
    field_name: str = AirweaveField(
        ..., description="Field name that contains this attachment", embeddable=True
    )
