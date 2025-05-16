"""
Salesforce entity definitions for Airweave.

This module defines schemas for Salesforce entities including:
- Objects
- Records
- Notes

References:
    https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_sobjects.htm
    https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_sobject_basic_info.htm
    https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/resources_sobject_note.htm
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import Breadcrumb, ChunkEntity


class SalesforceObjectEntity(ChunkEntity):
    """Salesforce object entity."""

    entity_id: str = Field(..., description="Unique Entity ID")
    object_name: str = Field(..., description="Object API name (e.g., 'Account', 'Contact', 'Opportunity')")
    label: str = Field(..., description="Display label of the object (e.g., 'Account')")
    label_plural: str = Field(..., description="Plural display label of the object (e.g., 'Accounts')")
    is_custom: bool = Field(False, description="Whether the object is custom")
    is_searchable: bool = Field(False, description="Whether the object supports search")
    record_count: Optional[int] = Field(None, description="Number of records in the object")
    created_date: Optional[datetime] = Field(None, description="Timestamp when the object was created")
    last_modified_date: Optional[datetime] = Field(
        None, description="Timestamp when the object was last modified"
    )


class SalesforceRecordEntity(ChunkEntity):
    """Salesforce record entity."""

    entity_id: str = Field(..., description="Unique Entity ID")
    breadcrumbs: List[Breadcrumb] = Field(
        default_factory=list, description="Breadcrumb hierarchy (e.g., parent object)"
    )
    object_name: str = Field(..., description="Parent object API name (e.g., 'Account', 'Opportunity')")
    record_id: str = Field(..., description="Record ID within the object")
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Key-value pairs of record fields (e.g., 'Name', 'Email')"
    )
    owner_id: Optional[str] = Field(
        None, description="ID of the user who owns the record"
    )
    created_by_id: Optional[str] = Field(
        None, description="ID of the user who created the record"
    )
    last_modified_by_id: Optional[str] = Field(
        None, description="ID of the user who last modified the record"
    )
    created_date: Optional[datetime] = Field(None, description="Timestamp when the record was created")
    last_modified_date: Optional[datetime] = Field(
        None, description="Timestamp when the record was last modified"
    )
    has_notes: bool = Field(False, description="Whether the record has associated notes")


class SalesforceNoteEntity(ChunkEntity):
    """Salesforce note entity."""

    entity_id: str = Field(..., description="Unique Entity ID")
    breadcrumbs: List[Breadcrumb] = Field(
        default_factory=list, description="Breadcrumb hierarchy (e.g., parent object and record)"
    )
    note_id: str = Field(..., description="Note ID")
    object_name: str = Field(..., description="Parent object API name (e.g., 'Account', 'Opportunity')")
    record_id: str = Field(..., description="Parent record ID")
    title: Optional[str] = Field(None, description="Title of the note")
    body: str = Field("", description="Content of the note")
    owner_id: Optional[str] = Field(
        None, description="ID of the user who owns the note"
    )
    created_by_id: Optional[str] = Field(
        None, description="ID of the user who created the note"
    )
    last_modified_by_id: Optional[str] = Field(
        None, description="ID of the user who last modified the note"
    )
    created_date: Optional[datetime] = Field(None, description="Timestamp when the note was created")
    last_modified_date: Optional[datetime] = Field(
        None, description="Timestamp when the note was last modified"
    )
    is_private: bool = Field(False, description="Whether the note is private")