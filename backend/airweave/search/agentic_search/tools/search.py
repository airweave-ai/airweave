"""Search tool: definition, execution, and handler.

The search tool allows the agent to query the vector database.
- SEARCH_TOOL: the tool definition dict sent to the LLM
- handle_search: the handler called when the agent invokes the tool
- execute_search: low-level execution (embed, compile, query)
- format_results_for_context: format results as markdown for the LLM context
"""

from typing import Any

from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.search.agentic_search.builders.complete_plan import (
    AgenticSearchCompletePlanBuilder,
)
from airweave.search.agentic_search.config import CHARS_PER_TOKEN
from airweave.search.agentic_search.emitter import AgenticSearchEmitter
from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall
from airweave.search.agentic_search.external.vector_database.interface import (
    AgenticSearchVectorDBInterface,
)
from airweave.search.agentic_search.schemas.filter import AgenticSearchFilterGroup
from airweave.search.agentic_search.schemas.plan import AgenticSearchPlan
from airweave.search.agentic_search.schemas.query_embeddings import (
    AgenticSearchQueryEmbeddings,
)
from airweave.search.agentic_search.schemas.retrieval_strategy import (
    AgenticSearchRetrievalStrategy,
)
from airweave.search.agentic_search.schemas.search_result import (
    AgenticSearchResult,
    AgenticSearchResults,
)
from airweave.search.agentic_search.schemas.state import AgenticSearchState
from airweave.search.agentic_search.services import AgenticSearchServices

# Reserve tokens for LLM response (reasoning + tool calls)
RESPONSE_RESERVE_TOKENS = 4096

# Minimum budget so we always show at least a few results
MIN_RESULT_BUDGET_TOKENS = 2048

# ── Tool definition (sent to the LLM) ────────────────────────────────

SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search",
        "description": (
            "Search the vector database for relevant entities. "
            "Use different queries, expansions, retrieval strategies (semantic, keyword, hybrid), "
            "limits and filters to refine results."
        ),
        "parameters": AgenticSearchPlan.model_json_schema(),
    },
}


# ── Handler (called by the dispatcher) ────────────────────────────────


async def handle_search(
    tc: LLMToolCall,
    state: AgenticSearchState,
    services: AgenticSearchServices,
    emitter: AgenticSearchEmitter,
    collection_id: str,
    user_filter: list,
    context_window_tokens: int,
) -> str:
    """Execute the search tool, merge results into state, return formatted content."""
    results = await execute_search(
        arguments=tc.arguments,
        user_filter=user_filter,
        dense_embedder=services.dense_embedder,
        sparse_embedder=services.sparse_embedder,
        vector_db=services.vector_db,
        collection_id=collection_id,
    )
    for r in results:
        if r.entity_id not in state.results:
            state.results[r.entity_id] = r
    state.results_by_tool_call_id[tc.id] = results
    available_tokens = _estimate_available_tokens(state.messages, context_window_tokens)
    requested_limit = tc.arguments.get("limit", 10)
    requested_offset = tc.arguments.get("offset", 0)
    return format_results_for_context(
        results,
        available_tokens,
        requested_limit=requested_limit,
        requested_offset=requested_offset,
    )


# ── Execution ─────────────────────────────────────────────────────────


async def execute_search(
    arguments: dict[str, Any],
    user_filter: list[AgenticSearchFilterGroup],
    dense_embedder: DenseEmbedderProtocol,
    sparse_embedder: SparseEmbedderProtocol,
    vector_db: AgenticSearchVectorDBInterface,
    collection_id: str,
) -> list[AgenticSearchResult]:
    """Execute the search tool and return raw results."""
    plan = AgenticSearchPlan.model_validate(arguments)

    # Merge with user filters
    complete_plan = AgenticSearchCompletePlanBuilder.build(plan, user_filter)

    # Embed queries based on retrieval strategy
    dense_embeddings = None
    sparse_embedding = None

    if plan.retrieval_strategy in (
        AgenticSearchRetrievalStrategy.SEMANTIC,
        AgenticSearchRetrievalStrategy.HYBRID,
    ):
        texts = [plan.query.primary] + list(plan.query.variations)
        dense_embeddings = await dense_embedder.embed_many(texts)

    if plan.retrieval_strategy in (
        AgenticSearchRetrievalStrategy.KEYWORD,
        AgenticSearchRetrievalStrategy.HYBRID,
    ):
        sparse_embedding = await sparse_embedder.embed(plan.query.primary)

    embeddings = AgenticSearchQueryEmbeddings(
        dense_embeddings=dense_embeddings,
        sparse_embedding=sparse_embedding,
    )

    # Compile and execute
    compiled_query = await vector_db.compile_query(
        plan=complete_plan,
        embeddings=embeddings,
        collection_id=collection_id,
    )
    search_results: AgenticSearchResults = await vector_db.execute_query(compiled_query)

    return search_results.results


# ── Context budget ─────────────────────────────────────────────────────


def _estimate_available_tokens(
    messages: list[dict],
    context_window_tokens: int,
) -> int:
    """Estimate how many tokens are available for new results.

    Sums character lengths of all messages, converts to token estimate,
    subtracts from context window with a reserve for the LLM response.
    """
    used_chars = sum(len(m.get("content", "") or "") for m in messages)
    used_tokens = used_chars // CHARS_PER_TOKEN
    available = context_window_tokens - used_tokens - RESPONSE_RESERVE_TOKENS
    return max(available, MIN_RESULT_BUDGET_TOKENS)


# ── Result formatting (truncation for context window) ─────────────────


def format_results_for_context(
    results: list[AgenticSearchResult],
    available_tokens: int,
    requested_limit: int | None = None,
    requested_offset: int = 0,
) -> str:
    """Format search results as markdown, fitting within the available token budget.

    Each result is included in full or not at all (never partially truncated).

    Returns:
        Formatted markdown string. May contain fewer results than provided
        if the budget is exceeded.
    """
    if not results:
        return "No results found."

    max_chars = available_tokens * CHARS_PER_TOKEN

    parts: list[str] = []
    chars_used = 0
    results_shown = 0

    for result in results:
        result_md = result.to_md()
        result_chars = len(result_md)

        if chars_used + result_chars > max_chars and parts:
            break

        parts.append(result_md)
        chars_used += result_chars
        results_shown += 1

    total = len(results)
    header = f"**{results_shown} of {total} results** (by relevance):\n\n"

    if results_shown < total:
        footer = f"\n\n*(Showing top {results_shown} of {total} results)*"
    else:
        footer = ""

    # Warn the agent when results hit the requested limit (more likely exist)
    pagination_warning = ""
    if requested_limit is not None and len(results) >= requested_limit:
        next_offset = requested_offset + requested_limit
        pagination_warning = (
            f"\n\n**Results hit the limit of {requested_limit}.** "
            f"More results likely exist. Search again with the same query "
            f"and filters but set offset={next_offset} to see the next page."
        )

    return header + "\n\n---\n\n".join(parts) + footer + pagination_warning
