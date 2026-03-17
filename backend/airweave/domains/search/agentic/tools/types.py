"""Typed result objects for agentic search tools.

Tools render their results (summaries or full content) and return them
as pre-rendered strings. The context manager decides how many fit
in the LLM context window.

- Search/navigate tools: return summaries (via SearchResult.to_snippet_summary_md())
- Read/review tools: return full content (via SearchResult.to_md())
- Collect/count/finish: return structured data (no rendering needed)
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RenderedResult:
    """A pre-rendered search result (summary or full content).

    The tool decides the format (summary vs full). The containing result
    type (SearchToolResult vs ReadToolResult) signals which it is.
    The context manager uses `text` for length measurement and truncation.
    """

    entity_id: str
    text: str


@dataclass(frozen=True)
class SearchToolResult:
    """Result from the search tool — summaries for discovered entities."""

    summaries: list[RenderedResult]
    new_count: int
    requested_limit: int = 0  # for pagination warning
    requested_offset: int = 0  # for pagination warning


@dataclass(frozen=True)
class ReadToolResult:
    """Result from the read tool — full content of requested entities."""

    entities: list[RenderedResult]
    not_found: list[str]
    read_entity_ids: list[str] = field(default_factory=list)  # for triage nudge


@dataclass(frozen=True)
class CollectToolResult:
    """Result from add_to_results or remove_from_results."""

    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    already_collected: list[str] = field(default_factory=list)
    not_found: list[str] = field(default_factory=list)
    total_collected: int = 0


@dataclass(frozen=True)
class CountToolResult:
    """Result from the count tool."""

    count: int


@dataclass(frozen=True)
class NavigateToolResult:
    """Result from get_children, get_siblings, or get_parent."""

    summaries: list[RenderedResult]  # navigation results rendered as summaries
    context_label: str


@dataclass(frozen=True)
class ReviewToolResult:
    """Result from review_results — full content of collected entities."""

    entities: list[RenderedResult]
    total_collected: int


@dataclass(frozen=True)
class FinishToolResult:
    """Result from return_results_to_user."""

    accepted: bool
    warning: str | None = None
    total_collected: int = 0


@dataclass(frozen=True)
class ToolErrorResult:
    """Returned to the LLM when a ToolError is caught by the dispatcher."""

    error: str
