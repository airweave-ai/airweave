"""Search query model for tracking and analyzing search operations."""

from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import JSON as sa_JSON
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

    # Search type (streaming vs non-streaming)
    is_streaming: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default="false",
        comment="Whether this was a streaming search",
    )

    # Search parameters (actual values used after applying defaults)
    retrieval_strategy: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="Retrieval strategy: 'hybrid', 'neural', 'keyword'"
    )
    limit: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Maximum number of results requested"
    )
    offset: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Number of results to skip for pagination"
    )
    temporal_relevance: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Temporal relevance weight (0.0 to 1.0)"
    )
    filter: Mapped[Optional[dict]] = mapped_column(
        sa_JSON, nullable=True, comment="Qdrant filter applied (if any)"
    )

    # Performance metrics
    duration_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Search execution time in milliseconds"
    )
    results_count: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="Number of results returned"
    )

    # Search configuration flags (actual features enabled after applying defaults)
    expand_query: Mapped[bool] = mapped_column(
        Boolean, nullable=False, comment="Whether query expansion was enabled"
    )
    interpret_filters: Mapped[bool] = mapped_column(
        Boolean, nullable=False, comment="Whether query interpretation was enabled"
    )
    rerank: Mapped[bool] = mapped_column(
        Boolean, nullable=False, comment="Whether LLM reranking was enabled"
    )
    generate_answer: Mapped[bool] = mapped_column(
        Boolean, nullable=False, comment="Whether answer generation was enabled"
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
        Index("ix_search_queries_is_streaming", "is_streaming"),
        Index("ix_search_queries_retrieval_strategy", "retrieval_strategy"),
        Index("ix_search_queries_duration", "duration_ms"),
        Index("ix_search_queries_results_count", "results_count"),
    )
