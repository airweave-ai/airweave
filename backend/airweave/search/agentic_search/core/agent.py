"""Agentic search agent.

Conversation + tool-calling architecture:
  1. Build system prompt with collection metadata
  2. Send initial user message with the search query
  3. Loop: LLM reasons in free text, calls search tool
  4. Context is managed via pruning old tool results
  5. Return accumulated search results

The conversation IS the history — no separate state/history objects needed.
"""

import asyncio
import time
from collections.abc import Iterable

from airweave.api.context import ApiContext
from airweave.search.agentic_search.builders import (
    AgenticSearchCollectionMetadataBuilder,
)
from airweave.search.agentic_search.config import config as agentic_config
from airweave.search.agentic_search.core.context_manager import manage_context
from airweave.search.agentic_search.core.debug import (
    dump_conversation,
    log_agent_response,
    log_token_breakdown,
)
from airweave.search.agentic_search.core.messages import (
    build_assistant_message,
    build_initial_user_message,
    build_tool_result_message,
    load_system_prompt,
)
from airweave.search.agentic_search.emitter import AgenticSearchEmitter
from airweave.search.agentic_search.external.llm.tool_response import LLMToolCall, LLMToolResponse
from airweave.search.agentic_search.schemas import (
    AgenticSearchRequest,
    AgenticSearchResponse,
)
from airweave.search.agentic_search.schemas.events import (
    AgenticSearchDoneEvent,
    AgenticSearchErrorEvent,
    AgenticSearchThinkingEvent,
    AgenticSearchToolCallEvent,
)
from airweave.search.agentic_search.schemas.search_result import AgenticSearchResult
from airweave.search.agentic_search.schemas.state import AgenticSearchState
from airweave.search.agentic_search.services import AgenticSearchServices
from airweave.search.agentic_search.tools import (
    COUNT_TOOL,
    MARK_AS_RELEVANT_TOOL,
    READ_TOOL,
    RETURN_RESULTS_TOOL,
    REVIEW_MARKED_RESULTS_TOOL,
    SEARCH_TOOL,
    UNMARK_TOOL,
    handle_tool_call,
)


