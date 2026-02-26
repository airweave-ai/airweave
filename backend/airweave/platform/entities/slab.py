"""Slab entity schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity


class SlabTopicEntity(BaseEntity):
    """Schema for a Slab topic (top-level category/folder).

    Topics are containers for posts in Slab, similar to spaces in Confluence
    or databases in Notion.
    """

    topic_id: str = AirweaveField(
        ..., description="Unique Slab ID of the topic.", is_entity_id=True
    )
    name: str = AirweaveField(
        ..., description="Display name of the topic", embeddable=True, is_name=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the topic was created.", is_created_at=True, embeddable=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the topic was last updated.", is_updated_at=True, embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Description of the topic", embeddable=True
    )
    slug: Optional[str] = AirweaveField(None, description="URL slug for the topic", embeddable=True)
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the topic in Slab.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the topic."""
        return self.web_url_value or ""


class SlabPostEntity(BaseEntity):
    """Schema for a Slab post (document/article).

    Posts are the main content entities in Slab, containing documentation
    and wiki articles.
    """

    post_id: str = AirweaveField(..., description="Unique Slab ID of the post.", is_entity_id=True)
    title: str = AirweaveField(..., description="Title of the post", embeddable=True, is_name=True)
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the post was created.", is_created_at=True, embeddable=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the post was last updated.", is_updated_at=True, embeddable=True
    )
    content: Optional[str] = AirweaveField(
        None, description="Full content/body of the post", embeddable=True
    )
    topic_id: str = AirweaveField(
        ..., description="ID of the topic this post belongs to", embeddable=False
    )
    topic_name: str = AirweaveField(
        ..., description="Name of the topic this post belongs to", embeddable=True
    )
    author: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Author information (name, email, etc.)", embeddable=True
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with the post", embeddable=True
    )
    slug: Optional[str] = AirweaveField(None, description="URL slug for the post", embeddable=True)
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the post in Slab.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the post."""
        return self.web_url_value or ""


class SlabCommentEntity(BaseEntity):
    """Schema for a Slab comment on a post.

    Comments provide discussion and feedback on posts.
    """

    comment_id: str = AirweaveField(
        ..., description="Unique Slab ID of the comment.", is_entity_id=True
    )
    content: str = AirweaveField(
        ..., description="Content/body of the comment", embeddable=True, is_name=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="When the comment was created.", is_created_at=True, embeddable=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="When the comment was last updated.", is_updated_at=True, embeddable=True
    )
    post_id: str = AirweaveField(
        ..., description="ID of the post this comment belongs to", embeddable=False
    )
    post_title: str = AirweaveField(
        ..., description="Title of the post this comment belongs to", embeddable=True
    )
    topic_id: Optional[str] = AirweaveField(
        None, description="ID of the topic this comment belongs to", embeddable=False
    )
    topic_name: Optional[str] = AirweaveField(
        None, description="Name of the topic this comment belongs to", embeddable=True
    )
    author: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Author information (name, email, etc.)", embeddable=True
    )
    web_url_value: Optional[str] = AirweaveField(
        None, description="URL to view the comment in Slab.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Browser URL for the comment."""
        return self.web_url_value or ""
