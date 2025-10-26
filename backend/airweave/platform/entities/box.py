"""Box entity schemas."""

from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


class BoxUserEntity(BaseEntity):
    """Schema for Box user entities.

    Reference:
        https://developer.box.com/reference/resources/user/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the Box user ID)
    # - breadcrumbs (empty - users are top-level)
    # - name (from display name)
    # - created_at (from created_at timestamp)
    # - updated_at (from modified_at timestamp)

    # API fields
    login: Optional[str] = AirweaveField(
        None, description="Login email address of the user", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the user (active, inactive, etc.)", embeddable=False
    )
    job_title: Optional[str] = AirweaveField(
        None, description="Job title of the user", embeddable=True
    )
    phone: Optional[str] = AirweaveField(
        None, description="Phone number of the user", embeddable=True
    )
    address: Optional[str] = AirweaveField(None, description="Address of the user", embeddable=True)
    language: Optional[str] = AirweaveField(
        None, description="Language of the user", embeddable=False
    )
    timezone: Optional[str] = AirweaveField(
        None, description="Timezone of the user", embeddable=False
    )
    space_amount: Optional[int] = AirweaveField(
        None, description="Total storage space available to the user in bytes", embeddable=False
    )
    space_used: Optional[int] = AirweaveField(
        None, description="Storage space used by the user in bytes", embeddable=False
    )
    max_upload_size: Optional[int] = AirweaveField(
        None, description="Maximum file size the user can upload in bytes", embeddable=False
    )
    avatar_url: Optional[str] = AirweaveField(
        None, description="URL to the user's avatar image", embeddable=False
    )


class BoxFolderEntity(BaseEntity):
    """Schema for Box folder entities.

    Reference:
        https://developer.box.com/reference/resources/folder/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the Box folder ID)
    # - breadcrumbs (parent folder breadcrumbs)
    # - name (from folder name)
    # - created_at (from created_at timestamp)
    # - updated_at (from modified_at timestamp)

    # API fields
    description: Optional[str] = AirweaveField(
        None, description="Description of the folder", embeddable=True
    )
    size: Optional[int] = AirweaveField(
        None, description="Size of the folder in bytes", embeddable=False
    )
    path_collection: List[Dict] = AirweaveField(
        default_factory=list,
        description="Path of parent folders from root to this folder",
        embeddable=True,
    )
    content_created_at: Optional[Any] = AirweaveField(
        None,
        description="When the content in this folder was originally created",
        embeddable=False,
    )
    content_modified_at: Optional[Any] = AirweaveField(
        None,
        description="When the content in this folder was last modified",
        embeddable=False,
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created this folder", embeddable=True
    )
    modified_by: Optional[Dict] = AirweaveField(
        None, description="User who last modified this folder", embeddable=True
    )
    owned_by: Optional[Dict] = AirweaveField(
        None, description="User who owns this folder", embeddable=True
    )
    parent_id: Optional[str] = AirweaveField(
        None, description="ID of the parent folder", embeddable=False
    )
    parent_name: Optional[str] = AirweaveField(
        None, description="Name of the parent folder", embeddable=True
    )
    item_status: Optional[str] = AirweaveField(
        None,
        description="Status of the folder (active, trashed, deleted)",
        embeddable=False,
    )
    shared_link: Optional[Dict] = AirweaveField(
        None, description="Shared link information for this folder", embeddable=True
    )
    folder_upload_email: Optional[Dict] = AirweaveField(
        None,
        description="Email address that can be used to upload files to this folder",
        embeddable=True,
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with this folder", embeddable=True
    )
    has_collaborations: Optional[bool] = AirweaveField(
        None, description="Whether this folder has collaborations", embeddable=False
    )
    permissions: Optional[Dict] = AirweaveField(
        None, description="Permissions the current user has on this folder", embeddable=False
    )
    permalink_url: Optional[str] = AirweaveField(
        None, description="Direct link to view the folder in Box", embeddable=False
    )
    etag: Optional[str] = AirweaveField(
        None, description="Entity tag for versioning", embeddable=False
    )
    sequence_id: Optional[str] = AirweaveField(
        None, description="Sequence ID for the most recent user event", embeddable=False
    )


