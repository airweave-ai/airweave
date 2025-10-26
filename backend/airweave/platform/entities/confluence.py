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

from typing import Any, Dict, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


class ConfluenceSpaceEntity(BaseEntity):
    """Schema for a Confluence Space.

    Reference:
        https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-spaces/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the space ID)
    # - breadcrumbs (empty - spaces are top-level)
    # - name (from space name)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    space_key: str = AirweaveField(..., description="Unique key for the space.", embeddable=True)
    space_type: Optional[str] = AirweaveField(
        None, description="Type of space (e.g. 'global').", embeddable=False
    )
    description: Optional[str] = AirweaveField(
        None, description="Description of the space.", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the space if applicable.", embeddable=False
    )
    homepage_id: Optional[str] = AirweaveField(
        None, description="ID of the homepage for this space.", embeddable=False
    )


class ConfluencePageEntity(FileEntity):
    """Schema for a Confluence Page.

    Pages are treated as FileEntity with HTML body saved to local file.
    Content is not stored in entity fields, only in the downloaded file.

    Reference:
        https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-pages/
    """

    # Base fields are inherited from BaseEntity:
    # - entity_id (the page ID)
    # - breadcrumbs (space breadcrumb)
    # - name (from title with .html extension)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # File fields are inherited from FileEntity:
    # - url (download URL for the page)
    # - size (0 - content in local file)
    # - file_type (set to "html")
    # - mime_type (set to "text/html")
    # - local_path (set after saving HTML content)

    # API fields (Confluence-specific)
    content_id: Optional[str] = AirweaveField(
        None, description="Actual Confluence page ID.", embeddable=False
    )
    title: Optional[str] = AirweaveField(None, description="Title of the page.", embeddable=True)
    space_id: Optional[str] = AirweaveField(
        None, description="ID of the space this page belongs to.", embeddable=False
    )
    body: Optional[str] = AirweaveField(
        None, description="HTML body or excerpt of the page.", embeddable=True
    )
    version: Optional[int] = AirweaveField(
        None, description="Page version number.", embeddable=False
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the page (e.g., 'current').", embeddable=False
    )


class ConfluenceBlogPostEntity(BaseEntity):
    """Schema for a Confluence Blog Post.

    Reference:
        https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-blog-posts/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the blog post ID)
    # - breadcrumbs (space breadcrumb)
    # - name (from blog post title)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    content_id: Optional[str] = AirweaveField(
        None, description="Actual Confluence blog post ID.", embeddable=False
    )
    title: Optional[str] = AirweaveField(
        None, description="Title of the blog post.", embeddable=True
    )
    space_id: Optional[str] = AirweaveField(
        None, description="ID of the space this blog post is in.", embeddable=False
    )
    body: Optional[str] = AirweaveField(
        None, description="HTML body of the blog post.", embeddable=True
    )
    version: Optional[int] = AirweaveField(
        None, description="Blog post version number.", embeddable=False
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the blog post (e.g., 'current').", embeddable=False
    )


class ConfluenceCommentEntity(BaseEntity):
    """Schema for a Confluence Comment.

    Reference:
        https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-comments/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the comment ID)
    # - breadcrumbs (space and page/blog breadcrumbs)
    # - name (from text preview)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    parent_content_id: Optional[str] = AirweaveField(
        None, description="ID of the content this comment is attached to.", embeddable=False
    )
    text: Optional[str] = AirweaveField(
        None, description="Text/HTML body of the comment.", embeddable=True
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the user who created the comment.", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the comment (e.g., 'current').", embeddable=False
    )


class ConfluenceDatabaseEntity(BaseEntity):
    """Schema for a Confluence Database object.

    Note: The "database" content type in Confluence Cloud.
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the database content ID)
    # - breadcrumbs (space breadcrumb)
    # - name (from database title)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    content_id: Optional[str] = AirweaveField(
        None, description="Actual Confluence database ID.", embeddable=False
    )
    title: Optional[str] = AirweaveField(
        None, description="Title or name of the database.", embeddable=True
    )
    space_key: Optional[str] = AirweaveField(
        None, description="Space key for the database item.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="Description or extra info about the DB.", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the database content item.", embeddable=False
    )


class ConfluenceFolderEntity(BaseEntity):
    """Schema for a Confluence Folder object.

    Note: The "folder" content type in Confluence Cloud.
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the folder content ID)
    # - breadcrumbs (space breadcrumb)
    # - name (from folder title)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    content_id: Optional[str] = AirweaveField(
        None, description="Actual Confluence folder ID.", embeddable=False
    )
    title: Optional[str] = AirweaveField(None, description="Name of the folder.", embeddable=True)
    space_key: Optional[str] = AirweaveField(
        None, description="Key of the space this folder is in.", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the folder (e.g., 'current').", embeddable=False
    )


class ConfluenceLabelEntity(BaseEntity):
    """Schema for a Confluence Label object.

    Reference:
        https://developer.atlassian.com/cloud/confluence/rest/v2/api-group-labels/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the label ID)
    # - breadcrumbs (empty - labels are top-level)
    # - name (from label name)
    # - created_at (None - labels don't have creation timestamp)
    # - updated_at (None - labels don't have update timestamp)

    # API fields
    label_type: Optional[str] = AirweaveField(
        None, description="Type of the label (e.g., 'global').", embeddable=False
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user or content that owns label.", embeddable=False
    )


class ConfluenceTaskEntity(BaseEntity):
    """Schema for a Confluence Task object.

    For example, tasks extracted from Confluence pages or macros.
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the task ID)
    # - breadcrumbs (space and content breadcrumbs)
    # - name (from task text)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    content_id: Optional[str] = AirweaveField(
        None,
        description="The content ID (page, blog, etc.) that this task is associated with.",
        embeddable=False,
    )
    space_key: Optional[str] = AirweaveField(
        None, description="Space key if task is associated with a space.", embeddable=True
    )
    text: Optional[str] = AirweaveField(None, description="Text of the task.", embeddable=True)
    assignee: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the user assigned to this task.", embeddable=True
    )
    completed: bool = AirweaveField(
        False, description="Indicates if this task is completed.", embeddable=True
    )
    due_date: Optional[Any] = AirweaveField(
        None, description="Due date/time if applicable.", embeddable=True
    )


class ConfluenceWhiteboardEntity(BaseEntity):
    """Schema for a Confluence Whiteboard object.

    Note: The "whiteboard" content type in Confluence Cloud.
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the whiteboard content ID)
    # - breadcrumbs (space breadcrumb)
    # - name (from whiteboard title)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    title: Optional[str] = AirweaveField(
        None, description="Title of the whiteboard.", embeddable=True
    )
    space_key: Optional[str] = AirweaveField(
        None, description="Key of the space this whiteboard is in.", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the whiteboard (e.g., 'current').", embeddable=False
    )


class ConfluenceCustomContentEntity(BaseEntity):
    """Schema for a Confluence Custom Content object.

    Note: The "custom content" type in Confluence Cloud.
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the custom content ID)
    # - breadcrumbs (space breadcrumb)
    # - name (from title)
    # - created_at (from createdAt timestamp)
    # - updated_at (from updatedAt timestamp)

    # API fields
    title: Optional[str] = AirweaveField(
        None, description="Title or name of this custom content.", embeddable=True
    )
    space_key: Optional[str] = AirweaveField(
        None, description="Key of the space this content resides in.", embeddable=True
    )
    body: Optional[str] = AirweaveField(
        None, description="Optional HTML body or representation.", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the custom content item (e.g., 'current').", embeddable=False
    )
