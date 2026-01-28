"""Context building utilities for agentic search.

This module provides utilities for building LLM context in the agentic search loop.
It includes:
- Airweave background (static): Explains how Airweave works
- Collection info: Describes the sources, entity types, and fields in a collection
- Search history: Formats previous iterations (plans, queries, judgements)
- Results formatting: Formats search results for LLM consumption

Both the Planner and Judge use these utilities to build their prompts.
"""

from airweave.search.agentic_search.context.airweave_background import AIRWEAVE_BACKGROUND
from airweave.search.agentic_search.context.collection_info import (
    CollectionInfoBuilder,
    CollectionInfoError,
)
from airweave.search.agentic_search.context.results import ResultsFormatter
from airweave.search.agentic_search.context.search_history import (
    IterationSummary,
    SearchHistoryBuilder,
)

__all__ = [
    # Static background
    "AIRWEAVE_BACKGROUND",
    # Collection info
    "CollectionInfoBuilder",
    "CollectionInfoError",
    # Search history
    "IterationSummary",
    "SearchHistoryBuilder",
    # Results formatting
    "ResultsFormatter",
]
