"""Spotlight search schemas.

This module exports all Pydantic schemas for the spotlight search module.
"""

from .answer import SpotlightAnswer
from .collection_metadata import (
    SpotlightCollectionMetadata,
    SpotlightEntityTypeMetadata,
    SpotlightSourceMetadata,
)
from .compiled_query import SpotlightCompiledQuery
from .database import (
    SpotlightCollection,
    SpotlightEntityCount,
    SpotlightEntityDefinition,
    SpotlightSource,
    SpotlightSourceConnection,
)
from .evaluation import SpotlightEvaluation
from .events import (
    SpotlightDoneEvent,
    SpotlightErrorEvent,
    SpotlightEvaluatingEvent,
    SpotlightEvent,
    SpotlightPlanningEvent,
    SpotlightSearchingEvent,
)
from .filter import SpotlightFilterCondition, SpotlightFilterGroup, SpotlightFilterOperator
from .history import SpotlightHistory, SpotlightHistoryIteration
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
    ResultBrief,
    ResultBriefEntry,
    SpotlightAccessControl,
    SpotlightBreadcrumb,
    SpotlightSearchResult,
    SpotlightSystemMetadata,
)
from .state import SpotlightCurrentIteration, SpotlightState

__all__ = [
    # Answer
    "SpotlightAnswer",
    # Collection metadata
    "SpotlightCollectionMetadata",
    "SpotlightEntityTypeMetadata",
    "SpotlightSourceMetadata",
    # Compiled query
    "SpotlightCompiledQuery",
    # Database (internal schemas for database layer)
    "SpotlightCollection",
    "SpotlightEntityCount",
    "SpotlightEntityDefinition",
    "SpotlightSource",
    "SpotlightSourceConnection",
    # Evaluation
    "SpotlightEvaluation",
    # Events
    "SpotlightDoneEvent",
    "SpotlightErrorEvent",
    "SpotlightEvaluatingEvent",
    "SpotlightEvent",
    "SpotlightPlanningEvent",
    "SpotlightSearchingEvent",
    # Filter
    "SpotlightFilterCondition",
    "SpotlightFilterGroup",
    "SpotlightFilterOperator",
    # History
    "SpotlightHistory",
    "SpotlightHistoryIteration",
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
    "ResultBrief",
    "ResultBriefEntry",
    "SpotlightAccessControl",
    "SpotlightBreadcrumb",
    "SpotlightSearchResult",
    "SpotlightSystemMetadata",
    # State
    "SpotlightCurrentIteration",
    "SpotlightState",
]
