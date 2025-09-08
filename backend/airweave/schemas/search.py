"""Search schemas for Airweave's search API.

This module provides schemas for unified semantic search functionality, enabling
queries across multiple data sources within collections. These schemas define
the search request and response formats for both raw search results and
AI-generated completions.
"""

from enum import Enum
from typing import TYPE_CHECKING, List, Literal, Optional

from pydantic import BaseModel, Field
from qdrant_client.http.models import Filter as QdrantFilter

if TYPE_CHECKING:
    from airweave.search.operations.completion import CompletionGeneration
    from airweave.search.operations.embedding import Embedding
    from airweave.search.operations.qdrant_filter import QdrantFilterOperation
    from airweave.search.operations.query_expansion import QueryExpansion
    from airweave.search.operations.query_interpretation import QueryInterpretation
    from airweave.search.operations.recency_bias import RecencyBias
    from airweave.search.operations.reranking import LLMReranking
    from airweave.search.operations.vector_search import VectorSearch


class ResponseType(str, Enum):
    """Response format options for search results."""

    RAW = "raw"
    COMPLETION = "completion"


class QueryExpansionStrategy(str, Enum):
    """Query expansion strategies for search."""

    AUTO = "auto"
    LLM = "llm"
    NO_EXPANSION = "no_expansion"


class SearchStatus(str, Enum):
    """Status indicators for search operation outcomes."""

    SUCCESS = "success"
    NO_RELEVANT_RESULTS = "no_relevant_results"
    NO_RESULTS = "no_results"


class QueryExpansions(BaseModel):
    """Structured output for LLM-based query expansions."""

    alternatives: List[str] = Field(
        ...,
        description="Alternative query phrasings",
        max_length=4,
    )


class SearchRequest(BaseModel):
    """Comprehensive search request encapsulating all search parameters."""

    # Core search parameters
    query: str = Field(
        ...,
        description="The search query text",
        min_length=1,
        max_length=1000,
        examples=["customer payment issues", "Q4 revenue trends", "support tickets about billing"],
    )

    # Qdrant native filter support
    filter: Optional[QdrantFilter] = Field(
        None, description="Qdrant native filter for metadata-based filtering"
    )

    # Pagination
    offset: Optional[int] = Field(0, ge=0, description="Number of results to skip (DEFAULT: 0)")

    limit: Optional[int] = Field(
        100, ge=1, le=1000, description="Maximum number of results to return (DEFAULT: 100)"
    )

    # Search quality parameters
    score_threshold: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold (DEFAULT: None - no filtering)",
    )

    # Response configuration
    response_type: ResponseType = Field(
        ResponseType.RAW, description="Type of response - 'raw' or 'completion' (DEFAULT: 'raw')"
    )

    # Hybrid search parameters
    search_method: Optional[Literal["hybrid", "neural", "keyword"]] = Field(
        None, description="Search method to use (DEFAULT: 'hybrid' - combines neural + BM25)"
    )

    # Recency bias (public abstraction over decay)
    recency_bias: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description=(
            "How much document age penalizes the similarity score (0..1). "
            "0 = no age penalty (pure similarity); "
            "0.5 = old docs lose up to 50% of their score; "
            "1 = old docs get zero score (pure recency). "
            "Applied as: score × (1 - bias + bias × age_factor). "
            "Works within top ~10,000 semantic matches. DEFAULT: 0.3"
        ),
    )

    expansion_strategy: Optional[QueryExpansionStrategy] = Field(
        None,
        description=(
            "Query expansion strategy (DEFAULT: 'auto' - generates up to 4 query variations). "
            "Options: 'auto', 'llm', 'no_expansion'"
        ),
    )

    # Advanced features (POST endpoint only)
    enable_reranking: Optional[bool] = Field(
        None,
        description=(
            "Enable LLM-based reranking to improve result relevance "
            "(DEFAULT: True - enabled, set to False to disable)"
        ),
    )

    enable_query_interpretation: Optional[bool] = Field(
        None,
        description=(
            "Enable automatic filter extraction from natural language query "
            "(DEFAULT: True - enabled, set to False to disable)"
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "query": "customer payment issues",
                    "filter": {
                        "must": [
                            {"key": "source_name", "match": {"value": "Support"}},
                            {"key": "status", "match": {"value": "open"}},
                        ]
                    },
                    "limit": 10,
                    "score_threshold": 0.7,
                    "response_type": "completion",
                },
                {"query": "Q4 revenue analysis", "limit": 20, "response_type": "raw"},
            ],
            "required": ["query"],
        },
    }


