"""Box entity schemas."""

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base_legacy import ChunkEntity, FileEntity


class BoxUserEntity(ChunkEntity):
    """Schema for Box user entities."""

    name: str = AirweaveField(..., description="Display name of the user", embeddable=True)
    box_id: str = Field(..., description="Unique Box ID of the user")
    login: Optional[str] = AirweaveField(
        None, description="Login email address of the user", embeddable=True
    )
    status: Optional[str] = AirweaveField(
        None, description="Status of the user (active, inactive, etc.)", embeddable=True
    )
    job_title: Optional[str] = AirweaveField(
        None, description="Job title of the user", embeddable=True
    )
    phone: Optional[str] = AirweaveField(
        None, description="Phone number of the user", embeddable=True
    )
    address: Optional[str] = AirweaveField(None, description="Address of the user", embeddable=True)
    language: Optional[str] = AirweaveField(
        None, description="Language of the user", embeddable=True
    )
    timezone: Optional[str] = AirweaveField(
        None, description="Timezone of the user", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When this user was created",
        embeddable=True,
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When this user was last modified",
        embeddable=True,
        is_updated_at=True,
    )
    space_amount: Optional[int] = Field(
        None, description="Total storage space available to the user in bytes"
    )
    space_used: Optional[int] = Field(None, description="Storage space used by the user in bytes")
    max_upload_size: Optional[int] = Field(
        None, description="Maximum file size the user can upload in bytes"
    )
    avatar_url: Optional[str] = Field(None, description="URL to the user's avatar image")


class BoxFolderEntity(ChunkEntity):
    """Schema for Box folder entities."""

    name: str = AirweaveField(..., description="Name of the folder", embeddable=True)
    box_id: str = Field(..., description="Unique Box ID of the folder")
    description: Optional[str] = AirweaveField(
        None, description="Description of the folder", embeddable=True
    )
    size: Optional[int] = Field(None, description="Size of the folder in bytes")
    path_collection: List[Dict] = AirweaveField(
        default_factory=list,
        description="Path of parent folders from root to this folder",
        embeddable=True,
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When this folder was created",
        embeddable=True,
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When this folder was last modified",
        embeddable=True,
        is_updated_at=True,
    )
    content_created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the content in this folder was originally created",
        embeddable=True,
    )
    content_modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the content in this folder was last modified",
        embeddable=True,
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
    parent_id: Optional[str] = Field(None, description="ID of the parent folder")
    parent_name: Optional[str] = AirweaveField(
        None, description="Name of the parent folder", embeddable=True
    )
    item_status: Optional[str] = AirweaveField(
        None,
        description="Status of the folder (active, trashed, deleted)",
        embeddable=True,
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
    has_collaborations: Optional[bool] = Field(
        None, description="Whether this folder has collaborations"
    )
    permissions: Optional[Dict] = Field(
        None, description="Permissions the current user has on this folder"
    )
    permalink_url: Optional[str] = Field(None, description="Direct link to view the folder in Box")
    etag: Optional[str] = Field(None, description="Entity tag for versioning")
    sequence_id: Optional[str] = Field(
        None, description="Sequence ID for the most recent user event"
    )


class BoxFileEntity(FileEntity):
    """Schema for Box file entities.

    Uses FileEntity base class which provides:
    - file_id: Unique identifier for the file
    - name: Name of the file
    - mime_type: MIME type
    - size: File size in bytes
    - download_url: URL to download the file
    """

    box_id: str = Field(..., description="Unique Box ID of the file")
    description: Optional[str] = AirweaveField(
        None, description="Description of the file", embeddable=True
    )
    parent_folder_id: str = Field(..., description="ID of the parent folder")
    parent_folder_name: str = AirweaveField(
        ..., description="Name of the parent folder", embeddable=True
    )
    path_collection: List[Dict] = AirweaveField(
        default_factory=list,
        description="Path of parent folders from root to this file",
        embeddable=True,
    )
    sha1: Optional[str] = Field(None, description="SHA1 hash of the file contents")
    extension: Optional[str] = AirweaveField(None, description="File extension", embeddable=True)
    version_number: Optional[str] = AirweaveField(
        None, description="Version number of the file", embeddable=True
    )
    comment_count: Optional[int] = Field(None, description="Number of comments on this file")
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When this file was created in Box",
        embeddable=True,
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When this file was last modified in Box",
        embeddable=True,
        is_updated_at=True,
    )
    content_created_at: Optional[datetime] = AirweaveField(
        None,
        description="When the content of this file was originally created",
        embeddable=True,
    )
    content_modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When the content of this file was last modified",
        embeddable=True,
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
        None, description="Status of the file (active, trashed, deleted)", embeddable=True
    )
    shared_link: Optional[Dict] = AirweaveField(
        None, description="Shared link information for this file", embeddable=True
    )
    tags: List[str] = AirweaveField(
        default_factory=list, description="Tags associated with this file", embeddable=True
    )
    has_collaborations: Optional[bool] = Field(
        None, description="Whether this file has collaborations"
    )
    permissions: Optional[Dict] = Field(
        None, description="Permissions the current user has on this file"
    )
    lock: Optional[Dict] = AirweaveField(
        None, description="Lock information if the file is locked", embeddable=True
    )
    permalink_url: Optional[str] = Field(None, description="Direct link to view the file in Box")
    etag: Optional[str] = Field(None, description="Entity tag for versioning")
    sequence_id: Optional[str] = Field(
        None, description="Sequence ID for the most recent user event"
    )


