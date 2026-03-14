"""Search domain types — re-exports for convenience.

Usage:
    from airweave.domains.search.types import SearchResult, FilterGroup, SearchPlan
"""

from airweave.domains.search.types.embeddings import QueryEmbeddings
from airweave.domains.search.types.filters import (
    FilterableField,
    FilterCondition,
    FilterGroup,
    FilterOperator,
    format_filter_groups_md,
)
from airweave.domains.search.types.metadata import (
    CollectionMetadata,
    EntityTypeMetadata,
    SourceMetadata,
)
from airweave.domains.search.types.plan import (
    RetrievalStrategy,
    SearchPlan,
    SearchQuery,
)
from airweave.domains.search.types.results import (
    CompiledQuery,
    SearchAccessControl,
    SearchBreadcrumb,
    SearchResult,
    SearchResults,
    SearchSystemMetadata,
)

__all__ = [
    # results
    "SearchBreadcrumb",
    "SearchSystemMetadata",
    "SearchAccessControl",
    "SearchResult",
    "SearchResults",
    "CompiledQuery",
    # filters
    "FilterableField",
    "FilterOperator",
    "FilterCondition",
    "FilterGroup",
    "format_filter_groups_md",
    # plan
    "RetrievalStrategy",
    "SearchQuery",
    "SearchPlan",
    # embeddings
    "QueryEmbeddings",
    # metadata
    "EntityTypeMetadata",
    "SourceMetadata",
    "CollectionMetadata",
]
