"""
Zoho CRM entity definitions for Airweave.

This module defines schemas for Zoho CRM entities including:
- Modules
- Records
- Notes

References:
    https://www.zoho.com/crm/developer/docs/api/v2/modules-api.html
    https://www.zoho.com/crm/developer/docs/api/v2/records-api.html
    https://www.zoho.com/crm/developer/docs/api/v2/notes-api.html
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field

from airweave.platform.entities._base import Breadcrumb, ChunkEntity


class ZohoCRMModuleEntity(ChunkEntity):
    """Zoho CRM module entity."""

    entity_id: str = Field(..., description="Unique Entity ID")
    module_id: str = Field(..., description="Module API name (e.g., 'Leads', 'Accounts', 'Deals')")
    module_name: str = Field(..., description="Singular display name of the module (e.g., 'Lead')")
    plural_label: str = Field(..., description="Plural display name of the module (e.g., 'Leads')")
    is_custom: bool = Field(False, description="Whether the module is custom")
    is_global_search_supported: bool = Field(
        False, description="Whether the module supports global search"
    )
    record_count: Optional[int] = Field(None, description="Number of records in the module")
    created_at: Optional[datetime] = Field(None, description="Timestamp when the module was created")
    modified_at: Optional[datetime] = Field(
        None, description="Timestamp when the module was last modified"
    )


class ZohoCRMRecordEntity(ChunkEntity):
    """Zoho CRM record entity."""

    entity_id: str = Field(..., description="Unique Entity ID")
    breadcrumbs: List[Breadcrumb] = Field(
        default_factory=list, description="Breadcrumb hierarchy (e.g., parent module)"
    )
    module_id: str = Field(..., description="Parent module API name (e.g., 'Leads', 'Accounts')")
    record_id: str = Field(..., description="Record ID within the module")
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Key-value pairs of record fields (e.g., 'First_Name', 'Email')"
    )
    owner: Optional[Dict[str, Any]] = Field(
        None, description="Information about the record owner (e.g., user ID and name)"
    )
    created_by: Optional[Dict[str, Any]] = Field(
        None, description="Information about the user who created the record"
    )
    modified_by: Optional[Dict[str, Any]] = Field(
        None, description="Information about the user who last modified the record"
    )
    created_at: Optional[datetime] = Field(None, description="Timestamp when the record was created")
    modified_at: Optional[datetime] = Field(
        None, description="Timestamp when the record was last modified"
    )
    has_notes: bool = Field(False, description="Whether the record has associated notes")
    notes_count: Optional[int] = Field(None, description="Number of notes associated with the record")


class ZohoCRMNoteEntity(ChunkEntity):
    """Zoho CRM note entity."""

    entity_id: str = Field(..., description="Unique Entity ID")
    breadcrumbs: List[Breadcrumb] = Field(
        default_factory=list, description="Breadcrumb hierarchy (e.g., parent module and record)"
    )
    note_id: str = Field(..., description="Note ID")
    module_id: str = Field(..., description="Parent module API name (e.g., 'Leads', 'Accounts')")
    record_id: str = Field(..., description="Parent record ID")
    note_content: str = Field("", description="Text content of the note")
    created_by: Optional[Dict[str, Any]] = Field(
        None, description="Information about the user who created the note"
    )
    modified_by: Optional[Dict[str, Any]] = Field(
        None, description="Information about the user who last modified the note"
    )
    created_at: Optional[datetime] = Field(None, description="Timestamp when the note was created")
    modified_at: Optional[datetime] = Field(
        None, description="Timestamp when the note was last modified"
    )