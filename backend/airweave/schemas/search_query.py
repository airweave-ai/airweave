"""Search query schemas for API serialization."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SearchQueryBase(BaseModel):
    """Base schema for search query operations."""

    query_text: str = Field(..., description="The search query text")
    query_length: int = Field(..., description="Length of the search query in characters")
    is_streaming: bool = Field(..., description="Whether this was a streaming search")
    retrieval_strategy: str = Field(
        ..., description="Retrieval strategy: 'hybrid', 'neural', 'keyword'"
    )
    limit: int = Field(..., description="Maximum number of results requested")
    offset: int = Field(..., description="Number of results to skip for pagination")
    temporal_relevance: float = Field(..., description="Temporal relevance weight (0.0 to 1.0)")
    filter: Optional[dict] = Field(None, description="Qdrant filter applied (if any)")
    duration_ms: int = Field(..., description="Search execution time in milliseconds")
    results_count: int = Field(..., description="Number of results returned")
    expand_query: bool = Field(..., description="Whether query expansion was enabled")
    interpret_filters: bool = Field(..., description="Whether query interpretation was enabled")
    rerank: bool = Field(..., description="Whether LLM reranking was enabled")
    generate_answer: bool = Field(..., description="Whether answer generation was enabled")


class SearchQueryCreate(SearchQueryBase):
    """Schema for creating a search query record."""

    collection_id: UUID = Field(..., description="ID of the collection that was searched")
    user_id: Optional[UUID] = Field(None, description="ID of the user who performed the search")
    api_key_id: Optional[UUID] = Field(None, description="ID of the API key used for the search")


class SearchQueryUpdate(BaseModel):
    """Schema for updating a search query record."""

    query_text: Optional[str] = Field(None, description="The search query text")
    query_length: Optional[int] = Field(
        None, description="Length of the search query in characters"
    )
    is_streaming: Optional[bool] = Field(None, description="Whether this was a streaming search")
    retrieval_strategy: Optional[str] = Field(None, description="Retrieval strategy")
    limit: Optional[int] = Field(None, description="Maximum number of results requested")
    offset: Optional[int] = Field(None, description="Number of results to skip for pagination")
    temporal_relevance: Optional[float] = Field(None, description="Temporal relevance weight")
    filter: Optional[dict] = Field(None, description="Qdrant filter applied (if any)")
    duration_ms: Optional[int] = Field(None, description="Search execution time in milliseconds")
    results_count: Optional[int] = Field(None, description="Number of results returned")
    expand_query: Optional[bool] = Field(None, description="Whether query expansion was enabled")
    interpret_filters: Optional[bool] = Field(
        None, description="Whether query interpretation was enabled"
    )
    rerank: Optional[bool] = Field(None, description="Whether LLM reranking was enabled")
    generate_answer: Optional[bool] = Field(
        None, description="Whether answer generation was enabled"
    )


class SearchQueryResponse(SearchQueryBase):
    """Schema for search query responses."""

    id: UUID = Field(..., description="Unique identifier for the search query")
    organization_id: UUID = Field(..., description="ID of the organization")
    collection_id: UUID = Field(..., description="ID of the collection that was searched")
    user_id: Optional[UUID] = Field(None, description="ID of the user who performed the search")
    api_key_id: Optional[UUID] = Field(None, description="ID of the API key used for the search")
    created_at: str = Field(..., description="When the search query was created")
    modified_at: str = Field(..., description="When the search query was last modified")
    created_by_email: Optional[str] = Field(
        None, description="Email of the user who created the record"
    )
    modified_by_email: Optional[str] = Field(
        None, description="Email of the user who last modified the record"
    )

    model_config = ConfigDict(from_attributes=True)


class SearchQueryAnalytics(BaseModel):
    """Schema for search query analytics data."""

    total_searches: int = Field(..., description="Total number of searches")
    average_duration_ms: float = Field(..., description="Average search duration in milliseconds")
    average_results_count: float = Field(..., description="Average number of results returned")
    most_common_queries: list[dict[str, int]] = Field(..., description="Most common search queries")
    streaming_searches: int = Field(..., description="Number of streaming searches")
    retrieval_strategy_distribution: dict[str, int] = Field(
        ..., description="Distribution of retrieval strategies"
    )
    feature_adoption: dict[str, float] = Field(
        ..., description="Adoption rates for search features (expansion, reranking, etc.)"
    )


class SearchQueryInsights(BaseModel):
    """Schema for search query insights and recommendations."""

    query_evolution_score: Optional[float] = Field(
        None, description="Query sophistication evolution score"
    )
    feature_adoption_rate: dict[str, float] = Field(..., description="Feature adoption rates")
    search_efficiency_trend: list[dict[str, float]] = Field(
        ..., description="Search efficiency trends over time"
    )
    recommended_queries: list[str] = Field(..., description="Recommended search queries")
    search_optimization_tips: list[str] = Field(..., description="Search optimization tips")
