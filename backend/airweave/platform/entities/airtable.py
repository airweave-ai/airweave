"""Airtable entity schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb, FileEntity


def _find_primary_field(fields: List[Dict[str, Any]]) -> Optional[str]:
    """Return the name of the primary field from a table's field definitions."""
    for field in fields:
        if field.get("type") == "primaryField" or field.get("isPrimary"):
            return field.get("name")
    return fields[0].get("name") if fields else None


def _extract_record_name(record_id: str, fields: Dict[str, Any]) -> str:
    """Pick a human-readable name from the first non-empty field value."""
    for value in fields.values():
        if isinstance(value, str) and value.strip():
            return value.strip()[:100]
        if value and not isinstance(value, (dict, list)):
            return str(value)[:100]
    return record_id


class AirtableUserEntity(BaseEntity):
    """The authenticated user (from /meta/whoami endpoint)."""

    user_id: str = AirweaveField(..., description="Airtable user ID", is_entity_id=True)
    display_name: str = AirweaveField(
        ..., description="Display name derived from email or ID", is_name=True, embeddable=True
    )

    email: Optional[str] = AirweaveField(None, description="User email address", embeddable=True)
    scopes: Optional[List[str]] = AirweaveField(
        default=None, description="OAuth scopes granted to the token", embeddable=False
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> AirtableUserEntity:
        """Construct from Airtable ``/meta/whoami`` response."""
        user_id = data.get("id", "unknown")
        email = data.get("email")
        return cls(
            user_id=user_id,
            display_name=email or user_id,
            breadcrumbs=[],
            email=email,
            scopes=data.get("scopes"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Account settings page for the authenticated user."""
        return "https://airtable.com/account"


class AirtableBaseEntity(BaseEntity):
    """Metadata for an Airtable base."""

    base_id: str = AirweaveField(..., description="Airtable base ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Base name", is_name=True, embeddable=True)

    permission_level: Optional[str] = AirweaveField(
        None, description="Permission level for this base", embeddable=False
    )
    url: Optional[str] = AirweaveField(
        None,
        description="URL to open the base in Airtable (legacy API field)",
        embeddable=False,
        unhashable=True,
    )

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> AirtableBaseEntity:
        """Construct from a base dict in the ``/meta/bases`` response."""
        base_id = data["id"]
        return cls(
            base_id=base_id,
            breadcrumbs=[],
            name=data.get("name", base_id),
            permission_level=data.get("permissionLevel"),
            url=f"https://airtable.com/{base_id}",
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Canonical link to open the base in Airtable."""
        return f"https://airtable.com/{self.base_id}"


class AirtableTableEntity(BaseEntity):
    """Metadata for an Airtable table (schema-level info)."""

    table_id: str = AirweaveField(..., description="Airtable table ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Table name", is_name=True, embeddable=True)

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

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        base_id: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AirtableTableEntity:
        """Construct from a table dict in the ``/meta/bases/{id}/tables`` response."""
        table_id = data["id"]
        fields = data.get("fields", [])
        return cls(
            table_id=table_id,
            breadcrumbs=list(breadcrumbs),
            name=data.get("name") or table_id,
            base_id=base_id,
            description=data.get("description"),
            fields_schema=fields,
            primary_field_name=_find_primary_field(fields),
            view_count=len(data.get("views", [])),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link back to the table inside the base."""
        return f"https://airtable.com/{self.base_id}/{self.table_id}"


class AirtableRecordEntity(BaseEntity):
    """One Airtable record (row) as a searchable chunk."""

    record_id: str = AirweaveField(..., description="Record ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Record display name", is_name=True, embeddable=True)
    created_at: Optional[datetime] = AirweaveField(
        None, description="Record creation time", is_created_at=True
    )

    base_id: str = AirweaveField(..., description="Parent base ID", embeddable=False)
    table_id: str = AirweaveField(..., description="Parent table ID", embeddable=False)
    table_name: Optional[str] = AirweaveField(
        None, description="Parent table name", embeddable=True
    )
    fields: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Raw Airtable fields map", embeddable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        base_id: str,
        table_id: str,
        table_name: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AirtableRecordEntity:
        """Construct from a record dict in the list-records response."""
        record_id = data["id"]
        fields = data.get("fields", {})
        return cls(
            record_id=record_id,
            breadcrumbs=list(breadcrumbs),
            name=_extract_record_name(record_id, fields),
            created_at=data.get("createdTime"),
            base_id=base_id,
            table_id=table_id,
            table_name=table_name,
            fields=fields,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Attempt to deep-link to the record inside its table."""
        return f"https://airtable.com/{self.base_id}/{self.table_id}/{self.record_id}"


class AirtableCommentEntity(BaseEntity):
    """A comment on an Airtable record."""

    comment_id: str = AirweaveField(..., description="Comment ID", is_entity_id=True)
    name: str = AirweaveField(..., description="Comment preview", is_name=True, embeddable=True)
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the comment was created", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the comment was last updated", is_updated_at=True
    )

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

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        record_id: str,
        base_id: str,
        table_id: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AirtableCommentEntity:
        """Construct from a comment dict in the list-comments response."""
        comment_id = data["id"]
        text = data.get("text", "")
        preview = text[:50] + "..." if len(text) > 50 else text
        author = data.get("author", {})
        return cls(
            comment_id=comment_id,
            breadcrumbs=list(breadcrumbs),
            name=preview or f"Comment {comment_id}",
            created_at=data.get("createdTime"),
            updated_at=data.get("lastUpdatedTime"),
            record_id=record_id,
            base_id=base_id,
            table_id=table_id,
            text=text,
            author_id=author.get("id"),
            author_email=author.get("email"),
            author_name=author.get("name"),
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the parent record where the comment resides."""
        return f"https://airtable.com/{self.base_id}/{self.table_id}/{self.record_id}"


class AirtableAttachmentEntity(FileEntity):
    """Attachment file from an Airtable record."""

    attachment_id: str = AirweaveField(
        ..., description="Attachment ID (or composite key)", is_entity_id=True
    )
    name: str = AirweaveField(..., description="Attachment filename", is_name=True, embeddable=True)

    base_id: str = AirweaveField(..., description="Base ID", embeddable=False)
    table_id: str = AirweaveField(..., description="Table ID", embeddable=False)
    table_name: Optional[str] = AirweaveField(None, description="Table name", embeddable=True)
    record_id: str = AirweaveField(..., description="Record ID", embeddable=False)
    field_name: str = AirweaveField(
        ..., description="Field name that contains this attachment", embeddable=True
    )

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        base_id: str,
        table_id: str,
        table_name: str,
        record_id: str,
        field_name: str,
        breadcrumbs: List[Breadcrumb],
    ) -> Optional[AirtableAttachmentEntity]:
        """Construct from an attachment dict. Returns None if no download URL."""
        url = data.get("url")
        if not url:
            return None

        att_id = data.get("id", f"{record_id}:{field_name}")
        filename = data.get("filename") or data.get("name") or "attachment"
        mime_type = data.get("type") or "application/octet-stream"
        file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

        return cls(
            attachment_id=att_id,
            breadcrumbs=list(breadcrumbs),
            name=filename,
            url=url,
            size=data.get("size", 0),
            file_type=file_type,
            mime_type=mime_type,
            local_path=None,
            base_id=base_id,
            table_id=table_id,
            table_name=table_name,
            record_id=record_id,
            field_name=field_name,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Link to the parent record containing this attachment."""
        return f"https://airtable.com/{self.base_id}/{self.table_id}/{self.record_id}"
