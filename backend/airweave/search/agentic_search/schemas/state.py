"""AgenticSearch state schema."""

from typing import Optional

from pydantic import BaseModel, Field

from airweave.search.agentic_search.schemas.filter import AgenticSearchFilterGroup
from airweave.search.agentic_search.schemas.request import AgenticSearchMode

from .collection_metadata import AgenticSearchCollectionMetadata
from .compiled_query import AgenticSearchCompiledQuery
from .evaluation import AgenticSearchEvaluation
from .history import AgenticSearchHistory
from .plan import AgenticSearchPlan
from .query_embeddings import AgenticSearchQueryEmbeddings
from .search_result import AgenticSearchResults


class AgenticSearchCurrentIteration(BaseModel):
    """Current agentic_search iteration schema."""

    plan: Optional[AgenticSearchPlan] = Field(default=None, description="Search plan.")
    query_embeddings: Optional[AgenticSearchQueryEmbeddings] = Field(
        default=None, description="Query embeddings."
    )
    compiled_query: Optional[AgenticSearchCompiledQuery] = Field(
        None, description="The compiled query."
    )
    search_results: Optional[AgenticSearchResults] = Field(
        default=None, description="Search results."
    )
    search_error: Optional[str] = Field(
        default=None,
        description="Error message if the search query failed. None means search succeeded.",
    )
    evaluation: Optional[AgenticSearchEvaluation] = Field(default=None, description="Evaluation.")


class AgenticSearchState(BaseModel):
    """AgenticSearch state schema."""

    user_query: str = Field(..., description="The user query.")
    user_filter: list[AgenticSearchFilterGroup] = Field(
        default_factory=list, description="The user filter."
    )
    mode: AgenticSearchMode = Field(
        default=AgenticSearchMode.THINKING, description="The search mode."
    )

    collection_metadata: AgenticSearchCollectionMetadata = Field(
        ..., description="The collection metadata."
    )

    iteration_number: int = Field(..., description="The current iteration number.")
    current_iteration: AgenticSearchCurrentIteration = Field(
        ..., description="The current iteration."
    )

    history: Optional[AgenticSearchHistory] = Field(default=None, description="The history.")

    is_consolidation: bool = Field(
        default=False,
        description="Whether this is a consolidation pass (final search after exhaustion).",
    )
