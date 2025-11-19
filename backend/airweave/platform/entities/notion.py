"""Notion entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.core.datetime_utils import utc_now_naive
from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


class NotionDatabaseEntity(BaseEntity):
    """Schema for a Notion database."""

    database_id: str = AirweaveField(
        ..., description="The ID of the database.", is_entity_id=True
    )
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
    property_id: str = AirweaveField(
        ..., description="The ID of the property", embeddable=False
    )
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

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the file."""
        if self.web_url_value:
            return self.web_url_value
        return self.url
