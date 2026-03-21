"""Notion entity schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from pydantic import computed_field

from airweave.core.datetime_utils import utc_now_naive
from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb, FileEntity

# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _extract_rich_text_plain(rich_text: List[dict]) -> str:
    """Extract plain text from Notion rich-text array."""
    if not rich_text or not isinstance(rich_text, list):
        return ""

    text_parts = []
    for text_obj in rich_text:
        if not text_obj or not isinstance(text_obj, dict):
            continue
        plain_text = text_obj.get("plain_text", "")
        if plain_text:
            text_parts.append(plain_text)

    return " ".join(text_parts)


def _parse_notion_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
    """Parse a Notion ISO-8601 datetime string into a naive UTC datetime."""
    if not datetime_str:
        return None
    try:
        if datetime_str.endswith("Z"):
            datetime_str = datetime_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, AttributeError):
        return None


def _extract_page_title(page: dict) -> str:
    """Extract the title from a Notion page object."""
    properties = page.get("properties", {})
    for _prop_name, prop_value in properties.items():
        if prop_value.get("type") == "title":
            title_content = prop_value.get("title", [])
            return _extract_rich_text_plain(title_content)
    return "Untitled"


def _format_database_schema(properties: dict) -> Dict[str, Any]:
    """Format database schema properties for better searchability."""
    formatted: Dict[str, Any] = {}
    for prop_name, prop_config in properties.items():
        prop_type = prop_config.get("type", "")
        prop_info: Dict[str, Any] = {
            "type": prop_type,
            "name": prop_config.get("name", prop_name),
        }
        if prop_type in ["select", "status"]:
            options = prop_config.get(prop_type, {}).get("options", [])
            prop_info["options"] = [opt.get("name", "") for opt in options if opt.get("name")]
        elif prop_type == "multi_select":
            options = prop_config.get("multi_select", {}).get("options", [])
            prop_info["options"] = [opt.get("name", "") for opt in options if opt.get("name")]
        elif prop_type == "number":
            format_type = prop_config.get("number", {}).get("format", "number")
            prop_info["format"] = format_type
        formatted[prop_name] = prop_info
    return formatted


_MIME_TYPE_MAP: Dict[str, str] = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "tiff": "image/tiff",
    "tif": "image/tiff",
    "ico": "image/vnd.microsoft.icon",
    "heic": "image/heic",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "avi": "video/x-msvideo",
    "mkv": "video/x-matroska",
    "wmv": "video/x-ms-wmv",
    "flv": "video/x-flv",
    "webm": "video/webm",
    "mpeg": "video/mpeg",
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "aac": "audio/aac",
    "ogg": "audio/ogg",
    "wma": "audio/x-ms-wma",
    "m4a": "audio/mp4",
    "m4b": "audio/mp4",
    "mid": "audio/midi",
    "midi": "audio/midi",
    "txt": "text/plain",
    "json": "application/json",
}


class NotionDatabaseEntity(BaseEntity):
    """Schema for a Notion database."""

    database_id: str = AirweaveField(..., description="The ID of the database.", is_entity_id=True)
    title: str = AirweaveField(
        ..., description="The title of the database", embeddable=True, is_name=True
    )
    created_time: Optional[datetime] = AirweaveField(
        None, description="When the database was created.", is_created_at=True
    )
    updated_time: Optional[datetime] = AirweaveField(
        None, description="When the database was last edited.", is_updated_at=True
    )
    description: str = AirweaveField(
        default="", description="The description of the database", embeddable=True
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Database properties schema", embeddable=False
    )
    properties_text: Optional[str] = AirweaveField(
        default=None, description="Human-readable schema description", embeddable=True
    )
    parent_id: str = AirweaveField(..., description="The ID of the parent", embeddable=False)
    parent_type: str = AirweaveField(
        ..., description="The type of the parent (workspace, page_id, etc.)", embeddable=False
    )
    icon: Optional[Dict[str, Any]] = AirweaveField(
        None, description="The icon of the database", embeddable=False
    )
    cover: Optional[Dict[str, Any]] = AirweaveField(
        None, description="The cover of the database", embeddable=False
    )
    archived: bool = AirweaveField(
        default=False, description="Whether the database is archived", embeddable=False
    )
    is_inline: bool = AirweaveField(
        default=False, description="Whether the database is inline", embeddable=False
    )
    url: str = AirweaveField(
        ..., description="The URL of the database", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the database."""
        return self.url or ""

    def model_post_init(self, __context) -> None:
        """Post-init hook to generate properties_text from schema."""
        super().model_post_init(__context)

        # Generate human-readable schema text if not already set
        if self.properties and not self.properties_text:
            self.properties_text = self._generate_schema_text()

    def _generate_schema_text(self) -> str:
        """Generate human-readable text from database schema for embedding.

        Creates a clean representation of the database structure.
        """
        if not self.properties:
            return ""

        text_parts = []

        for prop_name, prop_info in self.properties.items():
            if isinstance(prop_info, dict):
                prop_type = prop_info.get("type", "unknown")

                # Build property description
                desc_parts = [f"{prop_name} ({prop_type})"]

                # Add options if available
                if "options" in prop_info and prop_info["options"]:
                    options_str = ", ".join(prop_info["options"][:5])  # Limit to first 5
                    if len(prop_info["options"]) > 5:
                        options_str += f" +{len(prop_info['options']) - 5} more"
                    desc_parts.append(f"options: {options_str}")

                # Add format for numbers
                if "format" in prop_info:
                    desc_parts.append(f"format: {prop_info['format']}")

                text_parts.append(" ".join(desc_parts))

        return " | ".join(text_parts) if text_parts else ""

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        breadcrumbs: List[Breadcrumb],
    ) -> NotionDatabaseEntity:
        """Build from a Notion API database object."""
        database_id = data["id"]
        title = _extract_rich_text_plain(data.get("title", []))
        description = _extract_rich_text_plain(data.get("description", []))
        created_time = _parse_notion_datetime(data.get("created_time"))
        updated_time = _parse_notion_datetime(data.get("last_edited_time"))
        parent = data.get("parent", {})
        formatted_schema = _format_database_schema(data.get("properties", {}))

        return cls(
            entity_id=database_id,
            breadcrumbs=breadcrumbs,
            name=title or "Untitled Database",
            created_at=created_time,
            updated_at=updated_time,
            database_id=database_id,
            title=title or "Untitled Database",
            created_time=created_time,
            updated_time=updated_time,
            description=description,
            properties=formatted_schema,
            parent_id=parent.get("page_id", ""),
            parent_type=parent.get("type", "workspace"),
            icon=data.get("icon"),
            cover=data.get("cover"),
            archived=data.get("archived", False),
            is_inline=data.get("is_inline", False),
            url=data.get("url", ""),
        )


