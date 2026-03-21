"""Entity schemas for Document360.

MVP entities: Articles, Categories, Project Versions.
API reference: https://apidocs.document360.com/apidocs/getting-started
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse ISO 8601 datetime string to datetime."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


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

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> Document360ProjectVersionEntity:
        """Build from a Document360 project-version API object."""
        version_id = data.get("id") or ""
        version_name = (
            data.get("version_code_name")
            or (str(data["version_number"]) if data.get("version_number") is not None else None)
            or version_id
        )
        return cls(
            entity_id=version_id,
            breadcrumbs=[],
            id=version_id,
            name=str(version_name),
            version_number=data.get("version_number"),
            version_code_name=data.get("version_code_name"),
            is_main_version=data.get("is_main_version", False),
            is_public=data.get("is_public", True),
            is_beta=data.get("is_beta", False),
            is_deprecated=data.get("is_deprecated", False),
            created_at=_parse_dt(data.get("created_at")),
            modified_at=_parse_dt(data.get("modified_at")),
            slug=data.get("slug"),
            order=data.get("order"),
            version_type=data.get("version_type"),
        )


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

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        project_version_id: str,
        project_version_name: str,
        breadcrumbs: list[Breadcrumb],
    ) -> Document360CategoryEntity:
        """Build from a Document360 category API object."""
        cat_id = data.get("id") or ""
        return cls(
            entity_id=cat_id,
            breadcrumbs=breadcrumbs,
            id=cat_id,
            name=data.get("name") or "Unnamed category",
            description=data.get("description"),
            project_version_id=project_version_id,
            project_version_name=project_version_name,
            parent_category_id=data.get("parent_category_id"),
            order=data.get("order"),
            slug=data.get("slug"),
            category_type=data.get("category_type"),
            hidden=data.get("hidden", False),
            created_at=_parse_dt(data.get("created_at")),
            modified_at=_parse_dt(data.get("modified_at")),
        )


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

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        detail: Dict[str, Any] | None = None,
        category_id: str,
        category_name: str,
        project_version_id: str,
        project_version_name: str,
        breadcrumbs: list[Breadcrumb],
        lang_code: str = "en",
    ) -> Document360ArticleEntity:
        """Build from list-level article data with optional detail-level enrichment."""
        article_id = data.get("id") or ""
        d = detail or {}

        content = d.get("content")
        html_content = d.get("html_content")
        authors = d.get("authors") or []
        created_at = _parse_dt(d.get("created_at"))
        modified_at = _parse_dt(d.get("modified_at"))
        description = d.get("description")

        title = data.get("title") or d.get("title") or "Unnamed article"
        article_url = data.get("url")

        return cls(
            entity_id=article_id,
            breadcrumbs=breadcrumbs,
            id=article_id,
            name=title,
            content=content,
            html_content=html_content,
            description=description,
            category_id=category_id,
            category_name=category_name,
            project_version_id=project_version_id,
            project_version_name=project_version_name,
            slug=data.get("slug") or d.get("slug"),
            status=data.get("status") if data.get("status") is not None else d.get("status"),
            language_code=data.get("language_code") or lang_code,
            public_version=data.get("public_version"),
            latest_version=data.get("latest_version"),
            authors=authors,
            created_at=created_at or _parse_dt(data.get("modified_at")),
            modified_at=modified_at or _parse_dt(data.get("modified_at")),
            article_url=article_url,
            web_url_value=article_url,
        )
