from datetime import datetime
from typing import Optional, List
from pydantic import Field

from ._base import BaseEntity, ChunkEntity, Breadcrumb


class EvernoteNote(ChunkEntity):
    """Schema for Evernote notes."""

    title: str = Field(..., description="Title of the note")
    content: str = Field(..., description="Content of the note in ENML format")
    created: datetime = Field(..., description="Creation timestamp")
    updated: datetime = Field(..., description="Last update timestamp")
    notebook_guid: str = Field(..., description="GUID of the notebook this note belongs to")
    tag_guids: List[str] = Field(default_factory=list, description="List of tag GUIDs")
    attributes: Optional[dict] = Field(None, description="Additional note attributes")


class EvernoteNotebook(ChunkEntity):
    """Schema for Evernote notebooks."""

    name: str = Field(..., description="Name of the notebook")
    stack: Optional[str] = Field(None, description="Stack name if notebook is in a stack")
    created: datetime = Field(..., description="Creation timestamp")
    updated: datetime = Field(..., description="Last update timestamp")
    shared: bool = Field(default=False, description="Whether the notebook is shared")


class EvernoteTag(ChunkEntity):
    """Schema for Evernote tags."""

    name: str = Field(..., description="Name of the tag")
    parent_guid: Optional[str] = Field(None, description="GUID of the parent tag if nested")
    update_sequence_num: int = Field(..., description="Update sequence number for sync") 