class SearchResponse(BaseModel):
    """Comprehensive search response containing results and metadata."""

    results: list[dict] = Field(
        ...,
        description=(
            "Array of search result objects containing the found documents, records, "
            "or data entities."
        ),
    )
    response_type: ResponseType = Field(
        ...,
        description=(
            "Indicates whether results are raw search matches or AI-generated completions "
            "based on the found content."
        ),
    )
    completion: Optional[str] = Field(
        None,
        description=(
            "AI-generated natural language answer when response_type is 'completion'. This "
            "provides natural language answers to your query based on the content found "
            "across your connected data sources."
        ),
    )
    status: SearchStatus = Field(
        ...,
        description=(
            "Status of the search operation indicating the quality and availability of "
            "results:<br/>"
            "• **success**: Search found relevant results matching your query<br/>"
            "• **no_relevant_results**: Search completed but found no sufficiently "
            "relevant matches<br/>"
            "• **no_results**: Search found no results at all, possibly indicating empty "
            "collections or very specific queries"
        ),
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "results": [
                        {
                            "score": 0.92,
                            "payload": {
                                "source_name": "Payment API",
                                "entity_id": "trans_1234567890",
                                "title": "Transaction Processing",
                                "md_content": (
                                    "Customer John Doe successfully processed payment of $99 "
                                    "for monthly subscription"
                                ),
                                "created_at": "2024-01-15T10:30:00Z",
                                "metadata": {
                                    "amount": 99,
                                    "currency": "USD",
                                    "status": "completed",
                                },
                            },
                        },
                        {
                            "score": 0.87,
                            "payload": {
                                "source_name": "Support Tickets",
                                "entity_id": "ticket_987654321",
                                "title": "Billing Inquiry",
                                "md_content": (
                                    "Customer inquired about upgrading subscription plan "
                                    "for advanced analytics features"
                                ),
                                "created_at": "2024-01-14T14:22:00Z",
                                "metadata": {"priority": "medium", "status": "resolved"},
                            },
                        },
                    ],
                    "response_type": "raw",
                    "status": "success",
                },
                {
                    "results": [
                        {
                            "score": 0.95,
                            "payload": {
                                "source_name": "Customer Database",
                                "entity_id": "cust_abc123",
                                "md_content": "Premium customer account details",
                                "metadata": {"tier": "premium", "active": True},
                            },
                        },
                    ],
                    "response_type": "completion",
                    "completion": (
                        "Based on your recent data, customer John Doe successfully processed a $99 "
                        "monthly subscription payment on January 15th. There was also a related "
                        "support ticket from January 14th where a customer inquired about "
                        "upgrading from Basic to Pro plan for advanced analytics features. This "
                        "suggests strong customer engagement with your premium offerings."
                    ),
                    "status": "success",
                },
            ]
        }
    }


class SearchConfig(BaseModel):
    """Search configuration with operation instances.

    This represents the complete execution plan for a search request.
    Each field contains either an operation instance or None, making it
    clear which operations are enabled for this search.
    """

    # Core search parameters (from request)
    query: str = Field(..., description="The search query text")
    collection_id: str = Field(..., description="ID of the collection to search")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Pagination offset")
    score_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum score")

    # Hybrid search and recency parameters
    search_method: Literal["hybrid", "neural", "keyword"] = Field(
        "hybrid", description="Search method to use"
    )
    # Decay config removed: recency_bias and pre-search operator control recency
    recency_bias: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description=(
            "Relative weight for recency vs similarity when combining final scores (0..1)."
        ),
    )

    # Operations - each field is either an operation instance or None
    # This makes it explicit which operations are enabled
    query_interpretation: Optional["QueryInterpretation"] = Field(
        None, description="LLM-based filter extraction from natural language"
    )

    query_expansion: Optional["QueryExpansion"] = Field(
        None, description="Query expansion for improved recall"
    )

    qdrant_filter: Optional["QdrantFilterOperation"] = Field(
        None, description="User-provided Qdrant filter application"
    )

    embedding: "Embedding" = Field(..., description="Embedding generation (always required)")

    vector_search: "VectorSearch" = Field(
        ..., description="Vector similarity search (always required)"
    )

    # Recency normalization/boost (optional)
    recency: Optional["RecencyBias"] = Field(
        None, description="Dynamic recency normalization and boosting after retrieval"
    )

    reranking: Optional["LLMReranking"] = Field(None, description="LLM-based result reranking")

    completion: Optional["CompletionGeneration"] = Field(
        None, description="AI completion generation"
    )

    class Config:
        """Pydantic config."""

        arbitrary_types_allowed = True  # Allow operation instances
