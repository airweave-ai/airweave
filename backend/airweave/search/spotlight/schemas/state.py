"""Spotlight state schema."""

from typing import Optional

from pydantic import BaseModel, Field

from airweave.search.spotlight.schemas.filter import SpotlightFilterGroup
from airweave.search.spotlight.schemas.request import SpotlightSearchMode

from .collection_metadata import SpotlightCollectionMetadata
from .compiled_query import SpotlightCompiledQuery
from .evaluation import SpotlightEvaluation
from .history import SpotlightHistory
from .plan import SpotlightPlan
from .query_embeddings import SpotlightQueryEmbeddings
from .search_result import SpotlightSearchResults


class SpotlightCurrentIteration(BaseModel):
    """Current spotlight iteration schema."""

    plan: Optional[SpotlightPlan] = Field(default=None, description="Search plan.")
    query_embeddings: Optional[SpotlightQueryEmbeddings] = Field(
        default=None, description="Query embeddings."
    )
    compiled_query: Optional[SpotlightCompiledQuery] = Field(
        None, description="The compiled query."
    )
    search_results: Optional[SpotlightSearchResults] = Field(
        default=None, description="Search results."
    )
    search_error: Optional[str] = Field(
        default=None,
        description="Error message if the search query failed. None means search succeeded.",
    )
    evaluation: Optional[SpotlightEvaluation] = Field(default=None, description="Evaluation.")


class SpotlightState(BaseModel):
    """Spotlight state schema."""

    user_query: str = Field(..., description="The user query.")
    user_filter: list[SpotlightFilterGroup] = Field(
        default_factory=list, description="The user filter."
    )
    mode: SpotlightSearchMode = Field(
        default=SpotlightSearchMode.AGENTIC, description="The search mode."
    )

    collection_metadata: SpotlightCollectionMetadata = Field(
        ..., description="The collection metadata."
    )

    iteration_number: int = Field(..., description="The current iteration number.")
    current_iteration: SpotlightCurrentIteration = Field(..., description="The current iteration.")

    history: Optional[SpotlightHistory] = Field(default=None, description="The history.")

    is_consolidation: bool = Field(
        default=False,
        description="Whether this is a consolidation pass (final search after exhaustion).",
    )
