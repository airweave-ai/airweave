"""Search schemas for Airweave's search API."""

from enum import Enum
from typing import Optional

import tiktoken
from pydantic import BaseModel, Field, field_validator
from qdrant_client.http.models import Filter as QdrantFilter


class RetrievalStrategy(str, Enum):
    """Retrieval strategies for search."""

    HYBRID = "hybrid"
    NEURAL = "neural"
    KEYWORD = "keyword"


class SearchRequest(BaseModel):
    """Search request schema."""

    query: str = Field(..., description="The search query text")

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
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")

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

    retrieval_strategy: Optional[RetrievalStrategy] = Field(
        default=None, description="The retrieval strategy to use"
    )
    filter: Optional[QdrantFilter] = Field(
        default=None, description="Qdrant native filter for metadata-based filtering"
    )
    offset: Optional[int] = Field(default=None, description="Number of results to skip")
    limit: Optional[int] = Field(default=None, description="Maximum number of results to return")

    temporal_relevance: Optional[float] = Field(
        default=None,
        description=(
            "Weight recent content higher than older content; "
            "0 = no recency effect, 1 = only recent items matter"
        ),
    )

    expand_query: Optional[bool] = Field(
        default=None, description="Generate a few query variations to improve recall"
    )
    interpret_filters: Optional[bool] = Field(
        default=None, description="Extract structured filters from natural-language query"
    )
    rerank: Optional[bool] = Field(
        default=None,
        description=(
            "Reorder the top candidate results for improved relevance. "
            "Max number of results that can be reranked is capped to around 1000."
        ),
    )
    generate_answer: Optional[bool] = Field(
        default=None, description="Generate a natural-language answer to the query"
    )


class SearchDefaults(BaseModel):
    """Default values for search parameters loaded from YAML."""

    retrieval_strategy: RetrievalStrategy
    offset: int
    limit: int
    temporal_relevance: float
    expand_query: bool
    interpret_filters: bool
    rerank: bool
    generate_answer: bool


class SearchResponse(BaseModel):
    """Comprehensive search response containing results and metadata."""

    results: list[dict] = Field(
        description=(
            "Array of search result objects containing the found documents, records, "
            "or data entities."
        )
    )
    completion: Optional[str] = Field(
        description=(
            "This provides natural language answers to your query based on the content found "
            "across your connected data sources when generate_answer is true."
        ),
    )