class AgenticSearchAgent:
    """Agentic search agent using conversation + tool calling."""

    def __init__(
        self,
        services: AgenticSearchServices,
        ctx: ApiContext,
        emitter: AgenticSearchEmitter,
    ) -> None:
        """Initialize the agent."""
        self.services = services
        self.ctx = ctx
        self.emitter = emitter

        self._collection_id: str = ""
        self._context_window_tokens: int = 0
        self._user_filter: list = []

    async def run(
        self,
        collection_readable_id: str,
        request: AgenticSearchRequest,
        is_streaming: bool = False,
    ) -> AgenticSearchResponse:
        """Run the agent."""
        try:
            return await self._run(collection_readable_id, request, is_streaming)
        except Exception as e:
            await self.emitter.emit(AgenticSearchErrorEvent(message=str(e)))
            raise

    async def _run(  # noqa: C901
        self,
        collection_readable_id: str,
        request: AgenticSearchRequest,
        is_streaming: bool = False,
    ) -> AgenticSearchResponse:
        """Internal run method with the conversation loop.

        All message mutations happen here so the conversation flow is
        readable top-to-bottom in one place.
        """
        state = AgenticSearchState()
        no_tool_call_nudges = 0
        iterations_since_last_mark = 0
        total_llm_retries = 0
        stagnation_nudges_sent = 0
        hit_max_iterations = False

        # Build collection metadata
        metadata_builder = AgenticSearchCollectionMetadataBuilder(self.services.db)
        collection_metadata = await metadata_builder.build(collection_readable_id)

        self._collection_id = collection_metadata.collection_id
        self._context_window_tokens = self.services.llm.model_spec.context_window
        self._user_filter = request.filter

        # Build system prompt and initial user message
        system_prompt = load_system_prompt(collection_metadata)
        state.messages.append(
            build_initial_user_message(
                user_query=request.query,
                user_filter=request.filter,
            )
        )
        tools = [
            SEARCH_TOOL,
            COUNT_TOOL,
            READ_TOOL,
            MARK_AS_RELEVANT_TOOL,
            UNMARK_TOOL,
            REVIEW_MARKED_RESULTS_TOOL,
            RETURN_RESULTS_TOOL,
        ]

        # Rolling windows for 3-tier context management
        prev_search_ids: set[str] = set()
        prev_read_ids: set[str] = set()

        self.ctx.logger.debug(
            f"[AgenticSearch] Starting agent loop for query: {request.query!r} "
            f"on collection: {collection_readable_id}"
        )

        while True:
            # Guard: cap iterations to prevent runaway loops
            max_iter = agentic_config.MAX_ITERATIONS
            if state.iteration >= max_iter:
                hit_max_iterations = True
                self.ctx.logger.warning(
                    f"[AgenticSearch] Hit max iterations ({max_iter}) "
                    f"for query: {request.query!r}. "
                    f"Returning {len(state.marked_entity_ids)} marked results."
                )
                break

            # Debug: dump conversation and log token breakdown
            dump_conversation(
                state.iteration,
                system_prompt,
                state.messages,
                tools,
                self.ctx.logger,
            )
            log_token_breakdown(
                state.iteration,
                system_prompt,
                state.messages,
                tools,
                self.services.tokenizer,
                self.ctx.logger,
            )

            # Call LLM with tools (with conversation-level retry)
            llm_failed = False
            response = None
            retry_delay = agentic_config.AGENT_LLM_RETRY_DELAY
            for attempt in range(agentic_config.AGENT_LLM_MAX_RETRIES + 1):
                try:
                    response = await self.services.llm.create_with_tools(
                        messages=state.messages,
                        tools=tools,
                        system_prompt=system_prompt,
                    )
                    break
                except Exception as e:
                    if attempt < agentic_config.AGENT_LLM_MAX_RETRIES and self._is_retryable(e):
                        total_llm_retries += 1
                        self.ctx.logger.warning(
                            f"[AgenticSearch] LLM call failed at iteration "
                            f"{state.iteration} (attempt {attempt + 1}/"
                            f"{agentic_config.AGENT_LLM_MAX_RETRIES + 1}), "
                            f"retrying in {retry_delay:.0f}s: {e}"
                        )
                        await asyncio.sleep(retry_delay)
                        retry_delay *= 2
                    else:
                        error_detail = str(e)
                        self.ctx.logger.error(
                            f"[AgenticSearch] LLM call failed at iteration "
                            f"{state.iteration} after {attempt + 1} attempt(s): {error_detail}"
                        )
                        await self.emitter.emit(
                            AgenticSearchToolCallEvent(
                                iteration=state.iteration,
                                tool_call_id="__llm_error__",
                                tool_name="__llm_error__",
                                arguments={},
                                result_summary={
                                    "error": error_detail,
                                    "attempts": attempt + 1,
                                    "partial_results": len(state.marked_entity_ids),
                                },
                                duration_ms=0,
                            )
                        )
                        llm_failed = True
                        break

            if llm_failed or response is None:
                break

            # Debug: log thinking + tool calls (search plans)
            log_agent_response(state.iteration, response, self.ctx.logger)

            # Emit thinking event with LLM usage stats
            await self._emit_thinking(response, state)

            # Append assistant message (reasoning + tool calls)
            state.messages.append(build_assistant_message(response.text, response.tool_calls))

            if not response.tool_calls:
                no_tool_call_nudges += 1
                if no_tool_call_nudges >= 3:
                    self.ctx.logger.debug(
                        f"[AgenticSearch] Agent refused to use tools after "
                        f"{no_tool_call_nudges} nudges, forcing finish"
                    )
                    break
                self.ctx.logger.debug(
                    f"[AgenticSearch] No tool calls at iteration {state.iteration}, "
                    f"nudging agent to use tools ({no_tool_call_nudges}/3)"
                )
                state.messages.append(
                    {
                        "role": "user",
                        "content": (
                            "You must use tools to interact. "
                            "Call `search` to find results, `read` to examine them, "
                            "`mark_as_relevant` to mark them, "
                            "or `return_results_to_user` to end. Do not respond with plain text."
                        ),
                    }
                )
                state.iteration += 1
                continue

            # Agent used tools — reset nudge counter
            no_tool_call_nudges = 0

            # Track marks before tool execution for stagnation detection
            marks_before = len(state.marked_entity_ids)

            # Execute all tool calls (emits tool_call events)
            has_finish, new_search_tool_call_ids, new_read_tool_call_ids = (
                await self._execute_tool_calls(response.tool_calls, state)
            )

            # Stagnation detection: track iterations without new marks
            if len(state.marked_entity_ids) > marks_before:
                iterations_since_last_mark = 0
            else:
                iterations_since_last_mark += 1

            # Agent called finish — break after processing all tool calls
            if has_finish:
                self.ctx.logger.debug(
                    f"[AgenticSearch] Agent returned results after {state.iteration} iterations, "
                    f"{len(state.marked_entity_ids)} results marked"
                )
                break

            # 3-tier context management for search and read results
            if new_search_tool_call_ids or new_read_tool_call_ids:
                state.messages = manage_context(
                    messages=state.messages,
                    results_by_tool_call_id=state.results_by_tool_call_id,
                    reads_by_tool_call_id=state.reads_by_tool_call_id,
                    current_search_ids=new_search_tool_call_ids,
                    current_read_ids=new_read_tool_call_ids,
                    previous_search_ids=prev_search_ids,
                    previous_read_ids=prev_read_ids,
                )
                # Rotate: current → previous
                prev_search_ids = new_search_tool_call_ids
                prev_read_ids = new_read_tool_call_ids

            # Warnings when approaching iteration limit
            remaining = max_iter - state.iteration - 1
            if remaining == max_iter // 4:
                state.messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"[System] You have {remaining} iterations remaining out of "
                            f"{max_iter}. Start wrapping up: mark any relevant results you "
                            f"have seen and prepare to call return_results_to_user soon."
                        ),
                    }
                )
            elif remaining == 2:
                state.messages.append(
                    {
                        "role": "user",
                        "content": (
                            "[System] URGENT: You have only 2 iterations left. "
                            "You MUST call mark_as_relevant for any remaining relevant "
                            "results NOW, then call return_results_to_user. "
                            "Do NOT start new searches."
                        ),
                    }
                )
            elif remaining == 1:
                state.messages.append(
                    {
                        "role": "user",
                        "content": (
                            "[System] FINAL ITERATION. Call return_results_to_user now. "
                            "Any unmarked results will be lost."
                        ),
                    }
                )

            # Stagnation nudge
            stagnation_threshold = agentic_config.STAGNATION_THRESHOLD
            if iterations_since_last_mark >= stagnation_threshold:
                stagnation_nudges_sent += 1
                state.messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"[System] You haven't marked any new results in "
                            f"{iterations_since_last_mark} iterations. "
                            "If you've exhausted the search space, call return_results_to_user. "
                            "If not, try a fundamentally different search strategy."
                        ),
                    }
                )

            # Progress tracker
            state.messages.append(self._build_progress_message(state, max_iter))

            state.iteration += 1

        # Only return results the agent explicitly marked as relevant
        results = [state.results[eid] for eid in state.marked_entity_ids if eid in state.results]

        # Rerank using Cohere (if available and multiple results)
        if self.services.reranker and len(results) > 1:
            self.ctx.logger.debug(f"[AgenticSearch] Reranking {len(results)} results with Cohere")
            results = await self._rerank_results(results, request.query)
        elif not self.services.reranker:
            self.ctx.logger.debug("[AgenticSearch] Reranker not configured, skipping")
        else:
            self.ctx.logger.debug(f"[AgenticSearch] Skipping rerank ({len(results)} result(s))")

        # Truncate results to user-requested limit
        if request.limit is not None and len(results) > request.limit:
            results = results[: request.limit]

        self.ctx.logger.debug(f"[AgenticSearch] Done — returning {len(results)} results")
        resp = AgenticSearchResponse(results=results)
        # Deduplicate seen/marked IDs to original entity IDs (strip __chunk_ suffix)
        seen_original_ids = self._to_original_entity_ids(state.results.values())
        marked_original_ids = self._to_original_entity_ids(
            state.results[eid] for eid in state.marked_entity_ids if eid in state.results
        )

        await self.emitter.emit(
            AgenticSearchDoneEvent(
                response=resp,
                all_seen_entity_ids=seen_original_ids,
                all_marked_entity_ids=marked_original_ids,
                max_iterations_hit=hit_max_iterations,
                total_llm_retries=total_llm_retries,
                stagnation_nudges_sent=stagnation_nudges_sent,
            )
        )
        return resp

    # ── Tool execution ───────────────────────────────────────────────

    async def _execute_tool_calls(
        self,
        tool_calls: list[LLMToolCall],
        state: AgenticSearchState,
    ) -> tuple[bool, set[str], set[str]]:
        """Execute tool calls, emit tool_call events, append result messages.

        Returns (should_finish, new_search_tool_call_ids, new_read_tool_call_ids).
        """
        new_search_tool_call_ids: set[str] = set()
        new_read_tool_call_ids: set[str] = set()

        for tc in tool_calls:
            start = time.monotonic()
            try:
                content = await handle_tool_call(
                    tc=tc,
                    state=state,
                    services=self.services,
                    emitter=self.emitter,
                    collection_id=self._collection_id,
                    user_filter=self._user_filter,
                    context_window_tokens=self._context_window_tokens,
                )
                summary = self._build_tool_summary(tc, state)
            except Exception as e:
                content = f"Tool call failed: {e}"
                summary = {"error": str(e)}
            duration_ms = int((time.monotonic() - start) * 1000)

            # Emit tool_call event
            await self.emitter.emit(
                AgenticSearchToolCallEvent(
                    iteration=state.iteration,
                    tool_call_id=tc.id,
                    tool_name=tc.name,
                    arguments=tc.arguments,
                    result_summary=summary,
                    duration_ms=duration_ms,
                )
            )

            msg = build_tool_result_message(tc.id, content)
            msg["_tool_name"] = tc.name
            state.messages.append(msg)

            if tc.name == "search":
                new_search_tool_call_ids.add(tc.id)
            elif tc.name == "read":
                new_read_tool_call_ids.add(tc.id)

        return state.should_finish, new_search_tool_call_ids, new_read_tool_call_ids

    def _build_tool_summary(self, tc: LLMToolCall, state: AgenticSearchState) -> dict:
        """Build a compact summary dict for the tool_call event."""
        if tc.name == "search":
            results = state.results_by_tool_call_id.get(tc.id, [])
            all_ids = set(state.results.keys())
            new_ids = {r.entity_id for r in results}
            return {
                "result_count": len(results),
                "new_results": len(new_ids - (all_ids - new_ids)),
                "total_results_seen": len(all_ids),
            }
        if tc.name == "mark_as_relevant":
            return {
                "total_marked": len(state.marked_entity_ids),
            }
        if tc.name == "unmark":
            return {
                "total_marked": len(state.marked_entity_ids),
            }
        if tc.name == "read":
            entity_ids = tc.arguments.get("entity_ids", [])
            found = sum(1 for eid in entity_ids if eid in state.results)
            return {"found": found, "not_found": len(entity_ids) - found}
        if tc.name in ("review_marked_results", "return_results_to_user"):
            return {"total_marked": len(state.marked_entity_ids)}
        return {}

    @staticmethod
    def _is_retryable(error: Exception) -> bool:
        """Check if an LLM error is retryable at the conversation level."""
        error_str = str(error).lower()
        fatal_indicators = [
            "400",
            "401",
            "402",
            "403",
            "404",
            "bad request",
            "credit limit",
            "authentication",
            "authorization",
            "invalid api key",
            "model not found",
            "invalid parameter",
            "invalid_request_error",
        ]
        return not any(ind in error_str for ind in fatal_indicators)

    def _build_progress_message(self, state: AgenticSearchState, max_iterations: int) -> dict:
        """Build a brief progress status message for the agent."""
        remaining = max_iterations - state.iteration - 1
        return {
            "role": "user",
            "content": (
                f"[Progress] Iteration {state.iteration + 1}/{max_iterations} complete "
                f"({remaining} remaining). "
                f"Results seen: {len(state.results)} | "
                f"Marked: {len(state.marked_entity_ids)}"
            ),
        }

    @staticmethod
    def _to_original_entity_ids(results: Iterable[AgenticSearchResult]) -> list[str]:
        """Deduplicate results to unique original entity IDs."""
        seen: set[str] = set()
        ids: list[str] = []
        for r in results:
            orig = getattr(r, "airweave_system_metadata", None)
            orig_id = orig.original_entity_id if orig else None
            # Fallback: strip __chunk_ suffix
            use_id = orig_id or r.entity_id.split("__chunk_")[0]
            if use_id and use_id not in seen:
                seen.add(use_id)
                ids.append(use_id)
        return ids

    # ── Reranking ─────────────────────────────────────────────────────

    async def _rerank_results(
        self,
        results: list,
        query: str,
    ) -> list:
        """Rerank results using the reranker service.

        Uses textual_representation as the document content for reranking
        (not metadata/breadcrumbs) since that's the semantic content the
        reranker should score against the query.

        Falls back to original order on failure.
        """
        try:
            assert self.services.reranker is not None
            documents = [r.textual_representation for r in results]
            reranked = await self.services.reranker.rerank(
                query=query,
                documents=documents,
                top_n=len(results),
            )
            reordered = []
            for rr in reranked:
                original = results[rr.index]
                reordered.append(
                    original.model_copy(update={"relevance_score": rr.relevance_score})
                )
            return reordered
        except Exception:
            self.ctx.logger.warning(
                "Reranking failed, returning results in original order", exc_info=True
            )
            return results

    # ── Event emission ────────────────────────────────────────────────

    async def _emit_thinking(
        self,
        response: LLMToolResponse,
        state: AgenticSearchState,
    ) -> None:
        """Emit a thinking event with reasoning text and LLM usage stats."""
        parts = []
        if response.thinking:
            parts.append(response.thinking)
        if response.text:
            parts.append(response.text)

        text = "\n\n".join(parts) if parts else ""

        await self.emitter.emit(
            AgenticSearchThinkingEvent(
                iteration=state.iteration,
                text=text,
                prompt_tokens=response.usage.get("prompt_tokens", 0),
                completion_tokens=response.usage.get("completion_tokens", 0),
                cache_creation_input_tokens=response.usage.get("cache_creation_input_tokens", 0),
                cache_read_input_tokens=response.usage.get("cache_read_input_tokens", 0),
                tool_calls_count=len(response.tool_calls),
                stop_reason=response.stop_reason,
                total_results_seen=len(state.results),
                total_results_marked=len(state.marked_entity_ids),
            )
        )
