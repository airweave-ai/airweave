"""Search V2 request/response schemas."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from airweave.domains.search.types import (
    FilterGroup,
    PartialFailure,
    RetrievalStrategy,
    SearchResult,
)


class SearchTier(str, Enum):
    """Search tiers."""

    INSTANT = "instant"
    CLASSIC = "classic"
    AGENTIC = "agentic"


class InstantSearchRequest(BaseModel):
    """Instant search request — embed query, fire at Vespa, return results."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "How do I reset my password?",
                    "retrieval_strategy": "hybrid",
                    "limit": 10,
                },
                {"query": "quarterly revenue report"},
            ]
        }
    }

    query: str = Field(..., description="Search query text.")
    retrieval_strategy: RetrievalStrategy = Field(
        default=RetrievalStrategy.HYBRID,
        description="Which retrieval strategy to use.",
    )
    filter: Optional[list[FilterGroup]] = Field(
        default=None, description="Filter groups (combined with OR)."
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Number of results to skip.")

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        """Validate that query is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v


class ClassicSearchRequest(BaseModel):
    """Classic search request — LLM generates a search plan, execute against Vespa."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "quarterly revenue report", "limit": 10},
                {"query": "find the onboarding documentation"},
            ]
        }
    }

    query: str = Field(..., description="Search query text.")
    filter: Optional[list[FilterGroup]] = Field(
        default=None, description="Filter groups (combined with OR)."
    )
    limit: int = Field(default=100, ge=1, le=1000, description="Max results to return.")
    offset: int = Field(default=0, ge=0, description="Number of results to skip.")

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        """Validate that query is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v


class AgenticSearchRequest(BaseModel):
    """Agentic search request — full agent loop with tool calling."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"query": "find all deployment-related docs from last month", "thinking": True},
                {"query": "what authentication methods do we support?"},
            ]
        }
    }

    query: str = Field(..., description="Search query text.")
    thinking: bool = Field(
        default=False, description="Enable extended thinking / chain-of-thought."
    )
    filter: Optional[list[FilterGroup]] = Field(
        default=None, description="Filter groups (combined with OR)."
    )
    limit: Optional[int] = Field(
        default=None, ge=1, description="Max results. None means agent decides."
    )

    @field_validator("query")
    @classmethod
    def query_not_empty(cls, v: str) -> str:
        """Validate that query is not empty or whitespace-only."""
        if not v.strip():
            raise ValueError("Query cannot be empty")
        return v


class InternalAgenticSearchRequest(AgenticSearchRequest):
    """Admin-only agentic search request with model override for evals."""

    model: Optional[str] = Field(
        default=None,
        description=(
            "LLM model override. Format: 'provider/model' "
            "e.g. 'together/zai-glm-5-thinking'. "
            "When not set, uses the default model from config."
        ),
    )


class BrowseRequest(BaseModel):
    """Browse request — paginated tabular listing of a collection (POC, flag-gated).

    No query, no embeddings, no ranking. Uses Vespa's filter_search() under the hood
    and returns one row per source entity (filtered to chunk_index = 0).
    """

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"limit": 50, "offset": 0},
                {
                    "limit": 50,
                    "offset": 0,
                    "sync_ids": ["d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f80"],
                },
            ]
        }
    }

    filter: Optional[list[FilterGroup]] = Field(
        default=None,
        description="Filter groups (combined with OR). Same shape as search filters.",
    )
    limit: int = Field(default=50, ge=1, le=200, description="Max rows per page.")
    offset: int = Field(default=0, ge=0, description="Number of rows to skip.")

    sync_ids: Optional[list[str]] = Field(
        default=None,
        description="Convenience: limit results to these sync_ids. Translated to a FilterGroup.",
        max_length=100,
    )
    entity_types: Optional[list[str]] = Field(
        default=None,
        description=(
            "Convenience: limit results to these entity types. Translated to a FilterGroup."
        ),
        max_length=100,
    )
    name_query: Optional[str] = Field(
        default=None,
        description=(
            "Case-insensitive substring search against the entity name. Bypasses the "
            "FilterCondition `contains` operator (which is token-match in Vespa) and "
            "translates to a regex `matches` clause. Min length 2 to prevent full-scan "
            "triggers from a single character."
        ),
        min_length=2,
        max_length=200,
    )


