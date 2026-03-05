"""Pydantic schemas for browse tree domain."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class BrowseNode(BaseModel):
    """Source-agnostic browse tree node returned by source.get_browse_children()."""

    source_node_id: str  # unique ID within source (SP GUID, composite key, etc.)
    node_type: str  # site/list/folder/file/item
    title: str
    description: Optional[str] = None
    item_count: Optional[int] = None
    has_children: bool = False
    node_metadata: Optional[Dict[str, Any]] = None  # source-specific (url, base_template, etc.)


class BrowseTreeResponse(BaseModel):
    """API response for browse tree."""

    nodes: List[BrowseNode]
    parent_node_id: Optional[str] = None  # string (source node ID), not UUID
    total: int


class AclSyncResponse(BaseModel):
    """Response after triggering an ACL-only sync."""

    sync_job_id: UUID
    message: str = "ACL sync started"


class NodeSelectionData(BaseModel):
    """Typed representation of a node selection loaded for targeted sync."""

    source_node_id: str
    node_type: str
    node_title: Optional[str] = None
    node_metadata: Optional[Dict[str, Any]] = None


class NodeSelectionCreate(BaseModel):
    """Schema for creating a node selection."""

    source_node_id: str = Field(..., description="Source node ID from browse tree")
    node_type: str = Field(..., description="site/list/folder/file/item")
    node_title: Optional[str] = Field(None, description="Display snapshot")
    node_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Metadata for targeted fetch (site_url, list_id, etc.)"
    )


class NodeSelectionRequest(BaseModel):
    """Request body for selecting nodes."""

    source_node_ids: List[str] = Field(..., description="Source node IDs to select")


class NodeSelectionResponse(BaseModel):
    """Response after submitting node selections and triggering sync."""

    source_connection_id: UUID = Field(..., description="Source connection ID")
    selections_count: int
    sync_job_id: UUID = Field(..., description="ID of the triggered sync job")
    message: str = "Node selections saved and sync triggered"
