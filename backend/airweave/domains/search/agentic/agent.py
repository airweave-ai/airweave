"""Agentic search agent — the core orchestration loop.

Drives an LLM conversation with tool calling to iteratively search,
read, and collect relevant entities from the vector database.

The agent is constructed per-request by AgenticSearchService and
delegates to:
- ToolDispatcher for tool execution
- ContextManager for context window management
- Messages module for LLM message formatting
- EventBus for event emission
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Optional

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.core.events.search import (
    CompletedDiagnostics,
    FailedDiagnostics,
    RerankingDiagnostics,
    SearchCompletedEvent,
    SearchFailedEvent,
    SearchRerankingEvent,
    SearchThinkingEvent,
    SearchToolCalledEvent,
    ThinkingDiagnostics,
    ToolCalledDiagnostics,
)
from airweave.core.protocols.event_bus import EventBus
from airweave.core.protocols.llm import LLMProtocol
from airweave.core.protocols.reranker import RerankerProtocol
from airweave.core.protocols.tokenizer import TokenizerProtocol
from airweave.domains.collections.protocols import CollectionRepositoryProtocol
from airweave.domains.search.adapters.vector_db.protocol import VectorDBProtocol
from airweave.domains.search.agentic.context_manager import ContextManager
from airweave.domains.search.agentic.exceptions import (
    ContextBudgetExhaustedError,
    ToolError,
)
from airweave.domains.search.agentic.messages import (
    build_assistant_message,
    build_system_prompt,
    build_tool_result_message,
    build_user_message,
)
from airweave.domains.search.agentic.state import AgentState
from airweave.domains.search.agentic.tools import (
    ALL_TOOL_DEFINITIONS,
    AddToResultsTool,
    CountTool,
    GetChildrenTool,
    GetParentTool,
    GetSiblingsTool,
    ReadTool,
    RemoveFromResultsTool,
    ReturnResultsTool,
    ReviewResultsTool,
    SearchTool,
    ToolDispatcher,
)
from airweave.domains.search.agentic.tools.types import (
    CollectToolResult,
    CountToolResult,
    FinishToolResult,
    NavigateToolResult,
    ReadToolResult,
    ReviewToolResult,
    SearchToolResult,
    ToolErrorResult,
    ToolName,
)
from airweave.domains.search.config import SearchConfig
from airweave.domains.search.protocols import (
    CollectionMetadataBuilderProtocol,
    SearchPlanExecutorProtocol,
)
from airweave.domains.search.types import SearchResults
from airweave.schemas.search_v2 import SearchTier

if TYPE_CHECKING:
    from airweave.schemas.search_v2 import AgenticSearchRequest


class Agent:
    """Agentic search agent — iterative LLM + tool calling loop."""

    def __init__(
        self,
        llm: LLMProtocol,
        tokenizer: TokenizerProtocol,
        reranker: Optional[RerankerProtocol],
        executor: SearchPlanExecutorProtocol,
        vector_db: VectorDBProtocol,
        metadata_builder: CollectionMetadataBuilderProtocol,
        collection_repo: CollectionRepositoryProtocol,
        event_bus: EventBus,
        config: SearchConfig,
    ) -> None:
        """Initialize with all dependencies (injected by service)."""
        self._llm = llm
        self._tokenizer = tokenizer
        self._reranker = reranker
        self._executor = executor
        self._vector_db = vector_db
        self._metadata_builder = metadata_builder
        self._collection_repo = collection_repo
        self._event_bus = event_bus
        self._config = config

    async def run(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: AgenticSearchRequest,
    ) -> SearchResults:
        """Run the agent loop. Emits events throughout. Returns collected results."""
        start_time = time.monotonic()
        state = AgentState()
        diag = _DiagnosticsAccumulator()

        try:
            return await self._run(db, ctx, readable_id, request, state, start_time, diag)
        except Exception as e:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            await self._event_bus.publish(
                SearchFailedEvent(
                    organization_id=ctx.organization.id,
                    request_id=ctx.request_id,
                    tier=SearchTier.AGENTIC.value,
                    message=str(e),
                    duration_ms=duration_ms,
                    diagnostics=FailedDiagnostics(
                        iteration=diag.iteration,
                        partial_results_count=len(state.collected_ids),
                        all_seen_entity_ids=list(state.results.keys()),
                        all_collected_entity_ids=list(state.collected_ids),
                        prompt_tokens=diag.prompt_tokens,
                        completion_tokens=diag.completion_tokens,
                        cache_creation_input_tokens=diag.cache_creation,
                        cache_read_input_tokens=diag.cache_read,
                        stagnation_nudges_sent=diag.stagnation_nudges,
                        max_iterations_hit=diag.max_iterations_hit,
                    ),
                )
            )
            raise

    async def _run(
        self,
        db: AsyncSession,
        ctx: ApiContext,
        readable_id: str,
        request: AgenticSearchRequest,
        state: AgentState,
        start_time: float,
        diag: _DiagnosticsAccumulator,
    ) -> SearchResults:
        """Internal run method — the actual agent loop."""
        config = self._config

        # ── SETUP ──────────────────────────────────────────────────────
        collection = await self._collection_repo.get_by_readable_id(db, readable_id, ctx)
        if not collection:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{readable_id}' not found",
            )
        collection_id = str(collection.id)

        metadata = await self._metadata_builder.build(db, ctx, readable_id)
        system_prompt = build_system_prompt(metadata, config.MAX_ITERATIONS)
        user_filter = request.filter or []
        messages: list[dict] = [build_user_message(request.query, user_filter)]
        thinking_enabled = request.thinking

        # Construct per-request tools
        dispatcher = self._build_dispatcher(collection_id, user_filter)

        context_mgr = ContextManager(
            tokenizer=self._tokenizer,
            context_window=self._llm.model_spec.context_window,
            max_output_tokens=self._llm.model_spec.max_output_tokens,
            thinking_enabled=thinking_enabled,
            system_prompt=system_prompt,
            tools=ALL_TOOL_DEFINITIONS,
        )

        # ── ITERATION LOOP ─────────────────────────────────────────────
        max_iter = config.MAX_ITERATIONS
        no_tool_call_nudges = 0
        iterations_since_last_collect = 0
        prev_search_ids: set[str] = set()
        prev_read_ids: set[str] = set()

        for iteration in range(max_iter):
            diag.iteration = iteration

            # 1. Call LLM
            llm_start = time.monotonic()
            response = await self._llm.chat(
                messages, ALL_TOOL_DEFINITIONS, system_prompt, thinking=thinking_enabled
            )
            llm_duration = int((time.monotonic() - llm_start) * 1000)

            # 2. Accumulate token counts and retries
            diag.prompt_tokens += response.prompt_tokens
            diag.completion_tokens += response.completion_tokens
            diag.cache_creation += response.cache_creation_input_tokens
            diag.cache_read += response.cache_read_input_tokens
            diag.llm_retries += response.retries

            # 3. Emit thinking event
            await self._event_bus.publish(
                SearchThinkingEvent(
                    organization_id=ctx.organization.id,
                    request_id=ctx.request_id,
                    thinking=response.thinking,
                    text=response.text,
                    duration_ms=llm_duration,
                    diagnostics=ThinkingDiagnostics(iteration=iteration),
                )
            )

            # 4. Build assistant message
            messages.append(build_assistant_message(response))

            # 5. Handle no tool calls
            if not response.tool_calls:
                no_tool_call_nudges += 1
                if no_tool_call_nudges >= 3:
                    ctx.logger.debug(
                        f"[Agent] Forced finish: no tool calls after {no_tool_call_nudges} nudges"
                    )
                    break
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "You must use tools to interact. "
                            "Call `search` to find results, `read` to examine them, "
                            "`add_to_results` to collect them, "
                            "or `return_results_to_user` to end."
                        ),
                    }
                )
                continue

            no_tool_call_nudges = 0
            collected_before = len(state.collected_ids)

            # 6. Compress old iterations
            new_search_ids: set[str] = set()
            new_read_ids: set[str] = set()
            messages = context_mgr.compress_history(
                messages,
                state,
                new_search_ids,
                new_read_ids,
                prev_search_ids,
                prev_read_ids,
            )

            # 7. Safety check
            if not context_mgr.check_budget(messages):
                raise ContextBudgetExhaustedError(
                    "Context window too full for useful work after compression"
                )

            # 8. Execute tool calls
            await self._execute_tool_calls(
                response.tool_calls,
                state,
                dispatcher,
                context_mgr,
                messages,
                ctx,
                iteration,
                new_search_ids,
                new_read_ids,
            )

            # 9. Check finish
            if state.should_finish:
                ctx.logger.debug(
                    f"[Agent] Agent finished at iteration {iteration}, "
                    f"{len(state.collected_ids)} results collected"
                )
                break

            # 10. Stagnation detection
            if len(state.collected_ids) > collected_before:
                iterations_since_last_collect = 0
            else:
                iterations_since_last_collect += 1

            if iterations_since_last_collect >= config.STAGNATION_THRESHOLD:
                diag.stagnation_nudges += 1
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"[System] You haven't added new results in "
                            f"{iterations_since_last_collect} iterations. "
                            "Go back and re-read results you may have skipped. "
                            "If you've covered the search space, call "
                            "return_results_to_user."
                        ),
                    }
                )

            # 11. Iteration warnings + progress
            self._append_iteration_messages(messages, state, iteration, max_iter)

            # 13. Rotate context tiers
            prev_search_ids = new_search_ids
            prev_read_ids = new_read_ids

        else:
            # Loop exhausted without break — max iterations hit
            diag.max_iterations_hit = True
            ctx.logger.debug(
                f"[Agent] Max iterations ({max_iter}) reached, "
                f"{len(state.collected_ids)} results collected"
            )

        # ── FINALIZATION ───────────────────────────────────────────────
        collected_results = [
            state.results[eid] for eid in state.collected_ids if eid in state.results
        ]

        # Optional reranking
        if self._reranker and collected_results:
            rerank_start = time.monotonic()
            reranked = await self._reranker.rerank(
                query=request.query,
                documents=[r.textual_representation for r in collected_results],
            )
            rerank_duration = int((time.monotonic() - rerank_start) * 1000)

            # Reorder results by reranker scores
            reranked_results = [collected_results[r.index] for r in reranked]

            await self._event_bus.publish(
                SearchRerankingEvent(
                    organization_id=ctx.organization.id,
                    request_id=ctx.request_id,
                    duration_ms=rerank_duration,
                    diagnostics=RerankingDiagnostics(
                        input_count=len(collected_results),
                        output_count=len(reranked_results),
                        model="cohere/rerank-v4.0-pro",
                        top_relevance_score=(reranked[0].relevance_score if reranked else 0.0),
                        bottom_relevance_score=(reranked[-1].relevance_score if reranked else 0.0),
                    ),
                )
            )
            collected_results = reranked_results

        # Emit completed event
        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Deduplicate entity IDs to original IDs
        all_read_ids = list(
            {
                r.airweave_system_metadata.original_entity_id
                for results in state.reads_by_tool_call_id.values()
                for r in results
            }
        )

        await self._event_bus.publish(
            SearchCompletedEvent(
                organization_id=ctx.organization.id,
                request_id=ctx.request_id,
                tier=SearchTier.AGENTIC.value,
                results=[r.model_dump(mode="json") for r in collected_results],
                duration_ms=duration_ms,
                diagnostics=CompletedDiagnostics(
                    total_iterations=diag.iteration + 1,
                    all_seen_entity_ids=list(state.results.keys()),
                    all_read_entity_ids=all_read_ids,
                    all_collected_entity_ids=list(state.collected_ids),
                    max_iterations_hit=diag.max_iterations_hit,
                    total_llm_retries=diag.llm_retries,
                    stagnation_nudges_sent=diag.stagnation_nudges,
                    prompt_tokens=diag.prompt_tokens,
                    completion_tokens=diag.completion_tokens,
                    cache_creation_input_tokens=diag.cache_creation,
                    cache_read_input_tokens=diag.cache_read,
                ),
                collection_id=collection.id,
            )
        )

        return SearchResults(results=collected_results)

    @staticmethod
    def _append_iteration_messages(
        messages: list[dict],
        state: AgentState,
        iteration: int,
        max_iter: int,
    ) -> None:
        """Append iteration warnings and progress message."""
        remaining = max_iter - iteration - 1
        if remaining == max_iter // 4:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"[System] You have {remaining} iterations remaining. "
                        "Start wrapping up: collect promising results and "
                        "prepare to call return_results_to_user."
                    ),
                }
            )
        elif remaining == 2:
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "[System] URGENT: 2 iterations left. "
                        "Collect remaining results with add_to_results, "
                        "then call return_results_to_user."
                    ),
                }
            )
        elif remaining == 1:
            messages.append(
                {
                    "role": "user",
                    "content": ("[System] FINAL ITERATION. Call return_results_to_user now."),
                }
            )

        messages.append(
            {
                "role": "user",
                "content": (
                    f"[Progress] Iteration {iteration + 1}/{max_iter} | "
                    f"Results seen: {len(state.results)} | "
                    f"Collected: {len(state.collected_ids)}"
                ),
            }
        )

    async def _execute_tool_calls(
        self,
        tool_calls: list,
        state: AgentState,
        dispatcher: ToolDispatcher,
        context_mgr: ContextManager,
        messages: list[dict],
        ctx: ApiContext,
        iteration: int,
        new_search_ids: set[str],
        new_read_ids: set[str],
    ) -> None:
        """Execute all tool calls, emit events, fit results into context."""
        for tc in tool_calls:
            tc_start = time.monotonic()
            try:
                result = await dispatcher.dispatch(tc, state)
            except ToolError as e:
                result = ToolErrorResult(error=str(e))
            except Exception as e:
                result = ToolErrorResult(error=f"Unexpected error: {e}")
            tc_duration = int((time.monotonic() - tc_start) * 1000)

            await self._event_bus.publish(
                SearchToolCalledEvent(
                    organization_id=ctx.organization.id,
                    request_id=ctx.request_id,
                    tool_name=tc.name,
                    duration_ms=tc_duration,
                    diagnostics=ToolCalledDiagnostics(
                        iteration=iteration,
                        tool_call_id=tc.id,
                        arguments=tc.arguments,
                        stats=_build_tool_stats(result),
                    ),
                )
            )

            content = context_mgr.fit_tool_result(result, messages)
            messages.append(build_tool_result_message(tc.id, tc.name, content))

            if tc.name in (
                ToolName.SEARCH,
                ToolName.GET_CHILDREN,
                ToolName.GET_SIBLINGS,
            ):
                new_search_ids.add(tc.id)
            elif tc.name in (ToolName.READ, ToolName.GET_PARENT):
                new_read_ids.add(tc.id)

    def _build_dispatcher(self, collection_id: str, user_filter: list) -> ToolDispatcher:
        """Construct tools and dispatcher for this request."""
        return ToolDispatcher(
            {
                ToolName.SEARCH: SearchTool(
                    executor=self._executor,
                    user_filter=user_filter,
                    collection_id=collection_id,
                ),
                ToolName.READ: ReadTool(
                    vector_db=self._vector_db,
                    collection_id=collection_id,
                    surrounding_chunks=self._config.READ_SURROUNDING_CHUNKS,
                ),
                ToolName.ADD_TO_RESULTS: AddToResultsTool(),
                ToolName.REMOVE_FROM_RESULTS: RemoveFromResultsTool(),
                ToolName.COUNT: CountTool(
                    vector_db=self._vector_db,
                    collection_id=collection_id,
                    user_filter=user_filter,
                ),
                ToolName.GET_CHILDREN: GetChildrenTool(
                    vector_db=self._vector_db,
                    collection_id=collection_id,
                ),
                ToolName.GET_SIBLINGS: GetSiblingsTool(
                    vector_db=self._vector_db,
                    collection_id=collection_id,
                ),
                ToolName.GET_PARENT: GetParentTool(
                    vector_db=self._vector_db,
                    collection_id=collection_id,
                ),
                ToolName.REVIEW_RESULTS: ReviewResultsTool(),
                ToolName.RETURN_RESULTS: ReturnResultsTool(),
            }
        )


def _build_tool_stats(result: object) -> dict:
    """Build stats dict from a tool result for the ToolCalledEvent."""
    if isinstance(result, SearchToolResult):
        return {
            "result_count": len(result.summaries),
            "new_results": result.new_count,
        }
    if isinstance(result, ReadToolResult):
        return {
            "found": len(result.entities),
            "not_found": len(result.not_found),
        }
    if isinstance(result, CollectToolResult):
        return {"total_collected": result.total_collected}
    if isinstance(result, CountToolResult):
        return {"count": result.count}
    if isinstance(result, NavigateToolResult):
        return {"result_count": len(result.summaries)}
    if isinstance(result, ReviewToolResult):
        return {"total_collected": result.total_collected}
    if isinstance(result, FinishToolResult):
        return {"accepted": result.accepted, "total_collected": result.total_collected}
    if isinstance(result, ToolErrorResult):
        return {"error": result.error}
    return {}


class _DiagnosticsAccumulator:
    """Mutable accumulator for diagnostics across iterations."""

    def __init__(self) -> None:
        """Initialize counters."""
        self.iteration: int = 0
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.cache_creation: int = 0
        self.cache_read: int = 0
        self.llm_retries: int = 0
        self.stagnation_nudges: int = 0
        self.max_iterations_hit: bool = False
