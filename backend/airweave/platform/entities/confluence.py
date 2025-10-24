"""Confluence entity schemas.

Based on the Confluence Cloud REST API reference (read-only scope), we define
entity schemas for the major Confluence objects relevant to our application:
 - Space
 - Page
 - Blog Post
 - Comment
 - Database
 - Folder
 - Label
 - Task
 - Whiteboard
 - Custom Content

Objects that reference a hierarchical relationship (e.g., pages with ancestors,
whiteboards with ancestors) will represent that hierarchy through a list of
breadcrumbs (see Breadcrumb in airweave.platform.entities._base) rather than nested objects.

Reference:
    https://developer.atlassian.com/cloud/confluence/rest/v2/intro/
    https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-ancestors/
"""

from datetime import datetime
from typing import Any, Dict, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base_legacy import ChunkEntity, FileEntity


class ConfluenceSpaceEntity(ChunkEntity):
    """Schema for a Confluence Space.

    See:
      https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-spaces/
    """

    space_key: str = AirweaveField(..., description="Unique key for the space.", embeddable=True)
    name: Optional[str] = AirweaveField(None, description="Name of the space.", embeddable=True)
    space_type: Optional[str] = AirweaveField(None, description="Type of space (e.g. 'global').")
    description: Optional[str] = AirweaveField(
        None, description="Description of the space.", embeddable=True
    )
    status: Optional[str] = AirweaveField(None, description="Status of the space if applicable.")
    created_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the space was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the space was last updated.", is_updated_at=True
    )


class ConfluencePageEntity(FileEntity):
    """Schema for a Confluence Page.

    See:
      https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-pages/
    """

    content_id: Optional[str] = AirweaveField(None, description="Actual Confluence page ID.")
    title: Optional[str] = AirweaveField(None, description="Title of the page.", embeddable=True)
    space_id: Optional[str] = AirweaveField(
        None, description="ID of the space this page belongs to.", embeddable=True
    )
    body: Optional[str] = AirweaveField(
        None, description="HTML body or excerpt of the page.", embeddable=True
    )
    version: Optional[int] = AirweaveField(None, description="Page version number.")
    status: Optional[str] = AirweaveField(None, description="Status of the page (e.g., 'current').")
    created_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the page was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the page was last updated.", is_updated_at=True
    )
    metadata: Optional[Dict[str, Any]] = AirweaveField(
        default_factory=dict, description="Additional metadata about the page"
    )


class ConfluenceBlogPostEntity(ChunkEntity):
    """Schema for a Confluence Blog Post.

    See:
      https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-blog-posts/
    """

    content_id: Optional[str] = AirweaveField(None, description="Actual Confluence blog post ID.")
    title: Optional[str] = AirweaveField(
        None, description="Title of the blog post.", embeddable=True
    )
    space_id: Optional[str] = AirweaveField(
        None, description="ID of the space this blog post is in.", embeddable=True
    )
    body: Optional[str] = AirweaveField(
        None, description="HTML body of the blog post.", embeddable=True
    )
    version: Optional[int] = AirweaveField(None, description="Blog post version number.")
    status: Optional[str] = AirweaveField(
        None, description="Status of the blog post (e.g., 'current')."
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the blog post was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the blog post was last updated.", is_updated_at=True
    )


class ConfluenceCommentEntity(ChunkEntity):
    """Schema for a Confluence Comment.

    See:
      https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-comments/
    """

    content_id: Optional[str] = AirweaveField(
        None, description="ID of the content this comment is attached to.", embeddable=True
    )
    text: Optional[str] = AirweaveField(
        None, description="Text/HTML body of the comment.", embeddable=True
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the user who created the comment."
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when this comment was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when this comment was last updated.", is_updated_at=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the comment (e.g., 'current')."
    )


class ConfluenceDatabaseEntity(ChunkEntity):
    """Schema for a Confluence Database object.

    See:
      (the "database" content type in Confluence Cloud).
    """

    title: Optional[str] = AirweaveField(
        None, description="Title or name of the database.", embeddable=True
    )
    space_key: Optional[str] = AirweaveField(
        None, description="Space key for the database item.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Description or extra info about the DB.", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the database was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the database was last updated.", is_updated_at=True
    )
    status: Optional[str] = AirweaveField(None, description="Status of the database content item.")


class ConfluenceFolderEntity(ChunkEntity):
    """Schema for a Confluence Folder object.

    See:
      (the "folder" content type in Confluence Cloud).
    """

    title: Optional[str] = AirweaveField(None, description="Name of the folder.", embeddable=True)
    space_key: Optional[str] = AirweaveField(
        None, description="Key of the space this folder is in.", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the folder was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the folder was last updated.", is_updated_at=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the folder (e.g., 'current')."
    )


class ConfluenceLabelEntity(ChunkEntity):
    """Schema for a Confluence Label object.

    See:
      https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-labels/
    """

    name: str = AirweaveField(..., description="The text value of the label.", embeddable=True)
    label_type: Optional[str] = AirweaveField(
        None, description="Type of the label (e.g., 'global')."
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user or content that owns label."
    )


class ConfluenceTaskEntity(ChunkEntity):
    """Schema for a Confluence Task object.

    For example, tasks extracted from Confluence pages or macros.
    """

    content_id: Optional[str] = AirweaveField(
        None,
        description="The content ID (page, blog, etc.) that this task is associated with.",
        embeddable=True,
    )
    space_key: Optional[str] = AirweaveField(
        None, description="Space key if task is associated with a space.", embeddable=True
    )
    text: Optional[str] = AirweaveField(None, description="Text of the task.", embeddable=True)
    assignee: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the user assigned to this task."
    )
    completed: bool = AirweaveField(
        False, description="Indicates if this task is completed.", embeddable=True
    )
    due_date: Optional[datetime] = AirweaveField(
        None, description="Due date/time if applicable.", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when this task was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when this task was last updated.", is_updated_at=True
    )


class ConfluenceWhiteboardEntity(ChunkEntity):
    """Schema for a Confluence Whiteboard object.

    See:
      (the "whiteboard" content type in Confluence Cloud).
    """

    title: Optional[str] = AirweaveField(
        None, description="Title of the whiteboard.", embeddable=True
    )
    space_key: Optional[str] = AirweaveField(
        None, description="Key of the space this whiteboard is in.", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the whiteboard was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the whiteboard was last updated.", is_updated_at=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the whiteboard (e.g., 'current')."
    )


class ConfluenceCustomContentEntity(ChunkEntity):
    """Schema for a Confluence Custom Content object.

    See:
      (the "custom content" type in Confluence Cloud).
    """

    title: Optional[str] = AirweaveField(
        None, description="Title or name of this custom content.", embeddable=True
    )
    space_key: Optional[str] = AirweaveField(
        None, description="Key of the space this content resides in.", embeddable=True
    )
    body: Optional[str] = AirweaveField(
        None, description="Optional HTML body or representation.", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the custom content was created.", is_created_at=True
    )
    updated_at: Optional[datetime] = AirweaveField(
        None, description="Timestamp when the custom content was last updated.", is_updated_at=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the custom content item (e.g., 'current')."
    )