class NotionPageEntity(BaseEntity):
    """Schema for a Notion page with aggregated content."""

    page_id: str = AirweaveField(..., description="The ID of the page.", is_entity_id=True)
    parent_id: str = AirweaveField(..., description="The ID of the parent", embeddable=False)
    parent_type: str = AirweaveField(
        ...,
        description="The type of the parent (workspace, page_id, database_id, etc.)",
        embeddable=False,
    )
    title: str = AirweaveField(
        ..., description="The title of the page", embeddable=True, is_name=True
    )
    created_time: Optional[datetime] = AirweaveField(
        None, description="When the page was created.", is_created_at=True
    )
    updated_time: Optional[datetime] = AirweaveField(
        None, description="When the page was last edited.", is_updated_at=True
    )
    content: Optional[str] = AirweaveField(
        default=None, description="Full aggregated content", embeddable=True
    )
    properties: Dict[str, Any] = AirweaveField(
        default_factory=dict, description="Formatted page properties for search", embeddable=False
    )
    properties_text: Optional[str] = AirweaveField(
        default=None, description="Human-readable properties text", embeddable=True
    )
    property_entities: List[Any] = AirweaveField(
        default_factory=list, description="Structured property entities", embeddable=False
    )
    files: List[Any] = AirweaveField(
        default_factory=list, description="Files referenced in the page", embeddable=False
    )
    icon: Optional[Dict[str, Any]] = AirweaveField(
        None, description="The icon of the page", embeddable=False
    )
    cover: Optional[Dict[str, Any]] = AirweaveField(
        None, description="The cover of the page", embeddable=False
    )
    archived: bool = AirweaveField(
        default=False, description="Whether the page is archived", embeddable=False
    )
    in_trash: bool = AirweaveField(
        default=False, description="Whether the page is in trash", embeddable=False
    )
    url: str = AirweaveField(
        ..., description="The URL of the page", embeddable=False, unhashable=True
    )
    content_blocks_count: int = AirweaveField(
        default=0, description="Number of blocks processed", embeddable=False
    )
    max_depth: int = AirweaveField(
        default=0, description="Maximum nesting depth of blocks", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the page."""
        return self.url or ""

    # Lazy mechanics removed; eager-only entity

    def model_post_init(self, __context) -> None:
        """Post-init hook to generate properties_text from properties dict."""
        super().model_post_init(__context)

        # Generate human-readable properties text if not already set
        if self.properties and not self.properties_text:
            self.properties_text = self._generate_properties_text()

    def _generate_properties_text(self) -> str:
        """Generate human-readable text from properties for embedding.

        Creates a clean, searchable representation of property values.
        """
        if not self.properties:
            return ""

        text_parts = []

        # Process properties in a logical order
        priority_keys = [
            "Product Name",
            "Name",
            "Title",
            "Status",
            "Priority",
            "Launch Status",
            "Owner",
            "Team",
            "Description",
        ]

        # First add priority properties
        for key in priority_keys:
            if key in self.properties:
                value = self.properties[key]
                if value and str(value).strip():
                    # Skip if it's the same as the page title
                    if key in ["Product Name", "Name", "Title"] and value == self.title:
                        continue
                    text_parts.append(f"{key}: {value}")

        # Then add remaining properties
        for key, value in self.properties.items():
            if key not in priority_keys and not key.endswith("_options"):
                if value and str(value).strip():
                    # Format the key nicely
                    formatted_key = key.replace("_", " ").title()
                    text_parts.append(f"{formatted_key}: {value}")

        return " | ".join(text_parts) if text_parts else ""

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        breadcrumbs: List[Breadcrumb],
        content: Optional[str] = None,
        formatted_properties: Optional[Dict[str, Any]] = None,
        properties_text: Optional[str] = None,
        property_entities: Optional[List[Any]] = None,
        content_blocks_count: int = 0,
        max_depth: int = 0,
    ) -> NotionPageEntity:
        """Build from a Notion API page object.

        Async-computed fields (content, formatted_properties, properties_text,
        property_entities) are passed as kwargs because they require API calls
        that must happen in the source.
        """
        page_id = data["id"]
        title = _extract_page_title(data)
        created_time = _parse_notion_datetime(data.get("created_time"))
        updated_time = _parse_notion_datetime(data.get("last_edited_time"))
        parent = data.get("parent", {})

        return cls(
            entity_id=page_id,
            breadcrumbs=breadcrumbs,
            name=title,
            created_at=created_time,
            updated_at=updated_time,
            page_id=page_id,
            parent_id=parent.get("page_id") or parent.get("database_id") or "",
            parent_type=parent.get("type", "workspace"),
            title=title,
            created_time=created_time,
            updated_time=updated_time,
            content=content,
            properties=formatted_properties or {},
            properties_text=properties_text,
            property_entities=property_entities or [],
            files=[],
            icon=data.get("icon"),
            cover=data.get("cover"),
            archived=data.get("archived", False),
            in_trash=data.get("in_trash", False),
            url=data.get("url", ""),
            content_blocks_count=content_blocks_count,
            max_depth=max_depth,
        )


class NotionPropertyEntity(BaseEntity):
    """Schema for a Notion database page property."""

    # Base fields are inherited and set during entity creation:
    # - entity_id (property_id)
    # - breadcrumbs
    # - name (from property_name)
    # - created_at (None - properties don't have timestamps)
    # - updated_at (None - properties don't have timestamps)

    # API fields
    property_key: str = AirweaveField(
        ...,
        description="Stable unique identifier for the property entity.",
        embeddable=False,
        is_entity_id=True,
    )
    property_id: str = AirweaveField(..., description="The ID of the property", embeddable=False)
    property_name: str = AirweaveField(
        ..., description="The name of the property", embeddable=True, is_name=True
    )
    property_type: str = AirweaveField(..., description="The type of the property", embeddable=True)
    page_id: str = AirweaveField(
        ..., description="The ID of the page this property belongs to", embeddable=False
    )
    database_id: str = AirweaveField(
        ..., description="The ID of the database this property belongs to", embeddable=False
    )
    value: Optional[Any] = AirweaveField(
        None, description="The raw value of the property", embeddable=True
    )
    formatted_value: str = AirweaveField(
        default="", description="The formatted/display value of the property", embeddable=True
    )


class NotionFileEntity(FileEntity):
    """Schema for a Notion file.

    Reference:
        https://developers.notion.com/reference/file-object
    """

    # Base fields are inherited from BaseEntity:
    # - entity_id (file_id)
    # - breadcrumbs
    # - name
    # - created_at (None - Notion files don't have timestamps)
    # - updated_at (None - Notion files don't have timestamps)

    # File fields are inherited from FileEntity:
    # - url (download_url)
    # - size (None - not provided by Notion API in block content)
    # - file_type (e.g., "file", "external", "file_upload")
    # - mime_type
    # - local_path (set after download)

    # API fields (Notion-specific)
    file_id: str = AirweaveField(
        ..., description="ID of the file in Notion", embeddable=False, is_entity_id=True
    )
    file_name: str = AirweaveField(
        ..., description="Display name of the file", embeddable=True, is_name=True
    )
    expiry_time: Optional[datetime] = AirweaveField(
        None, description="When the file URL expires (for Notion-hosted files)", embeddable=False
    )
    caption: str = AirweaveField(default="", description="The caption of the file", embeddable=True)
    web_url_value: Optional[str] = AirweaveField(
        None, description="Link to view/download the file.", embeddable=False, unhashable=True
    )

    def needs_refresh(self) -> bool:
        """Check if the file URL needs to be refreshed (for Notion-hosted files)."""
        if self.file_type == "file" and self.expiry_time:
            return utc_now_naive() >= self.expiry_time
        return False

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        parent_id: str,
        breadcrumbs: List[Breadcrumb],
    ) -> NotionFileEntity:
        """Build from a Notion API file/image block-content object.

        Handles the three Notion file hosting variants: ``file`` (S3-hosted
        with expiry), ``file_upload`` (new upload API), and ``external``.
        """
        file_type_notion = data.get("type", "external")

        if file_type_notion == "file":
            file_data = data.get("file", {})
            url = file_data.get("url", "")
            expiry_time = _parse_notion_datetime(file_data.get("expiry_time"))
            file_id = url
            download_url = url
        elif file_type_notion == "file_upload":
            file_data = data.get("file_upload", {})
            file_id = file_data.get("id", "")
            download_url = f"https://api.notion.com/v1/files/{file_id}"
            url = download_url
            expiry_time = None
        else:
            file_data = data.get("external", {})
            url = file_data.get("url", "")
            file_id = url
            download_url = url
            expiry_time = None

        name = data.get("name", "")
        if not name and url:
            parsed_url = urlparse(url)
            name = parsed_url.path.split("/")[-1] if parsed_url.path else "Untitled File"

        caption = _extract_rich_text_plain(data.get("caption", []))
        display_name = name or "Untitled File"

        mime_type = None
        if name:
            ext = name.lower().split(".")[-1] if "." in name else ""
            mime_type = _MIME_TYPE_MAP.get(ext)

        general_file_type = mime_type.split("/")[0] if mime_type else "file"

        return cls(
            entity_id=f"file_{parent_id}_{hash(file_id)}",
            breadcrumbs=breadcrumbs,
            name=display_name,
            created_at=None,
            updated_at=None,
            url=download_url,
            size=0,
            file_type=general_file_type,
            mime_type=mime_type or "application/octet-stream",
            local_path=None,
            file_id=file_id,
            file_name=display_name,
            expiry_time=expiry_time,
            caption=caption,
            web_url_value=url,
        )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the file."""
        if self.web_url_value:
            return self.web_url_value
        return self.url
