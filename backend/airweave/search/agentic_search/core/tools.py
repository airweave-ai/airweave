"""Tool definitions and execution for the agentic search conversation loop.

Defines two tools the model can call:
- `search`: Search the vector database with query, filters, strategy, etc.
- `submit_answer`: Submit the final answer with text and citations.

Each tool has:
1. A definition dict (OpenAI-compatible function format) sent to the LLM
2. An async execution function that runs server-side when the model calls the tool
"""

import time
from typing import Any

from pydantic import BaseModel, Field

from airweave.domains.embedders.protocols import DenseEmbedderProtocol, SparseEmbedderProtocol
from airweave.search.agentic_search.builders.complete_plan import (
    AgenticSearchCompletePlanBuilder,
)
from airweave.search.agentic_search.config import CHARS_PER_TOKEN
from airweave.search.agentic_search.external.vector_database.interface import (
    AgenticSearchVectorDBInterface,
)
from airweave.search.agentic_search.schemas.answer import (
    AgenticSearchAnswer,
    AgenticSearchCitation,
)
from airweave.search.agentic_search.schemas.filter import AgenticSearchFilterGroup
from airweave.search.agentic_search.schemas.plan import AgenticSearchPlan
from airweave.search.agentic_search.schemas.search_result import (
    AgenticSearchResult,
    AgenticSearchResults,
)

# ── Constants ──────────────────────────────────────────────────────────

# Max share of context window a single tool result should occupy
MAX_TOOL_RESULT_CONTEXT_SHARE = 0.3

# ── Internal payload model ─────────────────────────────────────────────


class SubmitAnswerPayload(BaseModel):
    """Internal model for parsing the LLM's submit_answer tool call.

    Mirrors AgenticSearchAnswer fields plus an optional consolidation_search.
    This model is INTERNAL ONLY — never serialized to the API consumer.
    """

    text: str = Field(
        ...,
        description="The answer text. Should be clear and well-structured.",
    )
    citations: list[AgenticSearchCitation] = Field(
        ...,
        description="List of entity_ids from search results used to compose the answer.",
    )
    consolidation_search: AgenticSearchPlan | None = Field(
        default=None,
        description=(
            "Optional final search plan. Provide this ONLY when you could NOT find "
            "a direct answer. Design it to re-retrieve the MOST relevant results "
            "you saw during the conversation so we can return them to the user. "
            "This is not about discovering new things — target the specific results "
            "that were closest to answering the query. Omit when you DID find the answer."
        ),
    )


# ── Tool definitions (sent to the LLM) ────────────────────────────────

SEARCH_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search",
        "description": (
            "Search the vector database for relevant entities. "
            "Use different retrieval strategies (semantic, keyword, hybrid) "
            "and filters to refine results."
        ),
        "parameters": AgenticSearchPlan.model_json_schema(),
    },
}

SUBMIT_ANSWER_TOOL: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "submit_answer",
        "description": (
            "Submit the final answer with citations. Call this when you have "
            "enough information to answer the user's query, or when further "
            "searching would not improve the answer. If you could NOT find a "
            "direct answer, include a consolidation_search plan to surface the "
            "most relevant results you found during the conversation."
        ),
        "parameters": SubmitAnswerPayload.model_json_schema(),
    },
}


# ── Tool execution ─────────────────────────────────────────────────────


async def execute_search_tool(
    arguments: dict[str, Any],
    user_filter: list[AgenticSearchFilterGroup],
    dense_embedder: DenseEmbedderProtocol,
    sparse_embedder: SparseEmbedderProtocol,
    vector_db: AgenticSearchVectorDBInterface,
    collection_id: str,
    context_window_tokens: int,
) -> tuple[str, list[AgenticSearchResult], int]:
    """Execute the search tool and return formatted results.

    Args:
        arguments: Tool call arguments (parsed from model output).
        user_filter: User-supplied deterministic filters to merge.
        dense_embedder: Dense embedder for semantic search.
        sparse_embedder: Sparse embedder for keyword search.
        vector_db: Vector database interface.
        collection_id: Collection readable ID.
        context_window_tokens: Context window size for result budget.

    Returns:
        Tuple of (formatted_text, result_objects, duration_ms).
    """
    from airweave.search.agentic_search.schemas.query_embeddings import (
        AgenticSearchQueryEmbeddings,
    )
    from airweave.search.agentic_search.schemas.retrieval_strategy import (
        AgenticSearchRetrievalStrategy,
    )

    start = time.monotonic()

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

    duration_ms = int((time.monotonic() - start) * 1000)

    # Format results with budget (Layer 1 context management)
    formatted_text = format_results_for_tool_response(
        search_results,
        context_window_tokens,
    )

    return formatted_text, search_results.results, duration_ms


def format_results_for_tool_response(
    results: AgenticSearchResults,
    context_window_tokens: int,
) -> str:
    """Format search results as text for the tool response.

    Includes results by relevance until the budget is exhausted.
    Individual results are never truncated — shown in full or not at all.

    Args:
        results: Search results from Vespa.
        context_window_tokens: Context window size in tokens.

    Returns:
        Formatted markdown string with results.
    """
    if not results.results:
        return "No results found."

    max_chars = int(context_window_tokens * MAX_TOOL_RESULT_CONTEXT_SHARE * CHARS_PER_TOKEN)

    parts: list[str] = []
    chars_used = 0
    results_shown = 0

    for result in results.results:
        result_md = result.to_md()
        result_chars = len(result_md)

        if chars_used + result_chars > max_chars and parts:
            break

        parts.append(result_md)
        chars_used += result_chars
        results_shown += 1

    total = len(results.results)
    header = f"**{results_shown} of {total} results** (by relevance):\n\n"

    if results_shown < total:
        footer = f"\n\n*(Showing top {results_shown} of {total} results)*"
    else:
        footer = ""

    return header + "\n\n---\n\n".join(parts) + footer


def parse_submit_answer(
    arguments: dict[str, Any],
) -> tuple[AgenticSearchAnswer, AgenticSearchPlan | None]:
    """Parse submit_answer tool arguments into an answer and optional consolidation plan.

    Uses SubmitAnswerPayload internally, then splits into:
    - AgenticSearchAnswer (API-facing, no consolidation field)
    - AgenticSearchPlan | None (internal consolidation search plan)
    """
    payload = SubmitAnswerPayload.model_validate(arguments)
    answer = AgenticSearchAnswer(
        text=payload.text,
        citations=payload.citations,
    )
    return answer, payload.consolidation_search
