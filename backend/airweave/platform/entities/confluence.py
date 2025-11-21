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

from pydantic import computed_field

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
    space_id: str = AirweaveField(
        ..., description="Unique identifier for the space.", embeddable=False, is_entity_id=True
    )
    space_name: str = AirweaveField(
        ..., description="Display name of the space.", embeddable=True, is_name=True
    )
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
    site_url: Optional[str] = AirweaveField(
        None, description="Base Confluence site URL.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this space."""
        if self.site_url:
            return f"{self.site_url}/wiki/spaces/{self.space_key}"
        return f"https://your-domain.atlassian.net/wiki/spaces/{self.space_key}"


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
    content_id: str = AirweaveField(
        ..., description="Actual Confluence page ID.", embeddable=False, is_entity_id=True
    )
    title: str = AirweaveField(..., description="Title of the page.", embeddable=True, is_name=True)
    space_id: Optional[str] = AirweaveField(
        None, description="ID of the space this page belongs to.", embeddable=False
    )
    space_key: Optional[str] = AirweaveField(
        None, description="Key of the space this page belongs to.", embeddable=False
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
    site_url: Optional[str] = AirweaveField(
        None, description="Base Confluence site URL.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this page."""
        if self.site_url and self.space_key:
            return f"{self.site_url}/wiki/spaces/{self.space_key}/pages/{self.content_id}"
        return f"https://your-domain.atlassian.net/wiki/spaces/SPACE/pages/{self.content_id}"


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
    content_id: str = AirweaveField(
        ..., description="Actual Confluence blog post ID.", embeddable=False, is_entity_id=True
    )
    title: str = AirweaveField(
        ..., description="Title of the blog post.", embeddable=True, is_name=True
    )
    space_id: Optional[str] = AirweaveField(
        None, description="ID of the space this blog post is in.", embeddable=False
    )
    space_key: Optional[str] = AirweaveField(
        None, description="Key of the space this blog post is in.", embeddable=False
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
    site_url: Optional[str] = AirweaveField(
        None, description="Base Confluence site URL.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for this blog post."""
        if self.site_url and self.space_key:
            return f"{self.site_url}/wiki/spaces/{self.space_key}/blog/{self.content_id}"
        return f"https://your-domain.atlassian.net/wiki/spaces/SPACE/blog/{self.content_id}"


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
    comment_id: str = AirweaveField(
        ..., description="Unique identifier for the comment.", embeddable=False, is_entity_id=True
    )
    parent_content_id: Optional[str] = AirweaveField(
        None, description="ID of the content this comment is attached to.", embeddable=False
    )
    parent_space_key: Optional[str] = AirweaveField(
        None, description="Key of the space the parent content belongs to.", embeddable=False
    )
    text: str = AirweaveField(
        ..., description="Text/HTML body of the comment.", embeddable=True, is_name=True
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the user who created the comment.", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the comment (e.g., 'current').", embeddable=False
    )
    site_url: Optional[str] = AirweaveField(
        None, description="Base Confluence site URL.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for the parent page (comments don't have direct URLs)."""
        if self.site_url and self.parent_space_key and self.parent_content_id:
            return f"{self.site_url}/wiki/spaces/{self.parent_space_key}/pages/{self.parent_content_id}#comment-{self.comment_id}"
        return f"https://your-domain.atlassian.net/wiki/spaces/SPACE/pages/PAGE#comment-{self.comment_id}"


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
    content_id: str = AirweaveField(
        ..., description="Actual Confluence database ID.", embeddable=False, is_entity_id=True
    )
    title: str = AirweaveField(
        ..., description="Title or name of the database.", embeddable=True, is_name=True
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
    content_id: str = AirweaveField(
        ..., description="Actual Confluence folder ID.", embeddable=False, is_entity_id=True
    )
    title: str = AirweaveField(
        ..., description="Name of the folder.", embeddable=True, is_name=True
    )
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
    label_id: str = AirweaveField(
        ..., description="Unique identifier for the label.", embeddable=False, is_entity_id=True
    )
    label_name: str = AirweaveField(
        ..., description="Display name of the label.", embeddable=True, is_name=True
    )
    label_type: Optional[str] = AirweaveField(
        None, description="Type of the label (e.g., 'global').", embeddable=False
    )
    owner_id: Optional[str] = AirweaveField(
        None, description="ID of the user or content that owns label.", embeddable=False
    )
    site_url: Optional[str] = AirweaveField(
        None, description="Base Confluence site URL.", embeddable=False, unhashable=True
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct clickable web URL for searching this label."""
        if self.site_url:
            return f"{self.site_url}/wiki/label/{self.label_name}"
        return f"https://your-domain.atlassian.net/wiki/label/{self.label_name}"


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
    task_id: str = AirweaveField(
        ..., description="Unique identifier for the task.", embeddable=False, is_entity_id=True
    )
    content_id: Optional[str] = AirweaveField(
        None,
        description="The content ID (page, blog, etc.) that this task is associated with.",
        embeddable=False,
    )
    space_key: Optional[str] = AirweaveField(
        None, description="Space key if task is associated with a space.", embeddable=True
    )
    text: str = AirweaveField(..., description="Text of the task.", embeddable=True, is_name=True)
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
    whiteboard_id: str = AirweaveField(
        ...,
        description="Unique identifier for the whiteboard.",
        embeddable=False,
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ..., description="Title of the whiteboard.", embeddable=True, is_name=True
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
    custom_content_id: str = AirweaveField(
        ...,
        description="Unique identifier for the custom content.",
        embeddable=False,
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ..., description="Title or name of this custom content.", embeddable=True, is_name=True
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
