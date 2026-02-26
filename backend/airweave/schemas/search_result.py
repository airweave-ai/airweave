"""Internal search result schema for unified destination responses.

This module defines the AirweaveSearchResult schema that ensures both Qdrant
and Vespa destinations return identical payload structures. The schema is used
internally by destinations and serialized to dict for API responses.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BreadcrumbResult(BaseModel):
    """Breadcrumb in search result."""

    entity_id: str
    name: str
    entity_type: str


class AccessControlResult(BaseModel):
    """Access control info in search result."""

    is_public: bool = False
    viewers: List[str] = Field(default_factory=list)


class SystemMetadataResult(BaseModel):
    """System metadata in search result."""

    entity_type: str
    source_name: Optional[str] = None
    sync_id: Optional[str] = None
    sync_job_id: Optional[str] = None
    original_entity_id: Optional[str] = None
    chunk_index: Optional[int] = None


class AirweaveSearchResult(BaseModel):
    """Internal search result schema guaranteeing identical payloads.

    Used internally by destinations; serialized to dict for API response.
    This ensures Qdrant and Vespa return identical structures.

    The schema normalizes differences between destinations:
    - Vespa's flattened system metadata -> nested system_metadata
    - Vespa's epoch timestamps -> datetime objects
    - Vespa's payload JSON string -> source_fields dict
    - Qdrant's nested access dict -> access object
    """

    # Result metadata
    id: str = Field(..., description="Unique document ID from destination")
    score: float = Field(..., description="Relevance score (higher = more relevant)")

    # Core entity fields (REQUIRED - not optional)
    entity_id: str = Field(..., description="Original entity ID")
    name: str = Field(..., description="Entity display name")
    textual_representation: str = Field(..., description="Searchable text content")

    # Timestamps (always datetime, converted from epoch if needed)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Hierarchy
    breadcrumbs: List[BreadcrumbResult] = Field(default_factory=list)

    # System metadata (nested, not flattened)
    system_metadata: SystemMetadataResult

    # Access control (nested, not flattened)
    access: Optional[AccessControlResult] = None

    # Source-specific fields (always a dict, never a JSON string)
    source_fields: Dict[str, Any] = Field(
        default_factory=dict,
        description="All source-specific fields (e.g., issue_key, summary for Jira)",
    )

    @classmethod
    def format_results_for_logging(cls, results: List["AirweaveSearchResult"]) -> str:
        """Format a list of search results for readable logging.

        Args:
            results: List of search results to format

        Returns:
            Multi-line formatted string showing each result with full content
        """
        if not results:
            return "(no results)"

        lines = []
        for i, result in enumerate(results, 1):
            lines.append(f"\n{'=' * 80}")
            lines.append(f"RESULT {i}: {result.name}")
            lines.append(f"Score: {result.score:.4f} | Entity: {result.entity_id}")
            lines.append(f"Type: {result.system_metadata.entity_type}")
            lines.append(f"{'-' * 80}")
            lines.append("TEXTUAL REPRESENTATION:")
            lines.append(result.textual_representation)
        lines.append(f"\n{'=' * 80}")

        return "\n".join(lines)
