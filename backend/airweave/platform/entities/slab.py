"""Slab entity schemas."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, Breadcrumb


def _parse_dt(datetime_str: Optional[str]) -> Optional[datetime]:
    """Parse ISO datetime string to naive-UTC datetime."""
    if not datetime_str:
        return None
    try:
        if datetime_str.endswith("Z"):
            datetime_str = datetime_str[:-1] + "+00:00"
        dt = datetime.fromisoformat(datetime_str)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except (ValueError, AttributeError):
        return None


def _quill_delta_to_plain_text(content: Any) -> str:
    """Convert Slab/Quill delta JSON to plain text for embedding."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    parts: list[str] = []
    for op in content:
        if not isinstance(op, dict):
            continue
        insert = op.get("insert")
        if isinstance(insert, str):
            parts.append(insert)
        elif isinstance(insert, dict):
            parts.append("[image]" if "image" in insert else "[embed]")
    return "".join(parts).strip()


def _json_description_to_string(description: Any) -> Optional[str]:
    """Convert Topic.description (Json) to a single string."""
    if description is None:
        return None
    if isinstance(description, str):
        return description
    if isinstance(description, list):
        return " ".join(str(item) for item in description if item is not None).strip() or None
    if isinstance(description, dict):
        text = description.get("text") or description.get("content")
        if text:
            return str(text)
        return str(description)
    return str(description)


def _build_topic_url(host: str, topic_id: str) -> str:
    """Build web URL for a topic."""
    base = host if host.startswith("http") else f"https://{host}"
    return f"{base.rstrip('/')}/t/{topic_id}"


def _build_post_url(host: str, post_id: str) -> str:
    """Build web URL for a post."""
    base = host if host.startswith("http") else f"https://{host}"
    return f"{base.rstrip('/')}/posts/{post_id}"


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

    @classmethod
    def from_api(cls, data: Dict[str, Any], *, host: str) -> SlabTopicEntity:
        """Build a topic entity from API data."""
        topic_id = data.get("id")
        return cls(
            entity_id=topic_id,
            breadcrumbs=[],
            topic_id=topic_id,
            name=data.get("name", "Untitled Topic"),
            created_at=_parse_dt(data.get("insertedAt")),
            updated_at=_parse_dt(data.get("updatedAt")),
            description=_json_description_to_string(data.get("description")),
            slug=None,
            web_url_value=_build_topic_url(host, topic_id),
        )


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

    @classmethod
    def from_api(
        cls,
        data: Dict[str, Any],
        *,
        topics_by_id: Dict[str, Dict[str, Any]],
        host: str,
    ) -> SlabPostEntity:
        """Build a post entity from API data."""
        post_id = data.get("id")
        post_title = data.get("title", "Untitled Post")
        post_topics = data.get("topics") or []
        first_topic = post_topics[0] if post_topics else {}
        topic_id = first_topic.get("id", "")
        topic_name = first_topic.get("name", "Unknown topic")
        content_plain = _quill_delta_to_plain_text(data.get("content"))
        owner = data.get("owner") or {}
        author = (
            {"id": owner.get("id"), "name": owner.get("name"), "email": owner.get("email")}
            if owner
            else None
        )
        breadcrumbs: List[Breadcrumb] = []
        if topic_id and topic_id in topics_by_id:
            breadcrumbs.append(
                Breadcrumb(
                    entity_id=topic_id,
                    name=topics_by_id[topic_id].get("name", topic_name),
                    entity_type="SlabTopicEntity",
                )
            )
        return cls(
            entity_id=post_id,
            breadcrumbs=breadcrumbs,
            post_id=post_id,
            title=post_title,
            created_at=_parse_dt(data.get("insertedAt")),
            updated_at=_parse_dt(data.get("updatedAt")),
            content=content_plain or None,
            topic_id=topic_id or "",
            topic_name=topic_name,
            author=author,
            tags=[],
            slug=None,
            web_url_value=_build_post_url(host, post_id),
        )


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

    @classmethod
    def from_api(cls, payload: Dict[str, Any], *, host: str) -> Optional[SlabCommentEntity]:
        """Build a comment entity from a search result payload.

        Returns None if the payload has no comment ID.
        """
        comment = payload.get("comment") or {}
        node_content = payload.get("node_content")
        comment_id = comment.get("id")
        if not comment_id:
            return None
        post_obj = comment.get("post") or {}
        post_id = (post_obj.get("id") or "").strip()
        post_title = (post_obj.get("title") or "").strip() or "Unknown post"
        content_json = comment.get("content") or node_content
        content_plain = _quill_delta_to_plain_text(content_json) if content_json else ""
        author_data = comment.get("author") or {}
        author = (
            {
                "id": author_data.get("id"),
                "name": author_data.get("name"),
                "email": author_data.get("email"),
            }
            if author_data
            else None
        )
        base = host if host.startswith("http") else f"https://{host}"
        base_r = base.rstrip("/")
        if post_id:
            comment_url = f"{base_r}/posts/{post_id}#comment-{comment_id}"
        else:
            comment_url = f"{base_r}/comments/{comment_id}"
        return cls(
            entity_id=comment_id,
            breadcrumbs=[],
            comment_id=comment_id,
            content=content_plain or "",
            created_at=_parse_dt(comment.get("insertedAt")),
            updated_at=None,
            post_id=post_id or "",
            post_title=post_title,
            topic_id=None,
            topic_name=None,
            author=author,
            web_url_value=comment_url,
        )
