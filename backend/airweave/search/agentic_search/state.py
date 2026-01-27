"""State management for agentic search loop."""

from dataclasses import dataclass, field
from typing import Any

from airweave.search.agentic_search.openai import QueryEmbeddings
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
        embeddings: Dict mapping iteration -> QueryEmbeddings (dense + sparse)
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
    embeddings: dict[int, QueryEmbeddings] = field(default_factory=dict)
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

    def format_for_logging(self, verbose: bool = False) -> str:
        """Format the state for readable logging output.

        Args:
            verbose: If True, include full details; if False, show summary only

        Returns:
            Multi-line string representation of the current state
        """
        w = 58  # Box width (inner content)

        def box_line(content: str) -> str:
            """Create a box line with proper padding."""
            return f"│ {content:<{w}} │"

        lines = [
            "",
            "┌" + "─" * (w + 2) + "┐",
            box_line("AGENTIC SEARCH STATE"),
            "├" + "─" * (w + 2) + "┤",
            box_line(f"Query: {self._truncate(self.original_query, w - 7)}"),
            box_line(f"Collection: {self.collection_id}"),
            box_line(f"Iteration: {self.iteration}/{self.max_iterations}"),
            "├" + "─" * (w + 2) + "┤",
        ]

        # Add all summary sections
        self._add_plans_summary(lines, box_line, w, verbose)
        self._add_simple_summaries(lines, box_line)
        self._add_errors_summary(lines, box_line, w, verbose)
        self._add_final_results_summary(lines, box_line)

        lines.append("└" + "─" * (w + 2) + "┘")
        return "\n".join(lines)

    def _add_plans_summary(self, lines: list, box_line: callable, w: int, verbose: bool) -> None:
        """Add plans summary to log output."""
        if not self.plans:
            lines.append(box_line("Plans: (none)"))
            return

        lines.append(box_line(f"Plans: {len(self.plans)} generated"))
        if verbose:
            for i, plan in sorted(self.plans.items()):
                queries_str = ", ".join(
                    f'"{q[:20]}..."' if len(q) > 20 else f'"{q}"' for q in plan.queries[:2]
                )
                if len(plan.queries) > 2:
                    queries_str += f" (+{len(plan.queries) - 2} more)"
                lines.append(box_line(f"  [{i}] {self._truncate(queries_str, w - 6)}"))

    def _add_simple_summaries(self, lines: list, box_line: callable) -> None:
        """Add embeddings, YQLs, results, and judgements summaries."""
        # Embeddings
        if self.embeddings:
            lines.append(box_line(f"Embeddings: {len(self.embeddings)} iteration(s)"))
        else:
            lines.append(box_line("Embeddings: (none)"))

        # YQLs
        if self.yqls:
            lines.append(box_line(f"YQLs: {len(self.yqls)} generated"))
        else:
            lines.append(box_line("YQLs: (none)"))

        # Results
        if self.results:
            total = sum(len(r) for r in self.results.values())
            lines.append(box_line(f"Results: {total} across {len(self.results)} iter(s)"))
        else:
            lines.append(box_line("Results: (none)"))

        # Judgements
        if self.judgements:
            lines.append(box_line(f"Judgements: {len(self.judgements)} received"))
        else:
            lines.append(box_line("Judgements: (none)"))

    def _add_errors_summary(self, lines: list, box_line: callable, w: int, verbose: bool) -> None:
        """Add errors summary to log output."""
        if not self.errors:
            lines.append(box_line("Errors: (none)"))
            return

        lines.append(box_line(f"Errors: {len(self.errors)} error(s)"))
        if verbose:
            for i, err in sorted(self.errors.items()):
                lines.append(box_line(f"  [{i}] {self._truncate(err, w - 6)}"))

    def _add_final_results_summary(self, lines: list, box_line: callable) -> None:
        """Add final results summary to log output."""
        if self.final_results is not None:
            lines.append(box_line(f"Final Results: {len(self.final_results)} result(s)"))
        else:
            lines.append(box_line("Final Results: (not yet set)"))

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Truncate text to max length, adding ellipsis if needed."""
        if len(text) <= max_len:
            return text
        return text[: max_len - 3] + "..."