class BrowseResponse(BaseModel):
    """Browse response — page of results plus total count for pagination."""

    results: list[SearchResult] = Field(
        default_factory=list, description="Rows on this page (one per source entity)."
    )
    total: int = Field(..., description="Total entity count matching the filter.")
    limit: int = Field(..., description="Limit echoed back from the request.")
    offset: int = Field(..., description="Offset echoed back from the request.")


class SearchV2Response(BaseModel):
    """Unified response for all search tiers."""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [
                        {
                            "entity_id": "page-abc123",
                            "name": "Production Deployment Guide",
                            "relevance_score": 0.94,
                            "textual_representation": (
                                "# Production Deployment Guide\n\n"
                                "This document covers the standard deployment "
                                "process for production releases."
                            ),
                            "created_at": "2025-02-10T09:15:00Z",
                            "updated_at": "2025-03-18T16:30:00Z",
                            "breadcrumbs": [
                                {
                                    "entity_id": "ws-1",
                                    "name": "Acme Workspace",
                                    "entity_type": "NotionWorkspaceEntity",
                                },
                                {
                                    "entity_id": "db-eng",
                                    "name": "Engineering",
                                    "entity_type": "NotionDatabaseEntity",
                                },
                            ],
                            "airweave_system_metadata": {
                                "source_name": "notion",
                                "entity_type": "NotionPageEntity",
                                "original_entity_id": "page-abc123",
                                "chunk_index": 0,
                                "sync_id": "d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f80",
                                "sync_job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                            },
                            "access": {"viewers": None, "is_public": None},
                            "web_url": "https://notion.so/Deployment-Guide-abc123",
                            "url": None,
                            "raw_source_fields": {
                                "icon": "🚀",
                                "archived": False,
                                "parent_type": "database_id",
                            },
                        },
                        {
                            "entity_id": "msg-def456",
                            "name": "Deployment checklist update",
                            "relevance_score": 0.87,
                            "textual_representation": (
                                "Updated the deployment checklist to include "
                                "the new canary step. Make sure to verify "
                                "metrics before promoting to 100%."
                            ),
                            "created_at": "2025-03-15T11:22:00Z",
                            "updated_at": "2025-03-15T11:22:00Z",
                            "breadcrumbs": [
                                {
                                    "entity_id": "team-1",
                                    "name": "Acme",
                                    "entity_type": "SlackWorkspaceEntity",
                                },
                                {
                                    "entity_id": "chan-eng",
                                    "name": "#engineering",
                                    "entity_type": "SlackChannelEntity",
                                },
                            ],
                            "airweave_system_metadata": {
                                "source_name": "slack",
                                "entity_type": "SlackMessageEntity",
                                "original_entity_id": "msg-def456",
                                "chunk_index": 0,
                                "sync_id": "e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8091",
                                "sync_job_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
                            },
                            "access": {"viewers": None, "is_public": None},
                            "web_url": "https://acme.slack.com/archives/C0123ABC/p1710500520",
                            "url": None,
                            "raw_source_fields": {
                                "channel_name": "#engineering",
                                "username": "alice",
                            },
                        },
                    ]
                }
            ]
        }
    }

    results: list[SearchResult] = Field(
        default_factory=list, description="Search results ordered by relevance."
    )
    partial_failures: list[PartialFailure] = Field(
        default_factory=list,
        description=(
            "Sources that failed during this search but were skipped so other "
            "sources could still return results. Empty when the full search succeeded."
        ),
    )
