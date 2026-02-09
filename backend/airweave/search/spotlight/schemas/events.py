"""Event schemas for spotlight search streaming.

Typed events emitted during spotlight search to give users transparency
into the agent's reasoning process. Each event has a `type` literal
discriminator for clean JSON serialization and frontend consumption.

Planning and evaluating events carry the full plan/evaluation objects
so consumers (frontend, evals, scripts) can pick out whatever they need.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from airweave.search.spotlight.schemas.evaluation import SpotlightEvaluation
from airweave.search.spotlight.schemas.plan import SpotlightPlan
from airweave.search.spotlight.schemas.response import SpotlightResponse


class SpotlightPlanningEvent(BaseModel):
    """Emitted after the planner generates a search plan.

    Contains the full plan so consumers can access reasoning, query,
    strategy, filters, limit, offset -- whatever they need.

    Also includes history_shown / history_total so consumers can see
    how much of the search history the planner actually saw.
    """

    type: Literal["planning"] = "planning"
    iteration: int = Field(..., description="Current iteration number (0-indexed).")
    plan: SpotlightPlan = Field(..., description="The full search plan.")
    is_consolidation: bool = Field(
        default=False,
        description="Whether this is a consolidation pass (final search after exhaustion).",
    )
    history_shown: int = Field(
        ..., description="Number of detailed history iterations included in the planner prompt."
    )
    history_total: int = Field(..., description="Total number of past iterations.")


class SpotlightSearchingEvent(BaseModel):
    """Emitted after search execution completes.

    Shows how many results were found and how long the search took.
    """

    type: Literal["searching"] = "searching"
    iteration: int = Field(..., description="Current iteration number (0-indexed).")
    result_count: int = Field(..., description="Number of search results returned.")
    duration_ms: int = Field(
        ..., description="Time taken for query compilation and execution (ms)."
    )


class SpotlightEvaluatingEvent(BaseModel):
    """Emitted after the evaluator assesses search results.

    Contains the full evaluation (reasoning + should_continue).

    Also includes results_shown / results_total and history_shown / history_total
    so consumers can see how much context the evaluator actually saw.
    """

    type: Literal["evaluating"] = "evaluating"
    iteration: int = Field(..., description="Current iteration number (0-indexed).")
    evaluation: SpotlightEvaluation = Field(..., description="The full evaluation.")
    results_shown: int = Field(
        ..., description="Number of search results included in the evaluator prompt."
    )
    results_total: int = Field(
        ..., description="Total number of search results returned by the search engine."
    )
    history_shown: int = Field(
        ..., description="Number of detailed history iterations included in the evaluator prompt."
    )
    history_total: int = Field(..., description="Total number of past iterations.")


class SpotlightDoneEvent(BaseModel):
    """Emitted when the search is complete.

    Contains the full response with results and composed answer.
    """

    type: Literal["done"] = "done"
    response: SpotlightResponse = Field(..., description="The complete search response.")


class SpotlightErrorEvent(BaseModel):
    """Emitted when an error occurs during search."""

    type: Literal["error"] = "error"
    message: str = Field(..., description="Error description.")


SpotlightEvent = Annotated[
    Union[
        SpotlightPlanningEvent,
        SpotlightSearchingEvent,
        SpotlightEvaluatingEvent,
        SpotlightDoneEvent,
        SpotlightErrorEvent,
    ],
    Field(discriminator="type"),
]
