"""Entity schemas for Document360.

MVP entities: Articles, Categories, Project Versions.
API reference: https://apidocs.document360.com/apidocs/getting-started
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class Document360ProjectVersionEntity(BaseEntity):
    """Schema for Document360 project version (knowledge base version)."""

    id: str = AirweaveField(
        ...,
        description="Unique ID of the project version",
        embeddable=False,
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Display name of the version (e.g. version_code_name or version number)",
        embeddable=True,
        is_name=True,
    )
    version_number: Optional[float] = AirweaveField(
        None,
        description="Project version number",
        embeddable=True,
    )
    version_code_name: Optional[str] = AirweaveField(
        None,
        description="Custom version name (e.g. v1)",
        embeddable=True,
    )
    is_main_version: bool = Field(
        False,
        description="True if this is the main version after loading documentation",
    )
    is_public: bool = Field(
        True,
        description="True if this version is visible to the public",
    )
    is_beta: bool = Field(False, description="True if this version is marked as Beta")
    is_deprecated: bool = Field(
        False,
        description="True if this version is marked as deprecated",
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the version was created",
        embeddable=True,
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the version was last modified",
        embeddable=True,
        is_updated_at=True,
    )
    slug: Optional[str] = Field(None, description="URL slug for the version")
    order: Optional[int] = Field(None, description="Display order")
    version_type: Optional[int] = Field(
        None,
        description="0 = KB workspace, 1 = API Reference workspace",
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="Base URL to the knowledge base (if known)",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the project version."""
        return self.web_url_value or ""


class Document360CategoryEntity(BaseEntity):
    """Schema for Document360 category (folder/page/index in the TOC)."""

    id: str = AirweaveField(
        ...,
        description="Unique ID of the category",
        embeddable=False,
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Name of the category",
        embeddable=True,
        is_name=True,
    )
    description: Optional[str] = AirweaveField(
        None,
        description="Description of the category",
        embeddable=True,
    )
    project_version_id: Optional[str] = Field(
        None,
        description="ID of the project version this category belongs to",
    )
    project_version_name: Optional[str] = AirweaveField(
        None,
        description="Name of the project version",
        embeddable=True,
    )
    parent_category_id: Optional[str] = Field(
        None,
        description="ID of the parent category (null if top-level)",
    )
    order: Optional[int] = Field(None, description="Position inside the parent category")
    slug: Optional[str] = AirweaveField(
        None,
        description="URL slug of the category",
        embeddable=True,
    )
    category_type: Optional[int] = Field(
        None,
        description="0 = Folder, 1 = Page, 2 = Index",
    )
    hidden: bool = Field(False, description="Whether the category is visible on the site")
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the category was created",
        embeddable=True,
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the category was last modified",
        embeddable=True,
        is_updated_at=True,
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the category in Document360",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the category."""
        return self.web_url_value or ""


class Document360ArticleEntity(BaseEntity):
    """Schema for Document360 article (document with content)."""

    id: str = AirweaveField(
        ...,
        description="Unique ID of the article",
        embeddable=False,
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Title of the article",
        embeddable=True,
        is_name=True,
    )
    content: Optional[str] = AirweaveField(
        None,
        description="Main text content (Markdown or plain text)",
        embeddable=True,
    )
    html_content: Optional[str] = AirweaveField(
        None,
        description="HTML content when editor is WYSIWYG",
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None,
        description="Short description of the article",
        embeddable=True,
    )
    category_id: Optional[str] = Field(
        None,
        description="ID of the parent category",
    )
    category_name: Optional[str] = AirweaveField(
        None,
        description="Name of the parent category",
        embeddable=True,
    )
    project_version_id: Optional[str] = Field(
        None,
        description="ID of the project version",
    )
    project_version_name: Optional[str] = AirweaveField(
        None,
        description="Name of the project version",
        embeddable=True,
    )
    slug: Optional[str] = AirweaveField(
        None,
        description="URL slug of the article",
        embeddable=True,
    )
    status: Optional[int] = AirweaveField(
        None,
        description="0 = Draft, 3 = Published",
        embeddable=True,
    )
    language_code: Optional[str] = AirweaveField(
        None,
        description="Language code of the article",
        embeddable=True,
    )
    public_version: Optional[int] = Field(
        None,
        description="Published version number",
    )
    latest_version: Optional[int] = Field(
        None,
        description="Latest version number",
    )
    authors: List[Dict[str, Any]] = AirweaveField(
        default_factory=list,
        description="List of authors/contributors",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the article was created",
        embeddable=True,
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the article was last modified",
        embeddable=True,
        is_updated_at=True,
    )
    article_url: Optional[str] = Field(
        None,
        description="Full URL of the article from list API (if provided)",
    )
    web_url_value: Optional[str] = AirweaveField(
        None,
        description="URL to view the article in Document360",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """User-facing link to the article."""
        return self.web_url_value or self.article_url or ""
