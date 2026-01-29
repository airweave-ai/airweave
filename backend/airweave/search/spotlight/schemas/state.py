"""Spotlight state schema."""

from typing import Optional

from pydantic import BaseModel, Field

from .collection_metadata import SpotlightCollectionMetadata
from .evaluation import SpotlightEvaluation
from .history import SpotlightHistory
from .plan import SpotlightPlan
from .query_embeddings import SpotlightQueryEmbeddings
from .search_result import SpotlightSearchResult


class SpotlightCurrentIteration(BaseModel):
    """Current spotlight iteration schema."""

    plan: Optional[SpotlightPlan] = Field(default=None, description="Search plan.")
    query_embeddings: Optional[SpotlightQueryEmbeddings] = Field(
        default=None, description="Query embeddings."
    )
    compiled_query: str = Field(None, description="The compiled query.")
    results: Optional[list[SpotlightSearchResult]] = Field(
        default=None, description="Search results."
    )
    evaluation: Optional[SpotlightEvaluation] = Field(default=None, description="Evaluation.")


class SpotlightState(BaseModel):
    """Spotlight state schema."""

    user_query: str = Field(..., description="The user query.")
    collection_id: str = Field(..., description="The collection ID.")

    collection_metadata: SpotlightCollectionMetadata = Field(
        ..., description="The collection metadata."
    )

    iteration: int = Field(..., description="The current iteration number.")
    current_iteration: SpotlightCurrentIteration = Field(..., description="The current iteration.")

    history: SpotlightHistory = Field(..., description="The history.")