class BoxFileEntity(FileEntity):
    """Schema for Box file entities.

    Reference:
        https://developer.box.com/reference/resources/file/
    """

    # Base fields are inherited from BaseEntity:
    # - entity_id (the Box file ID)
    # - breadcrumbs (parent folder breadcrumbs)
    # - name (from file name)
    # - created_at (from created_at timestamp)
    # - updated_at (from modified_at timestamp)

    # File fields are inherited from FileEntity:
    # - url (download URL)
    # - size (file size in bytes)
    # - file_type (determined from mime_type or extension)
    # - mime_type
    # - local_path (set after download)

    # API fields (Box-specific)
    description: Optional[str] = AirweaveField(
        None, description="Description of the file", embeddable=True
    )
    parent_folder_id: str = AirweaveField(
        ..., description="ID of the parent folder", embeddable=False
    )
    parent_folder_name: str = AirweaveField(
        ..., description="Name of the parent folder", embeddable=True
    )
    path_collection: List[Dict] = AirweaveField(
        default_factory=list,
        description="Path of parent folders from root to this file",
        embeddable=True,
    )
    sha1: Optional[str] = AirweaveField(
        None, description="SHA1 hash of the file contents", embeddable=False
    )
    extension: Optional[str] = AirweaveField(None, description="File extension", embeddable=False)
    version_number: Optional[str] = AirweaveField(
        None, description="Version number of the file", embeddable=False
    )
    comment_count: Optional[int] = AirweaveField(
        None, description="Number of comments on this file", embeddable=False
    )
    content_created_at: Optional[Any] = AirweaveField(
        None,
        description="When the content of this file was originally created",
        embeddable=False,
    )
    content_modified_at: Optional[Any] = AirweaveField(
        None,
        description="When the content of this file was last modified",
        embeddable=False,
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created this file", embeddable=True
    )
    modified_by: Optional[Dict] = AirweaveField(
        None, description="User who last modified this file", embeddable=True
    )
    owned_by: Optional[Dict] = AirweaveField(
        None, description="User who owns this file", embeddable=True
    )
    item_status: Optional[str] = AirweaveField(
        None, description="Status of the file (active, trashed, deleted)", embeddable=False
    )
    shared_link: Optional[Dict] = AirweaveField(
        None, description="Shared link information for this file", embeddable=True
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with this file", embeddable=True
    )
    has_collaborations: Optional[bool] = AirweaveField(
        None, description="Whether this file has collaborations", embeddable=False
    )
    permissions: Optional[Dict] = AirweaveField(
        None, description="Permissions the current user has on this file", embeddable=False
    )
    lock: Optional[Dict] = AirweaveField(
        None, description="Lock information if the file is locked", embeddable=False
    )
    permalink_url: Optional[str] = AirweaveField(
        None, description="Direct link to view the file in Box", embeddable=False
    )
    etag: Optional[str] = AirweaveField(
        None, description="Entity tag for versioning", embeddable=False
    )
    sequence_id: Optional[str] = AirweaveField(
        None, description="Sequence ID for the most recent user event", embeddable=False
    )


class BoxCommentEntity(BaseEntity):
    """Schema for Box comment entities.

    Reference:
        https://developer.box.com/reference/resources/comment/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the Box comment ID)
    # - breadcrumbs (folder and file breadcrumbs)
    # - name (from message preview)
    # - created_at (from created_at timestamp)
    # - updated_at (from modified_at timestamp)

    # API fields
    file_id: str = AirweaveField(
        ..., description="ID of the file this comment is on", embeddable=False
    )
    file_name: str = AirweaveField(..., description="Name of the file", embeddable=True)
    message: str = AirweaveField(..., description="Content of the comment", embeddable=True)
    created_by: Dict = AirweaveField(
        ..., description="User who created this comment", embeddable=True
    )
    is_reply_comment: bool = AirweaveField(
        False, description="Whether this comment is a reply to another comment", embeddable=False
    )
    tagged_message: Optional[str] = AirweaveField(
        None,
        description="Tagged version of the message with user mentions",
        embeddable=True,
    )


class BoxCollaborationEntity(BaseEntity):
    """Schema for Box collaboration entities.

    Reference:
        https://developer.box.com/reference/resources/collaboration/
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the Box collaboration ID)
    # - breadcrumbs (folder/file breadcrumbs)
    # - name (from role and accessible_by info)
    # - created_at (from created_at timestamp)
    # - updated_at (from modified_at timestamp)

    # API fields
    role: str = AirweaveField(
        ...,
        description="Role of the collaborator (editor, viewer, previewer, etc.)",
        embeddable=True,
    )
    accessible_by: Dict = AirweaveField(
        ...,
        description="User or group that this collaboration applies to",
        embeddable=True,
    )
    item: Dict = AirweaveField(
        ..., description="File or folder that is being collaborated on", embeddable=True
    )
    item_id: str = AirweaveField(
        ..., description="ID of the item being collaborated on", embeddable=False
    )
    item_type: str = AirweaveField(
        ..., description="Type of the item (file or folder)", embeddable=True
    )
    item_name: str = AirweaveField(
        ..., description="Name of the item being collaborated on", embeddable=True
    )
    status: str = AirweaveField(
        ..., description="Status of the collaboration (accepted, pending, etc.)", embeddable=True
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created this collaboration", embeddable=True
    )
    expires_at: Optional[Any] = AirweaveField(
        None, description="When this collaboration expires", embeddable=False
    )
    is_access_only: Optional[bool] = AirweaveField(
        None, description="Whether this is an access-only collaboration", embeddable=False
    )
    invite_email: Optional[str] = AirweaveField(
        None, description="Email address invited to collaborate", embeddable=True
    )
    acknowledged_at: Optional[Any] = AirweaveField(
        None, description="When the collaboration was acknowledged", embeddable=False
    )
