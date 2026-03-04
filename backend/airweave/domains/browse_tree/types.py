"""Pydantic schemas for browse tree domain."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class DataTreeNodeResponse(BaseModel):
    """Response schema for a single data tree node."""

    id: UUID
    source_connection_id: UUID
    parent_id: Optional[UUID] = None
    node_type: str
    source_node_id: str
    title: str
    description: Optional[str] = None
    item_count: Optional[int] = None
    node_metadata: Optional[Dict[str, Any]] = None
    is_public: bool = False
    has_children: bool = False

    model_config = {"from_attributes": True}


class BrowseTreeResponse(BaseModel):
    """Response schema for browse tree listing."""

    nodes: List[DataTreeNodeResponse]
    parent_id: Optional[UUID] = None
    total: int


class MetadataSyncResponse(BaseModel):
    """Response after triggering a metadata sync."""

    sync_job_id: UUID
    message: str = "Metadata sync started"


class AclSyncResponse(BaseModel):
    """Response after triggering an ACL-only sync."""

    sync_job_id: UUID
    message: str = "ACL sync started"


class DataTreeNodeCreate(BaseModel):
    """Schema for creating/upserting a data tree node row."""

    id: UUID
    organization_id: UUID
    source_connection_id: UUID
    parent_id: Optional[UUID] = None
    node_type: str
    source_node_id: str
    title: str
    description: Optional[str] = None
    item_count: Optional[int] = None
    node_metadata: Optional[Dict[str, Any]] = None
    access_viewers: Optional[List[str]] = None
    is_public: bool = False


class NodeSelectionData(BaseModel):
    """Typed representation of a node selection loaded for targeted sync."""

    source_node_id: str
    node_type: str
    node_title: Optional[str] = None
    node_metadata: Optional[Dict[str, Any]] = None


class NodeSelectionCreate(BaseModel):
    """Request schema for creating a node selection."""

    source_node_id: str = Field(..., description="Matches DataTreeNode.source_node_id")
    node_type: str = Field(..., description="site/list/folder/file/item")
    node_title: Optional[str] = Field(None, description="Display snapshot")
    node_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Metadata for targeted fetch (site_url, list_id, etc.)"
    )


class NodeSelectionRequest(BaseModel):
    """Request body for selecting nodes."""

    admin_source_connection_id: UUID = Field(
        ..., description="Admin SC that owns the browse tree (DataTreeNode rows)"
    )
    source_node_ids: List[str] = Field(..., description="Source node IDs to select")


class NodeSelectionResponse(BaseModel):
    """Response after submitting node selections and triggering sync."""

    source_connection_id: UUID = Field(..., description="User's source connection ID")
    selections_count: int
    sync_job_id: UUID = Field(..., description="ID of the triggered sync job")
    message: str = "Node selections saved and sync triggered"
