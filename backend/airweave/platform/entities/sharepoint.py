"""SharePoint entity schemas.

Entity schemas for SharePoint objects based on Microsoft Graph API:
 - User
 - Group
 - Site
 - Drive (document library)
 - DriveItem (file/folder)

Reference:
  https://learn.microsoft.com/en-us/graph/api/resources/sharepoint
  https://learn.microsoft.com/en-us/graph/api/resources/site
  https://learn.microsoft.com/en-us/graph/api/resources/drive
  https://learn.microsoft.com/en-us/graph/api/resources/driveitem
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import FileEntity


class SharePointUserEntity(BaseEntity):
    """Schema for a SharePoint user.

    Based on the Microsoft Graph user resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/user
    """

    display_name: Optional[str] = AirweaveField(
        None, description="The name displayed in the address book for the user.", embeddable=True
    )
    user_principal_name: Optional[str] = AirweaveField(
        None,
        description="The user principal name (UPN) of the user (e.g., user@contoso.com).",
        embeddable=True,
    )
    mail: Optional[str] = AirweaveField(
        None, description="The SMTP address for the user.", embeddable=True
    )
    job_title: Optional[str] = AirweaveField(
        None, description="The user's job title.", embeddable=True
    )
    department: Optional[str] = AirweaveField(
        None, description="The department in which the user works.", embeddable=True
    )
    office_location: Optional[str] = AirweaveField(
        None, description="The office location in the user's place of business.", embeddable=True
    )
    mobile_phone: Optional[str] = AirweaveField(
        None, description="The primary cellular telephone number for the user."
    )
    business_phones: Optional[List[str]] = AirweaveField(
        None, description="The telephone numbers for the user."
    )
    account_enabled: Optional[bool] = AirweaveField(
        None, description="Whether the account is enabled."
    )


class SharePointGroupEntity(BaseEntity):
    """Schema for a SharePoint group.

    Based on the Microsoft Graph group resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/group
    """

    display_name: Optional[str] = AirweaveField(
        None, description="The display name for the group.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="An optional description for the group.", embeddable=True
    )
    mail: Optional[str] = AirweaveField(
        None, description="The SMTP address for the group.", embeddable=True
    )
    mail_enabled: Optional[bool] = AirweaveField(
        None, description="Whether the group is mail-enabled."
    )
    security_enabled: Optional[bool] = AirweaveField(
        None, description="Whether the group is a security group."
    )
    group_types: List[str] = AirweaveField(
        default_factory=list,
        description="Specifies the group type (e.g., 'Unified' for Microsoft 365 groups).",
        embeddable=True,
    )
    visibility: Optional[str] = AirweaveField(
        None,
        description="Visibility of the group (Public, Private, HiddenMembership).",
        embeddable=True,
    )
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Timestamp when the group was created.",
        is_created_at=True,
        embeddable=True,
    )


class SharePointSiteEntity(BaseEntity):
    """Schema for a SharePoint site.

    Based on the Microsoft Graph site resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/site
    """

    display_name: Optional[str] = AirweaveField(
        None, description="The full title for the site.", embeddable=True
    )
    name: Optional[str] = AirweaveField(
        None, description="The name/title of the site.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="The descriptive text for the site.", embeddable=True
    )
    web_url: Optional[str] = AirweaveField(
        None, description="URL that displays the site in the browser."
    )
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Date and time the site was created.",
        is_created_at=True,
        embeddable=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Date and time the site was last modified.",
        is_updated_at=True,
        embeddable=True,
    )
    is_personal_site: Optional[bool] = AirweaveField(
        None, description="Whether the site is a personal site."
    )
    site_collection: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Details about the site's site collection."
    )


class SharePointDriveEntity(BaseEntity):
    """Schema for a SharePoint drive (document library).

    Based on the Microsoft Graph drive resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/drive
    """

    name: Optional[str] = AirweaveField(None, description="The name of the drive.", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="User-visible description of the drive.", embeddable=True
    )
    drive_type: Optional[str] = AirweaveField(
        None,
        description="Type of drive (documentLibrary, business, etc.).",
        embeddable=True,
    )
    web_url: Optional[str] = AirweaveField(None, description="URL to view the drive in a browser.")
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Date and time the drive was created.",
        is_created_at=True,
        embeddable=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Date and time the drive was last modified.",
        is_updated_at=True,
        embeddable=True,
    )
    owner: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the drive's owner.", embeddable=True
    )
    quota: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the drive's storage quota."
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this drive."
    )


class SharePointDriveItemEntity(FileEntity):
    """Schema for a SharePoint drive item (file or folder).

    Based on the Microsoft Graph driveItem resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/driveitem
    """

    name: str = AirweaveField(
        ..., description="The name of the item (file or folder).", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="User-visible description of the item.", embeddable=True
    )
    web_url: Optional[str] = AirweaveField(
        None, description="URL to display the item in a browser."
    )
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Date and time the item was created.",
        is_created_at=True,
        embeddable=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Date and time the item was last modified.",
        is_updated_at=True,
        embeddable=True,
    )
    size: Optional[int] = AirweaveField(None, description="Size of the item in bytes.")
    file: Optional[Dict[str, Any]] = AirweaveField(
        None, description="File metadata if the item is a file (e.g., mimeType, hashes)."
    )
    folder: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Folder metadata if the item is a folder (e.g., childCount)."
    )
    parent_reference: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the parent of this item (driveId, path, etc)."
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the item.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who last modified the item.", embeddable=True
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this item."
    )
    drive_id: Optional[str] = AirweaveField(
        None, description="ID of the drive that contains this item."
    )


class SharePointListEntity(BaseEntity):
    """Schema for a SharePoint list.

    Based on the Microsoft Graph list resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/list
    """

    display_name: Optional[str] = AirweaveField(
        None, description="The displayable title of the list.", embeddable=True
    )
    name: Optional[str] = AirweaveField(None, description="The name of the list.", embeddable=True)
    description: Optional[str] = AirweaveField(
        None, description="The description of the list.", embeddable=True
    )
    web_url: Optional[str] = AirweaveField(None, description="URL to view the list in browser.")
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Date and time the list was created.",
        is_created_at=True,
        embeddable=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Date and time the list was last modified.",
        is_updated_at=True,
        embeddable=True,
    )
    list_info: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Additional list metadata (template, hidden, etc)."
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this list."
    )


class SharePointListItemEntity(BaseEntity):
    """Schema for a SharePoint list item.

    Based on the Microsoft Graph listItem resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/listitem
    """

    fields: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="The values of the columns set on this list item (dynamic schema).",
        embeddable=True,
    )
    content_type: Optional[Dict[str, Any]] = AirweaveField(
        None, description="The content type of this list item."
    )
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Date and time the item was created.",
        is_created_at=True,
        embeddable=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Date and time the item was last modified.",
        is_updated_at=True,
        embeddable=True,
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the item.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who last modified the item.", embeddable=True
    )
    web_url: Optional[str] = AirweaveField(None, description="URL to view the item in browser.")
    list_id: Optional[str] = AirweaveField(
        None, description="ID of the list that contains this item."
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this item."
    )


class SharePointPageEntity(BaseEntity):
    """Schema for a SharePoint site page.

    Based on the Microsoft Graph sitePage resource.
    Reference: https://learn.microsoft.com/en-us/graph/api/resources/sitepage
    """

    title: Optional[str] = AirweaveField(
        None, description="The title of the page.", embeddable=True
    )
    name: Optional[str] = AirweaveField(None, description="The name of the page.", embeddable=True)
    content: Optional[str] = AirweaveField(
        None,
        description="The actual page content (extracted from webParts).",
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="Description or summary of the page content.", embeddable=True
    )
    page_layout: Optional[str] = AirweaveField(
        None, description="The layout type of the page (article, home, etc).", embeddable=True
    )
    web_url: Optional[str] = AirweaveField(None, description="URL to view the page in browser.")
    created_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Date and time the page was created.",
        is_created_at=True,
        embeddable=True,
    )
    last_modified_datetime: Optional[datetime] = AirweaveField(
        None,
        description="Date and time the page was last modified.",
        is_updated_at=True,
        embeddable=True,
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the page.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who last modified the page.", embeddable=True
    )
    publishing_state: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Publishing status of the page."
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this page."
    )
