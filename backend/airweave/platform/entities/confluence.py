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

from pydantic import Field

from airweave.platform.entities._base import ChunkEntity, FileEntity


class ConfluenceSpaceEntity(ChunkEntity):
    """Schema for a Confluence Space.

    See:
      https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-spaces/
    """

    space_key: str = Field(..., description="Unique key for the space.")
    name: Optional[str] = Field(None, description="Name of the space.")
    space_type: Optional[str] = Field(None, description="Type of space (e.g. 'global').")
    description: Optional[str] = Field(None, description="Description of the space.")
    status: Optional[str] = Field(None, description="Status of the space if applicable.")
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when the space was created."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when the space was last updated."
    )


class ConfluencePageEntity(FileEntity):
    """Schema for a Confluence Page.

    See:
      https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-pages/
    """

    content_id: Optional[str] = Field(None, description="Actual Confluence page ID.")
    title: Optional[str] = Field(None, description="Title of the page.")
    space_id: Optional[str] = Field(None, description="ID of the space this page belongs to.")
    body: Optional[str] = Field(None, description="HTML body or excerpt of the page.")
    version: Optional[int] = Field(None, description="Page version number.")
    status: Optional[str] = Field(None, description="Status of the page (e.g., 'current').")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the page was created.")
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when the page was last updated."
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata about the page"
    )


class ConfluenceBlogPostEntity(ChunkEntity):
    """Schema for a Confluence Blog Post.

    See:
      https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-blog-posts/
    """

    content_id: Optional[str] = Field(None, description="Actual Confluence blog post ID.")
    title: Optional[str] = Field(None, description="Title of the blog post.")
    space_id: Optional[str] = Field(None, description="ID of the space this blog post is in.")
    body: Optional[str] = Field(None, description="HTML body of the blog post.")
    version: Optional[int] = Field(None, description="Blog post version number.")
    status: Optional[str] = Field(None, description="Status of the blog post (e.g., 'current').")
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when the blog post was created."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when the blog post was last updated."
    )


class ConfluenceCommentEntity(ChunkEntity):
    """Schema for a Confluence Comment.

    See:
      https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-comments/
    """

    content_id: Optional[str] = Field(
        None, description="ID of the content this comment is attached to."
    )
    text: Optional[str] = Field(None, description="Text/HTML body of the comment.")
    created_by: Optional[Dict[str, Any]] = Field(
        None, description="Information about the user who created the comment."
    )
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when this comment was created."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when this comment was last updated."
    )
    status: Optional[str] = Field(None, description="Status of the comment (e.g., 'current').")


class ConfluenceDatabaseEntity(ChunkEntity):
    """Schema for a Confluence Database object.

    See:
      (the "database" content type in Confluence Cloud).
    """

    title: Optional[str] = Field(None, description="Title or name of the database.")
    space_key: Optional[str] = Field(None, description="Space key for the database item.")
    description: Optional[str] = Field(None, description="Description or extra info about the DB.")
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when the database was created."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when the database was last updated."
    )
    status: Optional[str] = Field(None, description="Status of the database content item.")


class ConfluenceFolderEntity(ChunkEntity):
    """Schema for a Confluence Folder object.

    See:
      (the "folder" content type in Confluence Cloud).
    """

    title: Optional[str] = Field(None, description="Name of the folder.")
    space_key: Optional[str] = Field(None, description="Key of the space this folder is in.")
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when the folder was created."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when the folder was last updated."
    )
    status: Optional[str] = Field(None, description="Status of the folder (e.g., 'current').")


class ConfluenceLabelEntity(ChunkEntity):
    """Schema for a Confluence Label object.

    See:
      https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-labels/
    """

    name: str = Field(..., description="The text value of the label.")
    label_type: Optional[str] = Field(None, description="Type of the label (e.g., 'global').")
    owner_id: Optional[str] = Field(None, description="ID of the user or content that owns label.")


class ConfluenceTaskEntity(ChunkEntity):
    """Schema for a Confluence Task object.

    For example, tasks extracted from Confluence pages or macros.
    """

    content_id: Optional[str] = Field(
        None, description="The content ID (page, blog, etc.) that this task is associated with."
    )
    space_key: Optional[str] = Field(
        None, description="Space key if task is associated with a space."
    )
    text: Optional[str] = Field(None, description="Text of the task.")
    assignee: Optional[Dict[str, Any]] = Field(
        None, description="Information about the user assigned to this task."
    )
    completed: bool = Field(False, description="Indicates if this task is completed.")
    due_date: Optional[datetime] = Field(None, description="Due date/time if applicable.")
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when this task was created."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when this task was last updated."
    )


class ConfluenceWhiteboardEntity(ChunkEntity):
    """Schema for a Confluence Whiteboard object.

    See:
      (the "whiteboard" content type in Confluence Cloud).
    """

    title: Optional[str] = Field(None, description="Title of the whiteboard.")
    space_key: Optional[str] = Field(None, description="Key of the space this whiteboard is in.")
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when the whiteboard was created."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when the whiteboard was last updated."
    )
    status: Optional[str] = Field(None, description="Status of the whiteboard (e.g., 'current').")


class ConfluenceCustomContentEntity(ChunkEntity):
    """Schema for a Confluence Custom Content object.

    See:
      (the "custom content" type in Confluence Cloud).
    """

    title: Optional[str] = Field(None, description="Title or name of this custom content.")
    space_key: Optional[str] = Field(None, description="Key of the space this content resides in.")
    body: Optional[str] = Field(None, description="Optional HTML body or representation.")
    created_at: Optional[datetime] = Field(
        None, description="Timestamp when the custom content was created."
    )
    updated_at: Optional[datetime] = Field(
        None, description="Timestamp when the custom content was last updated."
    )
    status: Optional[str] = Field(
        None, description="Status of the custom content item (e.g., 'current')."
    )
