"""Domain events for the search domain (all tiers).

Lifecycle events (started, completed, failed) are shared across instant,
classic, and agentic tiers. Thinking and tool_called are agentic-specific.
Reranking applies to classic and agentic.

Each event separates user-facing fields (rendered in frontend, shown in SSE)
from diagnostics (consumed by evals repo, analytics, internal debugging).

Consumers:
- AgenticSearchStreamRelay: Bridges to PubSub for SSE streaming
- AnalyticsEventSubscriber: Tracks completed/failed in PostHog
- UsageBillingListener: Records query usage on completion
- Evals repo: Reads diagnostics from SSE stream for metrics
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from airweave.core.events.base import DomainEvent
from airweave.core.events.enums import SearchEventType

# ── Diagnostics models ────────────────────────────────────────────────


class ThinkingDiagnostics(BaseModel):
    """Diagnostics for a single LLM iteration."""

    model_config = ConfigDict(frozen=True)

    iteration: int = Field(..., description="0-indexed iteration number.")


class ToolCalledDiagnostics(BaseModel):
    """Diagnostics for a tool call."""

    model_config = ConfigDict(frozen=True)

    iteration: int = Field(..., description="0-indexed iteration number.")
    tool_call_id: str = Field(..., description="LLM-assigned tool call ID.")
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Full LLM-generated tool input (e.g., SearchPlan for search tool).",
    )
    stats: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-tool result counts (result_count, found, not_found, etc.).",
    )


class RerankingDiagnostics(BaseModel):
    """Diagnostics for the reranking step."""

    model_config = ConfigDict(frozen=True)

    input_count: int = Field(..., description="Results before reranking.")
    output_count: int = Field(..., description="Results after reranking.")
    model: str = Field(..., description="Reranker model name (e.g., 'cohere/rerank-v4.0-pro').")
    top_relevance_score: float = Field(..., description="Highest reranker relevance score.")
    bottom_relevance_score: float = Field(..., description="Lowest reranker relevance score.")


class _AgentRunDiagnostics(BaseModel):
    """Shared diagnostics for completed/failed agentic search events."""

    model_config = ConfigDict(frozen=True)

    total_iterations: int = 0
    all_seen_entity_ids: list[str] = Field(default_factory=list)
    all_read_entity_ids: list[str] = Field(default_factory=list)
    all_collected_entity_ids: list[str] = Field(default_factory=list)
    max_iterations_hit: bool = False
    total_llm_retries: int = 0
    stagnation_nudges_sent: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class CompletedDiagnostics(_AgentRunDiagnostics):
    """Diagnostics for a successfully completed agentic search."""

    pass


class FailedDiagnostics(_AgentRunDiagnostics):
    """Diagnostics for a failed agentic search."""

    iteration: int = Field(0, description="Iteration where the failure occurred.")
    partial_results_count: int = Field(0, description="Results collected before failure.")


# ── Shared events (all tiers) ─────────────────────────────────────────


class SearchStartedEvent(DomainEvent):
    """Emitted before search begins. Captures the full user request.

    Used by analytics (filter adoption, thinking toggle, query patterns)
    and evals. Not rendered in the frontend.
    """

    event_type: SearchEventType = SearchEventType.STARTED

    request_id: str
    tier: str  # SearchTier value ("instant", "classic", "agentic")
    collection_readable_id: str
    query: str

    # Tier-specific (optional)
    retrieval_strategy: Optional[str] = None  # RetrievalStrategy value, instant only
    thinking: Optional[bool] = None  # agentic only
    filter: Optional[list[dict[str, Any]]] = None  # serialized FilterGroups
    limit: Optional[int] = None
    offset: Optional[int] = None  # instant/classic only


class SearchCompletedEvent(DomainEvent):
    """Emitted when search completes successfully.

    Shared across all tiers. Diagnostics only populated for agentic.
    """

    event_type: SearchEventType = SearchEventType.COMPLETED

    request_id: str
    tier: str  # SearchTier value ("instant", "classic", "agentic")

    # User-facing
    results: list[dict[str, Any]] = Field(default_factory=list)  # serialized SearchResults
    duration_ms: int

    # Diagnostics (agentic only, None for instant/classic)
    diagnostics: Optional[CompletedDiagnostics] = None

    # Billing
    billable: bool = True
    collection_id: Optional[UUID] = None


class SearchFailedEvent(DomainEvent):
    """Emitted when search fails with an error.

    Shared across all tiers. Diagnostics only populated for agentic.
    """

    event_type: SearchEventType = SearchEventType.FAILED

    request_id: str
    tier: str  # SearchTier value ("instant", "classic", "agentic")

    # User-facing
    message: str
    duration_ms: int

    # Diagnostics (agentic only, None for instant/classic)
    diagnostics: Optional[FailedDiagnostics] = None


# ── Shared events (classic + agentic) ─────────────────────────────────


class SearchRerankingEvent(DomainEvent):
    """Emitted after the optional reranking step on results."""

    event_type: SearchEventType = SearchEventType.RERANKING

    request_id: str

    # User-facing
    duration_ms: int

    # Diagnostics
    diagnostics: RerankingDiagnostics


# ── Agentic-only events ───────────────────────────────────────────────


class SearchThinkingEvent(DomainEvent):
    """Emitted once per iteration after the LLM responds.

    Agentic only.
    - thinking: extended reasoning / chain-of-thought (ephemeral in some providers)
    - text: model's conversational output before tool calls
    Both are passed back to the LLM in the assistant message on the next turn.
    """

    event_type: SearchEventType = SearchEventType.THINKING

    request_id: str

    # User-facing
    thinking: Optional[str] = None  # extended reasoning (e.g., Anthropic thinking blocks)
    text: Optional[str] = None  # conversational text output
    duration_ms: int

    # Diagnostics
    diagnostics: ThinkingDiagnostics


class SearchToolCalledEvent(DomainEvent):
    """Emitted after each tool call completes.

    Agentic only. diagnostics.arguments contains the full LLM-generated
    tool input (e.g., SearchPlan with query expansions for the search tool).
    """

    event_type: SearchEventType = SearchEventType.TOOL_CALLED

    request_id: str

    # User-facing
    tool_name: str
    duration_ms: int

    # Diagnostics
    diagnostics: ToolCalledDiagnostics
