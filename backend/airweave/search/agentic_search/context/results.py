"""Search results formatting for agentic search context.

This module provides utilities for formatting search results as markdown for LLM prompts.
Used by the Judge to evaluate search results.

IMPORTANT: Never truncate result data. The reasoning model can handle full content.
Budget management is done by omitting entire results, not by truncating content.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from airweave.schemas.search_result import AirweaveSearchResult


class ResultsFormatter:
    """Formats search results for LLM context.

    Handles budget management by including full results until budget exhausted,
    then omitting the rest entirely (NEVER truncates individual result content).

    Usage:
        formatter = ResultsFormatter()
        markdown = formatter.format_results_markdown(results)
        markdown, count = formatter.format_results_with_budget(results, max_tokens, token_counter)
    """

    @staticmethod
    def format_result_markdown(result: AirweaveSearchResult) -> str:
        """Format a single result as markdown with FULL content.

        Dumps the entire entity as JSON - never truncates or omits fields.
        The reasoning model can handle the full data.

        Args:
            result: The search result to format

        Returns:
            Markdown header + full JSON dump of the result
        """
        # Header for readability
        lines = [
            f"### {result.name} (score: {result.score:.4f})",
            "",
            "```json",
            result.model_dump_json(indent=2),
            "```",
            "",
            "---",
            "",
        ]

        return "\n".join(lines)

    @staticmethod
    def format_results_markdown(
        results: List[AirweaveSearchResult],
        max_results: Optional[int] = None,
    ) -> str:
        """Format results as markdown.

        Args:
            results: Search results (assumed sorted by score, highest first)
            max_results: Maximum number of results to include (None = all)

        Returns:
            Markdown-formatted results
        """
        if not results:
            return "(No results)"

        results_to_format = results[:max_results] if max_results else results

        lines = [f"**Total results:** {len(results)}", ""]

        if max_results and len(results) > max_results:
            lines.append(f"*Showing top {max_results} results (highest scores first)*")
            lines.append("")

        for result in results_to_format:
            lines.append(ResultsFormatter.format_result_markdown(result))

        return "\n".join(lines)

    @staticmethod
    def format_results_with_budget(
        results: List[AirweaveSearchResult],
        max_tokens: int,
        token_counter: callable,
    ) -> Tuple[str, int]:
        """Format results to fit within token budget.

        Strategy:
        1. Start with highest-scoring results
        2. Add FULL results until budget exhausted
        3. Omit remaining results entirely (no truncation)

        Args:
            results: Search results (assumed sorted by score, highest first)
            max_tokens: Token budget
            token_counter: Function to count tokens in a string

        Returns:
            Tuple of (markdown string, number of results included)
        """
        if not results:
            return "(No results)", 0

        # Build up results starting from highest-scoring
        included_results: List[AirweaveSearchResult] = []
        current_tokens = 0

        # Reserve some tokens for header
        header_estimate = 50  # Approximate tokens for "Total results: X" etc.
        available_tokens = max_tokens - header_estimate

        for result in results:
            result_md = ResultsFormatter.format_result_markdown(result)
            result_tokens = token_counter(result_md)

            if current_tokens + result_tokens > available_tokens:
                break  # Can't fit this result

            included_results.append(result)
            current_tokens += result_tokens

        if not included_results:
            return (
                f"(Results omitted to fit context window - {len(results)} total)",
                0,
            )

        # Format the included results
        lines = [f"**Total results:** {len(results)}", ""]

        included_count = len(included_results)
        if included_count < len(results):
            omitted = len(results) - included_count
            lines.append(
                f"*Showing top {included_count} results (highest scores). "
                f"{omitted} lower-scoring results omitted to fit context.*"
            )
            lines.append("")

        for result in included_results:
            lines.append(ResultsFormatter.format_result_markdown(result))

        return "\n".join(lines), included_count

    @staticmethod
    def format_result_summary(result: AirweaveSearchResult) -> str:
        """Format a single result as a brief one-line summary.

        Used to indicate omitted results (when full results don't fit in budget).
        NOT a replacement for full content - just shows what was omitted.

        Args:
            result: The search result to format

        Returns:
            Brief summary line with key identifying info
        """
        return (
            f"- {result.name} (score: {result.score:.3f}, "
            f"type: {result.system_metadata.entity_type}, "
            f"id: {result.entity_id})"
        )

    @staticmethod
    def format_results_summary_list(
        results: List[AirweaveSearchResult],
        max_results: Optional[int] = None,
    ) -> str:
        """Format results as a brief summary list (no full content).

        Useful for showing what results exist when full content doesn't fit.

        Args:
            results: Search results (assumed sorted by score, highest first)
            max_results: Maximum number to include (None = all)

        Returns:
            Markdown list of result summaries
        """
        if not results:
            return "(No results)"

        results_to_format = results[:max_results] if max_results else results

        lines = [
            f"**Results summary** ({len(results)} total):",
            "",
        ]

        for result in results_to_format:
            lines.append(ResultsFormatter.format_result_summary(result))

        if max_results and len(results) > max_results:
            lines.append(f"- ... and {len(results) - max_results} more")

        return "\n".join(lines)
