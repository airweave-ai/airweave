"""Spotlight search schemas.

This module exports all Pydantic schemas for the spotlight search module.
"""

from .answer import SpotlightAnswer, SpotlightCitation
from .collection_metadata import SpotlightCollectionMetadata, SpotlightSourceMetadata
from .evaluation import SpotlightEvaluation
from .filter import SpotlightFilterCondition, SpotlightFilterGroup, SpotlightFilterOperator
from .history import SpotlightHistory, SpotlightIteration
from .plan import SpotlightPlan, SpotlightSearchQuery
from .query_embeddings import (
    SpotlightDenseEmbedding,
    SpotlightQueryEmbeddings,
    SpotlightSparseEmbedding,
)
from .request import SpotlightRequest
from .response import SpotlightResponse
from .retrieval_strategy import SpotlightRetrievalStrategy
from .search_result import (
    SpotlightAccessControl,
    SpotlightBreadcrumb,
    SpotlightSearchResult,
    SpotlightSystemMetadata,
)
from .search_result_summary import SpotlightSearchResultSummary
from .state import SpotlightCurrentIteration, SpotlightState

__all__ = [
    # Answer
    "SpotlightAnswer",
    "SpotlightCitation",
    # Collection metadata
    "SpotlightCollectionMetadata",
    "SpotlightSourceMetadata",
    # Evaluation
    "SpotlightEvaluation",
    # Filter
    "SpotlightFilterCondition",
    "SpotlightFilterGroup",
    "SpotlightFilterOperator",
    # History
    "SpotlightHistory",
    "SpotlightIteration",
    # Plan
    "SpotlightPlan",
    "SpotlightSearchQuery",
    # Query embeddings
    "SpotlightDenseEmbedding",
    "SpotlightQueryEmbeddings",
    "SpotlightSparseEmbedding",
    # Request/Response
    "SpotlightRequest",
    "SpotlightResponse",
    # Retrieval strategy
    "SpotlightRetrievalStrategy",
    # Search result
    "SpotlightAccessControl",
    "SpotlightBreadcrumb",
    "SpotlightSearchResult",
    "SpotlightSystemMetadata",
    # Search result summary
    "SpotlightSearchResultSummary",
    # State
    "SpotlightCurrentIteration",
    "SpotlightState",
]