class BoxCommentEntity(ChunkEntity):
    """Schema for Box comment entities."""

    box_id: str = Field(..., description="Unique Box ID of the comment")
    file_id: str = Field(..., description="ID of the file this comment is on")
    file_name: str = AirweaveField(..., description="Name of the file", embeddable=True)
    message: str = AirweaveField(..., description="Content of the comment", embeddable=True)
    created_by: Dict = AirweaveField(
        ..., description="User who created this comment", embeddable=True
    )
    created_at: datetime = AirweaveField(
        ...,
        description="When this comment was created",
        embeddable=True,
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When this comment was last modified",
        embeddable=True,
        is_updated_at=True,
    )
    is_reply_comment: bool = Field(
        False, description="Whether this comment is a reply to another comment"
    )
    tagged_message: Optional[str] = AirweaveField(
        None,
        description="Tagged version of the message with user mentions",
        embeddable=True,
    )


class BoxCollaborationEntity(ChunkEntity):
    """Schema for Box collaboration entities."""

    box_id: str = Field(..., description="Unique Box ID of the collaboration")
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
    item_id: str = Field(..., description="ID of the item being collaborated on")
    item_type: str = AirweaveField(
        ..., description="Type of the item (file or folder)", embeddable=True
    )
    item_name: str = AirweaveField(
        ..., description="Name of the item being collaborated on", embeddable=True
    )
    status: str = AirweaveField(
        ..., description="Status of the collaboration (accepted, pending, etc.)", embeddable=True
    )
    created_at: Optional[datetime] = AirweaveField(
        None,
        description="When this collaboration was created",
        embeddable=True,
        is_created_at=True,
    )
    modified_at: Optional[datetime] = AirweaveField(
        None,
        description="When this collaboration was last modified",
        embeddable=True,
        is_updated_at=True,
    )
    created_by: Optional[Dict] = AirweaveField(
        None, description="User who created this collaboration", embeddable=True
    )
    expires_at: Optional[datetime] = AirweaveField(
        None, description="When this collaboration expires", embeddable=True
    )
    is_access_only: Optional[bool] = Field(
        None, description="Whether this is an access-only collaboration"
    )
    invite_email: Optional[str] = AirweaveField(
        None, description="Email address invited to collaborate", embeddable=True
    )
    acknowledged_at: Optional[datetime] = AirweaveField(
        None, description="When the collaboration was acknowledged", embeddable=True
    )
