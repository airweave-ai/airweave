"""Search query model for tracking and analyzing search operations."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from airweave.models._base import OrganizationBase, UserMixin

if TYPE_CHECKING:
    from airweave.models.api_key import APIKey
    from airweave.models.collection import Collection
    from airweave.models.user import User


class SearchQuery(OrganizationBase, UserMixin):
    """Model for tracking search queries and their performance.

    This model stores comprehensive information about search operations
    to enable analytics, user experience improvements, and search evolution tracking.
    """

    __tablename__ = "search_queries"

    # Collection relationship
    collection_id: Mapped[UUID] = mapped_column(
        ForeignKey("collection.id", ondelete="CASCADE"),
        nullable=False,
        comment="Collection that was searched",
    )

    # User context (nullable for API key searches)
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who performed the search (null for API key searches)",
    )

    # API key context (nullable for user searches)
    api_key_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("api_key.id", ondelete="SET NULL"),
        nullable=True,
        comment="API key used for the search (null for user searches)",
    )

    # Search query details
    query_text: Mapped[str] = mapped_column(
        Text, nullable=False, comment="The actual search query text"
    )
    query_length: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Length of the search query in characters"
    )

    # Search type and response configuration
    search_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Type of search: 'basic', 'advanced'"
    )
    response_type: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Response type: 'raw', 'completion'"
    )

    # Search parameters
    limit: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Maximum number of results requested"
    )
    offset: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="Number of results to skip for pagination"
    )
    score_threshold: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Minimum similarity score threshold"
    )
    recency_bias: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Recency bias weight (0.0 to 1.0)"
    )
    search_method: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="Search method: 'hybrid', 'neural', 'keyword'"
    )

    # Performance metrics
    duration_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Search execution time in milliseconds"
    )
    results_count: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Number of results returned"
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Search status: 'success', 'no_results', 'no_relevant_results', 'error'",
    )

    # Search configuration flags
    query_expansion_enabled: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, comment="Whether query expansion was enabled"
    )
    reranking_enabled: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, comment="Whether LLM reranking was enabled"
    )
    query_interpretation_enabled: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, comment="Whether query interpretation was enabled"
    )

    # Relationships
    collection: Mapped["Collection"] = relationship(
        "Collection",
        back_populates="search_queries",
        lazy="noload",
    )
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="search_queries",
        lazy="noload",
    )
    api_key: Mapped[Optional["APIKey"]] = relationship(
        "APIKey",
        lazy="noload",
    )

    __table_args__ = (
        # Indexes for performance
        Index("ix_search_queries_org_created", "organization_id", "created_at"),
        Index("ix_search_queries_collection_created", "collection_id", "created_at"),
        Index("ix_search_queries_user_created", "user_id", "created_at"),
        Index("ix_search_queries_api_key_created", "api_key_id", "created_at"),
        Index("ix_search_queries_status", "status"),
        Index("ix_search_queries_search_type", "search_type"),
        Index("ix_search_queries_query_text", "query_text"),  # For text analysis
        Index("ix_search_queries_duration", "duration_ms"),
        Index("ix_search_queries_results_count", "results_count"),
    )
