"""Vespa destination internal data structures.

Simple Pydantic models for type safety and clear interfaces between components.
"""

from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field


class VespaDocument(BaseModel):
    """Transformed entity ready for Vespa feed.

    This is the output of EntityTransformer and input to VespaClient.feed_documents().
    """

    model_config = ConfigDict(populate_by_name=True)

    schema_name: str = Field(
        ..., alias="schema", description="Vespa schema name (e.g., 'base_entity')"
    )
    id: str = Field(..., description="Document ID (e.g., 'EntityType_entity_id')")
    fields: Dict[str, Any] = Field(..., description="Document fields for Vespa")


class FeedResult(BaseModel):
    """Result of a Vespa feed operation."""

    success_count: int = Field(default=0, description="Number of successfully fed documents")
    failed_docs: List[tuple] = Field(
        default_factory=list,
        description="List of (doc_id, status_code, body) for failed documents",
    )


class DeleteResult(BaseModel):
    """Result of a Vespa delete operation."""

    model_config = ConfigDict(populate_by_name=True)

    deleted_count: int = Field(default=0, description="Number of deleted documents")
    schema_name: str = Field(
        ..., alias="schema", description="Schema the deletion was performed on"
    )


class VespaQueryResponse(BaseModel):
    """Wrapper for Vespa query response with extracted metrics."""

    hits: List[Dict[str, Any]] = Field(default_factory=list, description="Search result hits")
    total_count: int = Field(default=0, description="Total matching documents")
    coverage_percent: float = Field(default=100.0, description="Search coverage percentage")
    query_time_ms: float = Field(default=0.0, description="Query execution time in milliseconds")

    model_config = ConfigDict(extra="allow")
