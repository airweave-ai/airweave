"""SharePoint 2019 On-Premise entity schemas.

Entity schemas for SharePoint 2019 On-Premise objects using REST API:
 - List (document library or custom list)
 - ListItem (item within a list, can be a file or data row)
 - File (downloadable document within a list)

Reference:
  SharePoint 2019 REST API: https://docs.microsoft.com/en-us/sharepoint/dev/sp-add-ins/get-to-know-the-sharepoint-rest-service
  SharePoint 2019 uses OData v3 (different from Microsoft Graph)
"""

from typing import Any, Dict, List, Optional

from pydantic import computed_field

from airweave.platform.entities._airweave_field import AirweaveField
from airweave.platform.entities._base import BaseEntity, FileEntity


class SharePoint2019ListEntity(BaseEntity):
    """Schema for a SharePoint 2019 list or document library.
    
    Lists are containers for data in SharePoint. Document libraries are
    a specialized type of list (BaseTemplate=101) that stores files.
    
    Reference:
        https://docs.microsoft.com/en-us/sharepoint/dev/sp-add-ins/working-with-lists-and-list-items-with-rest
    """
    
    id: str = AirweaveField(
        ...,
        description="List ID (GUID).",
        is_entity_id=True,
    )
    title: str = AirweaveField(
        ...,
        description="The displayable title of the list.",
        embeddable=True,
        is_name=True,
    )
    description: Optional[str] = AirweaveField(
        None, description="The description of the list.", embeddable=True
    )
    base_template: Optional[int] = AirweaveField(
        None, 
        description="The base template type (101=Document Library, 100=Generic List).", 
        embeddable=False
    )
    item_count: Optional[int] = AirweaveField(
        None, description="Number of items in the list.", embeddable=False
    )
    server_relative_url: Optional[str] = AirweaveField(
        None, description="Server-relative URL of the list.", embeddable=False
    )
    enable_versioning: Optional[bool] = AirweaveField(
        None, description="Whether versioning is enabled.", embeddable=False
    )
    hidden: Optional[bool] = AirweaveField(
        None, description="Whether the list is hidden.", embeddable=False
    )
    
    # Store raw API response for additional metadata
    raw_metadata: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Raw API response metadata.", embeddable=False
    )
    
    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct web URL to view the list in browser."""
        if self.server_relative_url:
            # server_relative_url already includes the site path
            return f"{{site_url}}{self.server_relative_url}"
        return "{site_url}"


class SharePoint2019ListItemEntity(BaseEntity):
    """Schema for a SharePoint 2019 list item.
    
    List items are rows of data within a list. They have dynamic fields
    based on the list's column configuration.
    
    Reference:
        https://docs.microsoft.com/en-us/sharepoint/dev/sp-add-ins/working-with-lists-and-list-items-with-rest
    """
    
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
        description="The values of the columns in this list item (dynamic schema).",
        embeddable=True,
    )
    content_type_id: Optional[str] = AirweaveField(
        None, description="The content type ID of this list item.", embeddable=False
    )
    file_system_object_type: Optional[int] = AirweaveField(
        None, 
        description="Type: 0=File, 1=Folder, 2=Web.", 
        embeddable=False
    )
    server_relative_url: Optional[str] = AirweaveField(
        None, description="Server-relative URL of the item.", embeddable=False
    )
    
    # References to parent containers
    list_id: Optional[str] = AirweaveField(
        None, description="ID of the list that contains this item.", embeddable=False
    )
    
    # Store raw API response for additional metadata
    raw_metadata: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Raw API response metadata.", embeddable=False
    )
    
    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct web URL to view the item in browser."""
        if self.list_id and self.id:
            return f"{{site_url}}/Lists/{{list_name}}/DispForm.aspx?ID={self.id}"
        return "{site_url}"


class SharePoint2019FileEntity(FileEntity):
    """Schema for a SharePoint 2019 file (document).
    
    Files in SharePoint 2019 are stored as list items in document libraries.
    This entity represents the file itself with download capabilities.
    
    Reference:
        https://docs.microsoft.com/en-us/sharepoint/dev/sp-add-ins/working-with-files-and-folders-with-rest
    """
    
    id: str = AirweaveField(
        ...,
        description="File's unique ID.",
        is_entity_id=True,
    )
    name: str = AirweaveField(
        ...,
        description="File name with extension.",
        embeddable=True,
        is_name=True,
    )
    title: Optional[str] = AirweaveField(
        None,
        description="Display title of the file (from list item Title field).",
        embeddable=True,
    )
    server_relative_url: str = AirweaveField(
        ...,
        description="Server-relative URL of the file (used for download).",
        embeddable=False,
    )
    length: Optional[int] = AirweaveField(
        None, description="File size in bytes.", embeddable=False
    )
    time_created: Optional[str] = AirweaveField(
        None, description="ISO timestamp when file was created.", embeddable=False
    )
    time_last_modified: Optional[str] = AirweaveField(
        None, description="ISO timestamp when file was last modified.", embeddable=False
    )
    
    # List item metadata (files are list items)
    list_item_id: Optional[int] = AirweaveField(
        None, description="ID of the associated list item.", embeddable=False
    )
    list_id: Optional[str] = AirweaveField(
        None, description="ID of the list that contains this file.", embeddable=False
    )
    
    # Author/Editor information
    author: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who created the file.", embeddable=True
    )
    modified_by: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who last modified the file.", embeddable=True
    )
    
    # Check out status
    checked_out_by_user: Optional[Dict[str, Any]] = AirweaveField(
        None, description="User who has checked out the file (if any).", embeddable=False
    )
    check_out_type: Optional[int] = AirweaveField(
        None, description="Check out type (0=None, 1=Online, 2=Offline).", embeddable=False
    )
    
    # Store raw API response for additional metadata
    raw_metadata: Optional[Dict[str, Any]] = AirweaveField(
        None, description="Raw API response metadata.", embeddable=False
    )
    
    @computed_field(return_type=str)
    def web_url(self) -> str:
        """Construct web URL to view/download the file."""
        if self.server_relative_url:
            return f"{{site_url}}{self.server_relative_url}"
        return "{site_url}"

