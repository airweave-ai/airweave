"""State management for agentic search loop."""

from dataclasses import dataclass, field
from typing import Any

from airweave.search.agentic_search.planner.schemas import SearchPlan

# TODO: type the yqls, results (AirweaveSearchResult), judgements, errors


@dataclass
class AgenticSearchState:
    """State container for the agentic search loop.

    This class holds all state that persists across iterations of the search loop.
    It is passed between the planner, builder, judge, and synthesizer components.

    Attributes:
        original_query: The user's original search query
        collection_id: The collection to search (readable ID)
        max_iterations: Maximum number of search iterations before stopping
        iteration: Current iteration number (0-indexed)
        collection_info: Markdown string describing the collection (built once)
        plans: Dict mapping iteration -> SearchPlan from the planner
        yqls: Dict mapping iteration -> YQL query string from the builder
        results: Dict mapping iteration -> search results from Vespa
        judgements: Dict mapping iteration -> judgement from the judge
        errors: Dict mapping iteration -> error message (if query failed)
        final_results: The final search results to use for synthesis (set by judge)
    """

    # Required inputs
    original_query: str
    collection_id: str

    # Configuration
    max_iterations: int = 5

    # Loop state
    iteration: int = 0

    # Built once (by planner on first iteration)
    collection_info: str | None = None

    # Per-iteration state (keyed by iteration number)
    plans: dict[int, SearchPlan] = field(default_factory=dict)
    yqls: dict[int, str] = field(default_factory=dict)
    results: dict[int, list[Any]] = field(default_factory=dict)
    judgements: dict[int, Any] = field(default_factory=dict)  # TODO: Judgement schema
    errors: dict[int, str] = field(default_factory=dict)

    # Final output (set when judge decides to stop)
    final_results: list[Any] | None = None

    @property
    def is_first_iteration(self) -> bool:
        """Check if this is the first iteration."""
        return self.iteration == 0

    @property
    def has_reached_max_iterations(self) -> bool:
        """Check if max iterations reached."""
        return self.iteration >= self.max_iterations

    @property
    def latest_plan(self) -> SearchPlan | None:
        """Get the most recent plan, if any."""
        if not self.plans:
            return None
        return self.plans[max(self.plans.keys())]

    @property
    def latest_results(self) -> list[Any] | None:
        """Get the most recent results, if any."""
        if not self.results:
            return None
        return self.results[max(self.results.keys())]

    @property
    def latest_error(self) -> str | None:
        """Get the most recent error, if any."""
        if self.iteration not in self.errors:
            return None
        return self.errors[self.iteration]
