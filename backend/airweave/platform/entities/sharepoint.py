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

from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


class SharePointUserEntity(BaseEntity):
    """Schema for a SharePoint user.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/user
    """

    id: str = AirweaveField(
        ...,
        description="SharePoint user ID.",
        is_entity_id=True,
    )
    display_name: str = AirweaveField(
        ...,
        description="The name displayed in the address book for the user.",
        embeddable=True,
        is_name=True,
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
        None, description="The primary cellular telephone number for the user.", embeddable=False
    )
    business_phones: Optional[List[str]] = AirweaveField(
        None, description="The telephone numbers for the user.", embeddable=False
    )
    account_enabled: Optional[bool] = AirweaveField(
        None, description="Whether the account is enabled.", embeddable=False
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="Link to the user's profile in SharePoint.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        """URL that opens the SharePoint user profile or mailto link."""
        if self.web_url_override:
            return self.web_url_override
        if self.mail:
            return f"mailto:{self.mail}"
        return "https://sharepoint.com/"


class SharePointGroupEntity(BaseEntity):
    """Schema for a SharePoint group.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/group
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the group ID)
    # - breadcrumbs (empty - groups are top-level)
    # - name (from display_name)
    # - created_at (from createdDateTime)
    # - updated_at (None - groups don't have update timestamp)

    # API fields
    id: str = AirweaveField(
        ...,
        description="Group ID.",
        is_entity_id=True,
    )
    display_name: str = AirweaveField(
        ...,
        description="The display name for the group.",
        embeddable=True,
        is_name=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="An optional description for the group.", embeddable=True
    )
    mail: Optional[str] = AirweaveField(
        None, description="The SMTP address for the group.", embeddable=True
    )
    mail_enabled: Optional[bool] = AirweaveField(
        None, description="Whether the group is mail-enabled.", embeddable=False
    )
    security_enabled: Optional[bool] = AirweaveField(
        None, description="Whether the group is a security group.", embeddable=False
    )
    group_types: List[str] = AirweaveField(
        default_factory=list,
        description="Specifies the group type (e.g., 'Unified' for Microsoft 365 groups).",
        embeddable=True,
    )
    visibility: Optional[str] = AirweaveField(
        None,
        description="Visibility of the group (Public, Private, HiddenMembership).",
        embeddable=False,
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="Link to the group in Microsoft 365.",
        embeddable=False,
        unhashable=True,
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        if self.web_url_override:
            return self.web_url_override
        return f"https://outlook.office.com/groups/{self.id}"


class SharePointSiteEntity(BaseEntity):
    """Schema for a SharePoint site.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/site
    """

    id: str = AirweaveField(
        ...,
        description="Site ID from Microsoft Graph.",
        is_entity_id=True,
    )
    display_name: str = AirweaveField(
        ...,
        description="The full title for the site.",
        embeddable=True,
        is_name=True,
    )
    site_name: Optional[str] = AirweaveField(
        None, description="The name/title of the site.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="The descriptive text for the site.", embeddable=True
    )
    web_url_override: Optional[str] = AirweaveField(
        None,
        description="URL that displays the site in the browser.",
        embeddable=False,
        unhashable=True,
    )
    is_personal_site: Optional[bool] = AirweaveField(
        None, description="Whether the site is a personal site.", embeddable=False
    )
    site_collection: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Details about the site's site collection.", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        if self.web_url_override:
            return self.web_url_override
        return f"https://sharepoint.com/sites/{self.id}"


class SharePointDriveEntity(BaseEntity):
    """Schema for a SharePoint drive (document library).

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/drive
    """

    id: str = AirweaveField(
        ...,
        description="Drive ID.",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Drive name.",
        embeddable=True,
        is_name=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="User-visible description of the drive.", embeddable=True
    )
    drive_type: Optional[str] = AirweaveField(
        None,
        description="Type of drive (documentLibrary, business, etc.).",
        embeddable=True,
    )
    web_url_override: Optional[str] = AirweaveField(
        None, description="URL to view the drive in a browser.", embeddable=False, unhashable=True
    )
    owner: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the drive's owner.", embeddable=True
    )
    quota: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Information about the drive's storage quota.", embeddable=False
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this drive.", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        if self.web_url_override:
            return self.web_url_override
        if self.site_id:
            return f"https://sharepoint.com/sites/{self.site_id}/_layouts/15/onedrive.aspx"
        return "https://onedrive.live.com/"


