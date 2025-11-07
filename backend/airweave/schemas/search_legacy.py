"""Legacy search schemas for backwards compatibility.

These schemas maintain backwards compatibility with the old search API
while internally converting to the new search implementation.
"""

from enum import Enum
from typing import Literal, Optional

import tiktoken
from pydantic import BaseModel, Field, field_validator
from qdrant_client.http.models import Filter as QdrantFilter


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


class LegacySearchRequest(BaseModel):
    """Legacy search request schema for backwards compatibility."""

    # Core search parameters
    query: str = Field(
        ...,
        description="The search query text (max 2048 tokens)",
    )

    @field_validator("query")
    @classmethod
    def validate_query_token_length(cls, v: str) -> str:
        """Validate that query doesn't exceed 4096 tokens.

        Args:
            v: The query string to validate

        Returns:
            The validated query string

        Raises:
            ValueError: If query exceeds 4096 tokens
        """
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            token_count = len(encoding.encode(v))

            max_tokens = 2048
            if token_count > max_tokens:
                raise ValueError(
                    f"Query is too long: {token_count} tokens exceeds maximum of {max_tokens} "
                    "tokens. Please use a shorter, more focused search query."
                )

            return v
        except Exception as e:
            if "exceeds maximum" in str(e):
                raise
            # If tokenization itself fails, let it through (shouldn't happen)
            return v

    # Qdrant native filter support
    filter: Optional[QdrantFilter] = Field(
        None, description="Qdrant native filter for metadata-based filtering"
    )

    # Pagination
    offset: Optional[int] = Field(0, ge=0, description="Number of results to skip")
    limit: Optional[int] = Field(100, ge=1, le=1000, description="Maximum number of results")

    # Search quality parameters
    score_threshold: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Minimum similarity score threshold (deprecated, will be ignored)",
    )

    # Response configuration
    response_type: ResponseType = Field(
        ResponseType.RAW, description="Type of response - 'raw' or 'completion'"
    )

    # Hybrid search parameters
    search_method: Optional[Literal["hybrid", "neural", "keyword"]] = Field(
        None, description="Search method to use"
    )

    # Recency bias
    recency_bias: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="How much document age affects the similarity score (0..1)",
    )

    expansion_strategy: Optional[QueryExpansionStrategy] = Field(
        None,
        description="Query expansion strategy",
    )

    # Advanced features
    enable_reranking: Optional[bool] = Field(
        None,
        description="Enable LLM-based reranking to improve result relevance",
    )

    enable_query_interpretation: Optional[bool] = Field(
        None,
        description="Enable automatic filter extraction from natural language query",
    )


class LegacySearchResponse(BaseModel):
    """Legacy search response schema for backwards compatibility."""

    results: list[dict] = Field(
        ...,
        description="Array of search result objects",
    )
    response_type: ResponseType = Field(
        ...,
        description="Indicates whether results are raw search matches or AI-generated completions",
    )
    completion: Optional[str] = Field(
        None,
        description="AI-generated natural language answer when response_type is 'completion'",
    )
    status: SearchStatus = Field(
        ...,
        description="Status of the search operation",
    )
