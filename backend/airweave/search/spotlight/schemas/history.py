"""Spotlight history schema."""

from pydantic import BaseModel, Field

from .evaluation import SpotlightEvaluation
from .plan import SpotlightPlan
from .search_result_summary import SpotlightSearchResultSummary

# Hisoty is created after the first full iteration


class SpotlightIteration(BaseModel):
    """Spotlight iteration schema."""

    plan: SpotlightPlan = Field(..., description="Plan used for this iteration.")
    compiled_query: str = Field(..., description="The compiled query.")
    result_summaries: list[SpotlightSearchResultSummary] = Field(
        ..., description="Summary of each search result."
    )
    evaluation: SpotlightEvaluation = Field(
        ..., description="Evaluation of the results used for this iteration."
    )


class SpotlightHistory(BaseModel):
    """Spotlight history schema."""

    iterations: dict[int, SpotlightIteration] = Field(
        ...,
        description="Past iterations keyed by iteration number.",
    )