class SharePointDriveItemEntity(FileEntity):
    """Schema for a SharePoint drive item (file or folder).

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/driveitem
    """

    id: str = AirweaveField(
        ...,
        description="Drive item ID.",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="Graph item name.",
        embeddable=True,
        is_name=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="User-visible description of the item.", embeddable=True
    )
    web_url_override: Optional[str] = AirweaveField(
        None, description="URL to display the item in a browser.", embeddable=False
    )
    file: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="File metadata if the item is a file (e.g., mimeType, hashes).",
        embeddable=False,
    )
    folder: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Folder metadata if the item is a folder (e.g., childCount).",
        embeddable=False,
    )
    parent_reference: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="Information about the parent of this item (driveId, path, etc).",
        embeddable=False,
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the item.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who last modified the item.", embeddable=True
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this item.", embeddable=False
    )
    drive_id: Optional[str] = AirweaveField(
        None, description="ID of the drive that contains this item.", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        if self.web_url_override:
            return self.web_url_override
        return f"https://sharepoint.com/_layouts/15/Doc.aspx?sourcedoc={self.id}"


class SharePointListEntity(BaseEntity):
    """Schema for a SharePoint list.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/list
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the list ID)
    # - breadcrumbs (site breadcrumb)
    # - name (from display_name)
    # - created_at (from createdDateTime)
    # - updated_at (from lastModifiedDateTime)

    # API fields
    id: str = AirweaveField(
        ...,
        description="List ID.",
        is_entity_id=True,
    )
    display_name: str = AirweaveField(
        ...,
        description="The displayable title of the list.",
        embeddable=True,
        is_name=True,
    )
    list_name: Optional[str] = AirweaveField(
        None, description="The name of the list.", embeddable=True
    )
    description: Optional[str] = AirweaveField(
        None, description="The description of the list.", embeddable=True
    )
    web_url_override: Optional[str] = AirweaveField(
        None, description="URL to view the list in browser.", embeddable=False
    )
    list_info: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Additional list metadata (template, hidden, etc).", embeddable=False
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this list.", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        if self.web_url_override:
            return self.web_url_override
        if self.site_id:
            return f"https://sharepoint.com/sites/{self.site_id}/lists/{self.id}"
        return "https://sharepoint.com/"


class SharePointListItemEntity(BaseEntity):
    """Schema for a SharePoint list item.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/listitem
    """

    # Base fields are inherited and set during entity creation:
    # - entity_id (the list item ID)
    # - breadcrumbs (site and list breadcrumbs)
    # - name (from fields data or item ID)
    # - created_at (from createdDateTime)
    # - updated_at (from lastModifiedDateTime)

    # API fields
    id: str = AirweaveField(
        ...,
        description="List item ID.",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="Display title for the list item.",
        embeddable=True,
        is_name=True,
    )
    fields: Optional[Dict[str, Any]] = AirweaveField(
        None,
        description="The values of the columns set on this list item (dynamic schema).",
        embeddable=True,
    )
    content_type: Optional[Dict[str, Any]] = AirweaveField(
        None, description="The content type of this list item.", embeddable=False
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the item.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who last modified the item.", embeddable=True
    )
    web_url_override: Optional[str] = AirweaveField(
        None, description="URL to view the item in browser.", embeddable=False
    )
    list_id: Optional[str] = AirweaveField(
        None, description="ID of the list that contains this item.", embeddable=False
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this item.", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        if self.web_url_override:
            return self.web_url_override
        if self.site_id and self.list_id:
            return f"https://sharepoint.com/sites/{self.site_id}/lists/{self.list_id}/DispForm.aspx?ID={self.id}"
        return "https://sharepoint.com/"


class SharePointPageEntity(BaseEntity):
    """Schema for a SharePoint site page.

    Reference:
        https://learn.microsoft.com/en-us/graph/api/resources/sitepage
    """

    id: str = AirweaveField(
        ...,
        description="Page ID.",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="The title of the page.",
        embeddable=True,
        is_name=True,
    )
    page_name: Optional[str] = AirweaveField(
        None, description="The name of the page.", embeddable=True
    )
    content: Optional[str] = AirweaveField(
        None,
        description="The actual page content (extracted from webParts).",
        embeddable=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="Description or summary of the page content.", embeddable=True
    )
    page_layout: Optional[str] = AirweaveField(
        None, description="The layout type of the page (article, home, etc).", embeddable=False
    )
    web_url_override: Optional[str] = AirweaveField(
        None, description="URL to view the page in browser.", embeddable=False
    )
    created_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who created the page.", embeddable=True
    )
    last_modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Identity of the user who last modified the page.", embeddable=True
    )
    publishing_state: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Publishing status of the page.", embeddable=False
    )
    site_id: Optional[str] = AirweaveField(
        None, description="ID of the site that contains this page.", embeddable=False
    )

    @computed_field(return_type=str)
    def web_url(self) -> str:
        if self.web_url_override:
            return self.web_url_override
        if self.site_id:
            return f"https://sharepoint.com/sites/{self.site_id}/SitePages/{self.page_name or self.id}.aspx"
        return "https://sharepoint.com/"
