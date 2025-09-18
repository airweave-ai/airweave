"""Search query schemas for API serialization."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SearchQueryBase(BaseModel):
    """Base schema for search query operations."""

    query_text: str = Field(..., description="The search query text")
    query_length: int = Field(..., description="Length of the search query in characters")
    search_type: str = Field(..., description="Type of search: 'basic', 'advanced', 'streaming'")
    response_type: Optional[str] = Field(None, description="Response type: 'raw', 'completion'")
    limit: Optional[int] = Field(None, description="Maximum number of results requested")
    offset: Optional[int] = Field(None, description="Number of results to skip for pagination")
    score_threshold: Optional[float] = Field(None, description="Minimum similarity score threshold")
    recency_bias: Optional[float] = Field(None, description="Recency bias weight (0.0 to 1.0)")
    search_method: Optional[str] = Field(
        None, description="Search method: 'hybrid', 'neural', 'keyword'"
    )
    duration_ms: int = Field(..., description="Search execution time in milliseconds")
    results_count: int = Field(..., description="Number of results returned")
    status: str = Field(
        ..., description="Search status: 'success', 'no_results', 'no_relevant_results', 'error'"
    )
    query_expansion_enabled: Optional[bool] = Field(
        None, description="Whether query expansion was enabled"
    )
    reranking_enabled: Optional[bool] = Field(None, description="Whether LLM reranking was enabled")
    query_interpretation_enabled: Optional[bool] = Field(
        None, description="Whether query interpretation was enabled"
    )


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
    search_type: Optional[str] = Field(None, description="Type of search")
    response_type: Optional[str] = Field(None, description="Response type")
    limit: Optional[int] = Field(None, description="Maximum number of results requested")
    offset: Optional[int] = Field(None, description="Number of results to skip for pagination")
    score_threshold: Optional[float] = Field(None, description="Minimum similarity score threshold")
    recency_bias: Optional[float] = Field(None, description="Recency bias weight")
    search_method: Optional[str] = Field(None, description="Search method")
    duration_ms: Optional[int] = Field(None, description="Search execution time in milliseconds")
    results_count: Optional[int] = Field(None, description="Number of results returned")
    status: Optional[str] = Field(None, description="Search status")
    query_expansion_enabled: Optional[bool] = Field(
        None, description="Whether query expansion was enabled"
    )
    reranking_enabled: Optional[bool] = Field(None, description="Whether LLM reranking was enabled")
    query_interpretation_enabled: Optional[bool] = Field(
        None, description="Whether query interpretation was enabled"
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

    class Config:
        """Pydantic configuration for SearchQueryInDBBase."""

        from_attributes = True


class SearchQueryAnalytics(BaseModel):
    """Schema for search query analytics data."""

    total_searches: int = Field(..., description="Total number of searches")
    successful_searches: int = Field(..., description="Number of successful searches")
    failed_searches: int = Field(..., description="Number of failed searches")
    average_duration_ms: float = Field(..., description="Average search duration in milliseconds")
    average_results_count: float = Field(..., description="Average number of results returned")
    most_common_queries: list[dict[str, int]] = Field(..., description="Most common search queries")
    search_types_distribution: dict[str, int] = Field(
        ..., description="Distribution of search types"
    )
    status_distribution: dict[str, int] = Field(..., description="Distribution of search statuses")


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
