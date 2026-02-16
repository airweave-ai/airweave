"""Search schemas for Airweave's search API."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

import tiktoken
from pydantic import BaseModel, Field, field_validator

# Type alias for the canonical Airweave filter format.
# This follows the Qdrant filter structure (must/should/must_not) which is
# translated to destination-specific formats by each destination's translate_filter().
AirweaveFilter = Dict[str, Any]


class RetrievalStrategy(str, Enum):
    """Retrieval strategies for search."""

    HYBRID = "hybrid"
    NEURAL = "neural"
    KEYWORD = "keyword"


class AirweaveTemporalConfig(BaseModel):
    """Destination-agnostic temporal relevance configuration.

    This configuration is translated to destination-specific formats:
    - Qdrant: DecayConfig with linear decay
    - Vespa: Freshness ranking function (future implementation)

    The TemporalRelevance operation dynamically computes these values by analyzing
    the actual timestamp distribution in the collection.
    """

    weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Weight of temporal relevance in final ranking (0-1)",
    )
    reference_field: str = Field(
        default="updated_at",
        description="Timestamp field to use for temporal relevance calculation",
    )
    target_datetime: Optional[datetime] = Field(
        default=None,
        description=(
            "Reference point for decay calculation. When set dynamically by "
            "TemporalRelevance operation, this is the newest timestamp in the collection. "
            "If None, destinations should use datetime.now()."
        ),
    )
    scale_seconds: Optional[float] = Field(
        default=None,
        description=(
            "Time scale for decay in seconds. When set dynamically by TemporalRelevance "
            "operation, this is the full time span from oldest to newest document. "
            "If None, destinations should use a sensible default (e.g., 7 days)."
        ),
    )
    decay_scale: Optional[str] = Field(
        default=None,
        description=(
            "DEPRECATED: Use scale_seconds instead. "
            "Time scale as string (e.g., '7d' for 7 days). Only used if scale_seconds is None."
        ),
    )


class SearchRequest(BaseModel):
    """Search request for querying a collection.

    Provides fine-grained control over the search pipeline including retrieval strategy,
    filtering, and AI-powered features like query expansion and answer generation.
    """

    query: str = Field(
        ...,
        description="The search query text (required, max 2048 tokens)",
        json_schema_extra={"example": "How do I reset my password?"},
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
        if not v or not v.strip():
            raise ValueError("Query cannot be empty")

        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            # Use allowed_special="all" to handle special tokens like <|endoftext|>
            token_count = len(encoding.encode(v, allowed_special="all"))

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
        default=None,
        description=(
            "Search strategy: 'hybrid' (default), 'neural' (semantic only), "
            "or 'keyword' (BM25 only)"
        ),
        json_schema_extra={"example": "hybrid"},
    )
    filter: Optional[AirweaveFilter] = Field(
        default=None,
        description="Structured filter for metadata-based filtering (Qdrant filter format)",
        json_schema_extra={
            "example": {"must": [{"key": "source_name", "match": {"value": "GitHub"}}]}
        },
    )
    offset: Optional[int] = Field(
        default=None,
        description="Number of results to skip for pagination (default: 0)",
        json_schema_extra={"example": 0},
    )
    limit: Optional[int] = Field(
        default=None,
        description="Maximum number of results to return (default: 1000)",
        json_schema_extra={"example": 10},
    )

    temporal_relevance: Optional[float] = Field(
        default=None,
        description=(
            "DEPRECATED: This field is accepted for backwards compatibility but ignored. "
            "Temporal relevance has been removed."
        ),
        json_schema_extra={"example": 0.0},
    )

    expand_query: Optional[bool] = Field(
        default=None,
        description="Generate query variations to improve recall (default: true)",
        json_schema_extra={"example": True},
    )
    interpret_filters: Optional[bool] = Field(
        default=None,
        description=(
            "Extract structured filters from natural language "
            "(e.g., 'from last week' becomes a date filter)"
        ),
        json_schema_extra={"example": False},
    )
    rerank: Optional[bool] = Field(
        default=None,
        description="LLM-based reranking for improved relevance (default: true)",
        json_schema_extra={"example": True},
    )
    generate_answer: Optional[bool] = Field(
        default=None,
        description="Generate an AI answer based on search results (default: true)",
        json_schema_extra={"example": True},
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summary": "Simple search",
                    "value": {"query": "How do I reset my password?"},
                },
                {
                    "summary": "Search with filters",
                    "value": {
                        "query": "deployment errors",
                        "filter": {"must": [{"key": "source_name", "match": {"value": "GitHub"}}]},
                        "limit": 20,
                    },
                },
                {
                    "summary": "Fast search (no AI features)",
                    "value": {
                        "query": "kubernetes config",
                        "expand_query": False,
                        "rerank": False,
                        "generate_answer": False,
                    },
                },
                {
                    "summary": "Full-featured search",
                    "value": {
                        "query": "What are best practices for error handling?",
                        "retrieval_strategy": "hybrid",
                        "expand_query": True,
                        "interpret_filters": True,
                        "rerank": True,
                        "generate_answer": True,
                        "limit": 10,
                    },
                },
            ]
        }
    }


class SearchDefaults(BaseModel):
    """Default values for search parameters loaded from YAML."""

    retrieval_strategy: RetrievalStrategy
    offset: int
    limit: int
    expand_query: bool
    interpret_filters: bool
    rerank: bool
    generate_answer: bool


class SearchResponse(BaseModel):
    """Search response containing results and optional AI-generated completion.

    Each result includes the matched entity's content, metadata, relevance score,
    and source information.
    """

    results: list[dict] = Field(
        ...,
        description=(
            "Array of search result objects containing the found documents, records, "
            "or data entities. Each result includes entity_id, source_name, md_content, "
            "metadata, score, breadcrumbs, and url."
        ),
    )
    completion: Optional[str] = Field(
        default=None,
        description=(
            "AI-generated natural language answer to your query based on the search results. "
            "Only included when generate_answer is true in the request."
        ),
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "results": [
                    {
                        "entity_id": "abc123-def456-789012",
                        "source_name": "GitHub",
                        "md_content": "# Password Reset Guide\n\nTo reset your password...",
                        "metadata": {
                            "file_path": "docs/auth/password-reset.md",
                            "last_modified": "2024-03-15T09:30:00Z",
                        },
                        "score": 0.92,
                        "breadcrumbs": ["docs", "auth", "password-reset.md"],
                        "url": "https://github.com/company/docs/blob/main/docs/auth/password-reset.md",
                    },
                    {
                        "entity_id": "xyz789-abc123-456789",
                        "source_name": "Notion",
                        "md_content": "## User Authentication\n\nPassword reset is available...",
                        "metadata": {"page_id": "page-123", "workspace": "Engineering"},
                        "score": 0.85,
                        "breadcrumbs": ["Engineering", "User Authentication"],
                        "url": "https://notion.so/page-123",
                    },
                ],
                "completion": (
                    "To reset your password, navigate to the login page and click "
                    "'Forgot Password'. You'll receive an email with a reset link "
                    "that expires in 24 hours. For security, ensure you're using "
                    "a strong password with at least 12 characters."
                ),
            }
        }
    }
