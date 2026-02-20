"""Entity schemas for Coda.

Maps Coda API resources (docs, pages, tables, rows) to Airweave entities
for hybrid documentation and database content.
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class CodaDocEntity(BaseEntity):
    """Schema for a Coda doc (top-level container)."""

    doc_id: str = AirweaveField(
        ...,
        description="ID of the Coda doc.",
        embeddable=False,
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Name/title of the doc.",
        embeddable=True,
        is_name=True,
    )
    owner: Optional[str] = AirweaveField(
        None,
        description="Email of the doc owner.",
        embeddable=True,
    )
    owner_name: Optional[str] = AirweaveField(
        None,
        description="Display name of the doc owner.",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the doc was created.",
        embeddable=True,
        is_created_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the doc was last modified.",
        embeddable=True,
        is_updated_at=True,
    )
    workspace_name: Optional[str] = AirweaveField(
        None,
        description="Name of the workspace containing the doc.",
        embeddable=True,
    )
    folder_name: Optional[str] = AirweaveField(
        None,
        description="Name of the folder containing the doc.",
        embeddable=True,
    )
    browser_link: Optional[str] = AirweaveField(
        None,
        description="Browser URL for the doc.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the doc."""
        return self.browser_link or ""


class CodaPageEntity(BaseEntity):
    """Schema for a Coda page (canvas with content)."""

    page_id: str = AirweaveField(
        ...,
        description="ID of the page.",
        embeddable=False,
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Name of the page.",
        embeddable=True,
        is_name=True,
    )
    subtitle: Optional[str] = AirweaveField(
        None,
        description="Subtitle of the page.",
        embeddable=True,
    )
    doc_id: str = AirweaveField(
        ...,
        description="ID of the parent doc.",
        embeddable=False,
    )
    doc_name: Optional[str] = AirweaveField(
        None,
        description="Name of the parent doc.",
        embeddable=True,
    )
    content: Optional[str] = AirweaveField(
        None,
        description="Aggregated page content (plain text).",
        embeddable=True,
    )
    content_type: Optional[str] = AirweaveField(
        None,
        description="Page type (canvas, embed, syncPage).",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the page was created.",
        embeddable=True,
        is_created_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the page was last modified.",
        embeddable=True,
        is_updated_at=True,
    )
    browser_link: Optional[str] = AirweaveField(
        None,
        description="Browser URL for the page.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the page."""
        return self.browser_link or ""


class CodaTableEntity(BaseEntity):
    """Schema for a Coda table or view."""

    table_id: str = AirweaveField(
        ...,
        description="ID of the table.",
        embeddable=False,
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Name of the table.",
        embeddable=True,
        is_name=True,
    )
    table_type: Optional[str] = AirweaveField(
        None,
        description="Type (table or view).",
        embeddable=True,
    )
    doc_id: str = AirweaveField(
        ...,
        description="ID of the parent doc.",
        embeddable=False,
    )
    doc_name: Optional[str] = AirweaveField(
        None,
        description="Name of the parent doc.",
        embeddable=True,
    )
    page_name: Optional[str] = AirweaveField(
        None,
        description="Name of the parent page if any.",
        embeddable=True,
    )
    row_count: int = AirweaveField(
        0,
        description="Number of rows in the table.",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the table was created.",
        embeddable=True,
        is_created_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the table was last modified.",
        embeddable=True,
        is_updated_at=True,
    )
    browser_link: Optional[str] = AirweaveField(
        None,
        description="Browser URL for the table.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the table."""
        return self.browser_link or ""


class CodaRowEntity(BaseEntity):
    """Schema for a row in a Coda table."""

    row_id: str = AirweaveField(
        ...,
        description="ID of the row.",
        embeddable=False,
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Display name of the row (identifying column value).",
        embeddable=True,
        is_name=True,
    )
    table_id: str = AirweaveField(
        ...,
        description="ID of the parent table.",
        embeddable=False,
    )
    table_name: Optional[str] = AirweaveField(
        None,
        description="Name of the parent table.",
        embeddable=True,
    )
    doc_id: str = AirweaveField(
        ...,
        description="ID of the doc containing the table.",
        embeddable=False,
    )
    values: Dict[str, Any] = AirweaveField(
        default_factory=dict,
        description="Cell values keyed by column ID.",
        embeddable=True,
    )
    values_text: Optional[str] = AirweaveField(
        None,
        description="Human-readable row content for search.",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the row was created.",
        embeddable=True,
        is_created_at=True,
    )
    updated_at: Optional[datetime] = AirweaveField(
        None,
        description="When the row was last modified.",
        embeddable=True,
        is_updated_at=True,
    )
    browser_link: Optional[str] = AirweaveField(
        None,
        description="Browser URL for the row.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the row."""
        return self.browser_link or ""
