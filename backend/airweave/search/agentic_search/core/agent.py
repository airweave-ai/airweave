"""Agentic search agent.

Conversation + tool-calling architecture:
  1. Build system prompt with collection metadata
  2. Send initial user message with the search query
  3. Loop: LLM reasons in free text, calls search or submit_answer tools
  4. Context is managed via pruning old tool results (Layer 2)
  5. Return results from the final search iteration (not all accumulated results)
  6. If the model didn't find an answer, execute an optional consolidation search

The conversation IS the history — no separate state/history objects needed.
"""

import time
from dataclasses import dataclass, field

from airweave.analytics.agentic_search_analytics import (
    track_agentic_search_completion,
    track_agentic_search_error,
)
from airweave.api.context import ApiContext
from airweave.core.protocols.metrics import AgenticSearchMetrics
from airweave.search.agentic_search.builders import (
    AgenticSearchCollectionMetadataBuilder,
)
from airweave.search.agentic_search.config import CHARS_PER_TOKEN
from airweave.search.agentic_search.core.context_manager import (
    estimate_message_chars,
    prune_context,
)
from airweave.search.agentic_search.core.messages import (
    build_assistant_message,
    build_initial_user_message,
    build_tool_result_message,
    load_system_prompt,
)
from airweave.search.agentic_search.core.tools import (
    SEARCH_TOOL,
    SUBMIT_ANSWER_TOOL,
    execute_search_tool,
    parse_submit_answer,
)
from airweave.search.agentic_search.emitter import AgenticSearchEmitter
from airweave.search.agentic_search.external.llm.tool_response import (
    LLMToolCall,
    LLMToolResponse,
)
from airweave.search.agentic_search.schemas import (
    AgenticSearchAnswer,
    AgenticSearchRequest,
    AgenticSearchResponse,
    AgenticSearchResult,
)
from airweave.search.agentic_search.schemas.events import (
    AgenticSearchDoneEvent,
    AgenticSearchErrorEvent,
    AgenticSearchingEvent,
    AgenticSearchThinkingEvent,
)
from airweave.search.agentic_search.schemas.plan import AgenticSearchPlan
from airweave.search.agentic_search.schemas.request import AgenticSearchMode
from airweave.search.agentic_search.services import AgenticSearchServices

# Maps timing-label suffixes to canonical step names used in metrics.
_STEP_LABEL_MAP: dict[str, str] = {
    "plan": "plan",
    "embed": "embed",
    "compile": "search",
    "execute": "search",
    "search_error": "search",
    "evaluate": "evaluate",
    "compose": "compose",
}


@dataclass
class _LoopState:
    """Mutable state for the conversation loop."""

    messages: list[dict] = field(default_factory=list)
    last_search_results: list[AgenticSearchResult] = field(default_factory=list)
    answer: AgenticSearchAnswer | None = None
    consolidation_plan: AgenticSearchPlan | None = None
    search_count: int = 0
    iteration: int = 0
    timings: list[tuple[str, int]] = field(default_factory=list)
    _current_iteration_seen: set[str] = field(default_factory=set)
    _iteration_had_search: bool = False

    def start_new_iteration(self) -> None:
        """Reset per-iteration tracking. Called at the start of each LLM turn.

        Does NOT clear last_search_results — those are preserved until a new
        search actually happens. This ensures that if the final iteration only
        calls submit_answer (no search), we still have the previous results.
        """
        self._current_iteration_seen = set()
        self._iteration_had_search = False

    def merge_search_results(self, results: list[AgenticSearchResult]) -> None:
        """Merge results from a search call into this iteration's results.

        On the first search of a new iteration, replaces previous results.
        Multiple search calls within the same turn are merged together.
        Deduplication is within the iteration only (by entity_id).
        """
        if not self._iteration_had_search:
            self.last_search_results = []
            self._iteration_had_search = True
        for r in results:
            if r.entity_id not in self._current_iteration_seen:
                self.last_search_results.append(r)
                self._current_iteration_seen.add(r.entity_id)


class AgenticSearchAgent:
    """Agentic search agent using conversation + tool calling."""

    # Safety cap — prompt instructs the model to stop well before this
    MAX_ITERATIONS = 20

    def __init__(
        self,
        services: AgenticSearchServices,
        ctx: ApiContext,
        emitter: AgenticSearchEmitter,
        *,
        metrics: AgenticSearchMetrics | None = None,
    ):
        """Initialize the agent."""
        self.services: AgenticSearchServices = services
        self.ctx: ApiContext = ctx
        self.emitter: AgenticSearchEmitter = emitter
        self._metrics = metrics

        # Per-run state set in _run(), used by helper methods
        self._collection_id: str = ""
        self._context_window_tokens: int = 0
        self._user_filter: list = []
        self._t: float = 0.0  # timing checkpoint

    async def run(
        self,
        collection_readable_id: str,
        request: AgenticSearchRequest,
        is_streaming: bool = False,
    ) -> AgenticSearchResponse:
        """Run the agent."""
        start_time = time.monotonic()
        try:
            response = await self._run(collection_readable_id, request, is_streaming)
            return response
        except Exception as e:
            if self._metrics is not None:
                try:
                    self._metrics.inc_search_errors(request.mode.value, is_streaming)
                except Exception:
                    self.ctx.logger.debug(
                        "[AgenticSearchAgent] Failed to record error metric",
                        exc_info=True,
                    )
            duration_ms = int((time.monotonic() - start_time) * 1000)
            await self.emitter.emit(AgenticSearchErrorEvent(message=str(e)))
            try:
                track_agentic_search_error(
                    ctx=self.ctx,
                    query=request.query,
                    collection_slug=collection_readable_id,
                    duration_ms=duration_ms,
                    mode=request.mode.value,
                    error_message=str(e),
                    error_type=type(e).__name__,
                    is_streaming=is_streaming,
                )
            except Exception:
                self.ctx.logger.debug(
                    "[AgenticSearchAgent] Failed to track error analytics",
                    exc_info=True,
                )
            raise
        finally:
            if self._metrics is not None:
                try:
                    self._metrics.inc_search_requests(
                        request.mode.value,
                        is_streaming,
                    )
                    self._metrics.observe_duration(
                        request.mode.value,
                        time.monotonic() - start_time,
                    )
                except Exception:
                    self.ctx.logger.debug(
                        "[AgenticSearchAgent] Failed to record metric",
                        exc_info=True,
                    )

    async def _run(
        self,
        collection_readable_id: str,
        request: AgenticSearchRequest,
        is_streaming: bool = False,
    ) -> AgenticSearchResponse:
        """Internal run method with the conversation loop."""
        total_start = time.monotonic()
        self._t = total_start
        state = _LoopState()

        # Build collection metadata
        metadata_builder = AgenticSearchCollectionMetadataBuilder(self.services.db)
        collection_metadata = await metadata_builder.build(collection_readable_id)
        self._lap(state, "build_collection_metadata")

        # Store loop-invariant config for helper methods
        self._collection_id = collection_metadata.collection_id
        self._context_window_tokens = self.services.llm.model_spec.context_window
        self._user_filter = request.filter

        # Build system prompt and initial message
        system_prompt = load_system_prompt(collection_metadata)
        state.messages = [
            build_initial_user_message(
                user_query=request.query,
                user_filter=request.filter,
                mode=request.mode,
            )
        ]
        tools = [SEARCH_TOOL, SUBMIT_ANSWER_TOOL]
        is_fast = request.mode == AgenticSearchMode.FAST

        while state.iteration < self.MAX_ITERATIONS:
            state.start_new_iteration()

            # Layer 2: Prune old tool results
            state.messages = prune_context(
                state.messages,
                self._context_window_tokens,
                logger=self.ctx.logger,
            )

            # Log full conversation payload before sending
            self._log_llm_input(state, system_prompt)

            # Call LLM with tools
            response = await self.services.llm.create_with_tools(
                messages=state.messages,
                tools=tools,
                system_prompt=system_prompt,
            )
            self._lap(state, f"iter_{state.iteration}/llm")

            # Log LLM response
            self._log_llm_output(state, response)

            # Emit thinking event (extended thinking + regular text)
            await self._emit_thinking(response, state)

            # Append assistant message to conversation
            state.messages.append(build_assistant_message(response.text, response.tool_calls))

            if not response.tool_calls:
                self.ctx.logger.warning("[AgenticSearchAgent] Model stopped without calling a tool")
                break

            # Process tool calls
            if await self._process_tool_calls(response.tool_calls, state):
                break

            # FAST mode: after the first search, remove the search tool so the
            # model can only call submit_answer. The model already knows it has
            # one shot (via the prompt) and crafts a broad query accordingly.
            if is_fast and state.search_count > 0:
                tools = [SUBMIT_ANSWER_TOOL]

            state.iteration += 1

        # Fallback if model never called submit_answer
        if state.answer is None:
            self.ctx.logger.warning("[AgenticSearchAgent] No submit_answer, using fallback")
            state.answer = AgenticSearchAnswer(
                text="The search could not produce a definitive answer. "
                "Please try refining your query.",
                citations=[],
            )

        # Execute consolidation search if the model provided one,
        # otherwise use the last iteration's search results
        if state.consolidation_plan is not None:
            results = await self._execute_consolidation_search(state)
            self._lap(state, "consolidation_search")
        else:
            results = state.last_search_results

        # Truncate results to user-requested limit
        if request.limit is not None and len(results) > request.limit:
            results = results[: request.limit]

        resp = AgenticSearchResponse(
            results=results,
            answer=state.answer,
            answer_found=state.consolidation_plan is None,
        )
        await self.emitter.emit(AgenticSearchDoneEvent(response=resp))

        total_ms = self._log_timings(state, total_start)
        self._track_analytics(
            request,
            collection_readable_id,
            results,
            state.answer,
            state.timings,
            total_ms,
            is_streaming,
            state.iteration + 1,
            state.search_count,
            had_consolidation=state.consolidation_plan is not None,
        )
        return resp

    async def _emit_thinking(
        self,
        response: LLMToolResponse,
        state: _LoopState,
    ) -> None:
        """Emit a thinking event combining extended thinking and regular text."""
        parts = []
        if response.thinking:
            parts.append(response.thinking)
        if response.text:
            parts.append(response.text)
        if parts:
            await self.emitter.emit(
                AgenticSearchThinkingEvent(
                    iteration=state.iteration,
                    text="\n\n".join(parts),
                )
            )

    async def _process_tool_calls(
        self,
        tool_calls: list[LLMToolCall],
        state: _LoopState,
    ) -> bool:
        """Process tool calls from the LLM response. Returns True if done."""
        for tc in tool_calls:
            if tc.name == "search":
                await self._handle_search(tc, state)
            elif tc.name == "submit_answer":
                answer, consolidation_plan = parse_submit_answer(tc.arguments)
                state.answer = answer
                state.consolidation_plan = consolidation_plan
                self._lap(state, f"iter_{state.iteration}/submit_answer")
                return True
        return False

    async def _handle_search(
        self,
        tc: LLMToolCall,
        state: _LoopState,
    ) -> None:
        """Execute a search tool call and update state."""
        state.search_count += 1
        try:
            formatted_text, results, duration_ms = await execute_search_tool(
                arguments=tc.arguments,
                user_filter=self._user_filter,
                dense_embedder=self.services.dense_embedder,
                sparse_embedder=self.services.sparse_embedder,
                vector_db=self.services.vector_db,
                collection_id=self._collection_id,
                context_window_tokens=self._context_window_tokens,
            )
            state.merge_search_results(results)
            state.messages.append(build_tool_result_message(tc.id, formatted_text))
            self._lap(state, f"iter_{state.iteration}/search")
            await self.emitter.emit(
                AgenticSearchingEvent(
                    iteration=state.iteration,
                    result_count=len(results),
                    duration_ms=duration_ms,
                )
            )
        except Exception as e:
            error_msg = f"Search failed: {e}"
            self.ctx.logger.warning(f"[AgenticSearchAgent] {error_msg}")
            state.messages.append(build_tool_result_message(tc.id, error_msg))
            self._lap(state, f"iter_{state.iteration}/search_error")

    async def _execute_consolidation_search(
        self,
        state: _LoopState,
    ) -> list[AgenticSearchResult]:
        """Execute the consolidation search plan provided by the model.

        Runs a single search (embed -> compile -> execute) using the consolidation
        plan from submit_answer. On failure, falls back to last_search_results.
        """
        plan = state.consolidation_plan
        self.ctx.logger.debug(
            f"[AgenticSearchAgent] Running consolidation search: "
            f"query='{plan.query.primary}', "
            f"strategy={plan.retrieval_strategy.value}, "
            f"limit={plan.limit}"
        )
        try:
            _formatted_text, results, duration_ms = await execute_search_tool(
                arguments=plan.model_dump(),
                user_filter=self._user_filter,
                dense_embedder=self.services.dense_embedder,
                sparse_embedder=self.services.sparse_embedder,
                vector_db=self.services.vector_db,
                collection_id=self._collection_id,
                context_window_tokens=self._context_window_tokens,
            )
            self.ctx.logger.debug(
                f"[AgenticSearchAgent] Consolidation search returned "
                f"{len(results)} results in {duration_ms}ms"
            )
            return results
        except Exception as e:
            self.ctx.logger.warning(
                f"[AgenticSearchAgent] Consolidation search failed: {e}. "
                f"Falling back to last_search_results."
            )
            return state.last_search_results

    def _lap(self, state: _LoopState, label: str) -> None:
        """Record a timing lap."""
        now = time.monotonic()
        state.timings.append((label, int((now - self._t) * 1000)))
        self._t = now

    def _log_llm_input(
        self,
        state: _LoopState,
        system_prompt: str,
    ) -> None:
        """Log LLM input stats for this iteration."""
        log = self.ctx.logger
        n_msgs = len(state.messages)
        sys_chars = len(system_prompt)
        msg_chars = sum(estimate_message_chars(m) for m in state.messages)
        total_chars = sys_chars + msg_chars
        est_tokens = total_chars // CHARS_PER_TOKEN

        summary_lines = [
            f"Iteration {state.iteration}  |  "
            f"{n_msgs} messages  |  "
            f"~{est_tokens:,} tokens "
            f"({total_chars:,} chars)",
            f"  system_prompt: {sys_chars:,} chars",
        ]
        for i, msg in enumerate(state.messages):
            role = msg.get("role", "?")
            chars = estimate_message_chars(msg)
            tool_calls = msg.get("tool_calls")
            tool_id = msg.get("tool_call_id", "")

            detail = ""
            if role == "tool":
                detail = f"  tool_call_id={tool_id}"
            elif tool_calls:
                names = ", ".join(tc["function"]["name"] for tc in tool_calls)
                detail = f"  tools=[{names}]"

            summary_lines.append(f"  [{i}] {role:<10} {chars:>8,} chars{detail}")

        log.debug("[AgenticSearchAgent] LLM input summary:\n" + "\n".join(summary_lines))

    def _log_llm_output(
        self,
        state: _LoopState,
        response: LLMToolResponse,
    ) -> None:
        """Log LLM output stats and full tool call arguments (search plans)."""
        log = self.ctx.logger
        text_len = len(response.text) if response.text else 0
        n_tools = len(response.tool_calls) if response.tool_calls else 0
        usage = response.usage

        # Summary line
        summary_parts = [
            f"Iteration {state.iteration}  |  "
            f"stop={response.stop_reason}  |  "
            f"text={text_len:,} chars  |  "
            f"{n_tools} tool call(s)",
        ]

        if usage:
            prompt_t = usage.get("input_tokens") or usage.get("prompt_tokens", "?")
            comp_t = usage.get("output_tokens") or usage.get("completion_tokens", "?")
            summary_parts.append(f"  usage: {prompt_t} prompt / {comp_t} completion")

        log.debug("[AgenticSearchAgent] LLM output summary:\n" + "\n".join(summary_parts))

        # Full tool calls with complete arguments (search plans, submit_answer)
        if response.tool_calls:
            for tc in response.tool_calls:
                log.debug(
                    f"\n\n[AgenticSearchAgent] LLM output tool_call: "
                    f"id={tc.id} name={tc.name}\n"
                    f"arguments={tc.arguments}\n\n"
                )

    def _log_timings(self, state: _LoopState, total_start: float) -> int:
        """Log all step timings in a single summary."""
        total_ms = int((time.monotonic() - total_start) * 1000)
        lines = [f"{'Step':<30} {'Duration':>8}"]
        lines.append("\u2500" * 40)
        for label, ms in state.timings:
            lines.append(f"{label:<30} {ms:>6}ms")
        lines.append("\u2500" * 40)
        lines.append(f"{'Total':<30} {total_ms:>6}ms")
        self.ctx.logger.debug("[AgenticSearchAgent] Timings:\n" + "\n".join(lines))
        return total_ms

    def _record_metrics(
        self,
        timings: list[tuple[str, int]],
        mode: str,
        iteration_count: int,
        result_count: int,
    ) -> None:
        """Record Prometheus metrics from pipeline timings.

        Non-blocking: errors are logged but never affect the response.
        """
        if self._metrics is None:
            return
        try:
            self._metrics.observe_iterations(mode, iteration_count)
            self._metrics.observe_results_per_search(result_count)
            for label, ms in timings:
                # Extract the step suffix: "iter_0/plan" -> "plan",
                # "compose" -> "compose"
                suffix = label.rsplit("/", 1)[-1]
                step = _STEP_LABEL_MAP.get(suffix)
                if step is not None:
                    self._metrics.observe_step_duration(step, ms / 1000.0)
        except Exception:
            self.ctx.logger.debug(
                "[AgenticSearchAgent] Failed to record Prometheus metrics",
                exc_info=True,
            )

    def _track_analytics(
        self,
        request: AgenticSearchRequest,
        collection_readable_id: str,
        results: list[AgenticSearchResult],
        answer: AgenticSearchAnswer,
        timings: list[tuple[str, int]],
        total_ms: int,
        is_streaming: bool,
        total_iterations: int,
        search_count: int,
        had_consolidation: bool = False,
    ) -> None:
        """Track analytics. Errors are logged and swallowed."""
        try:
            if request.mode == AgenticSearchMode.FAST:
                exit_reason = "fast_mode"
            elif search_count == 0:
                exit_reason = "no_search"
            else:
                exit_reason = "answer_submitted"

            llm = self.services.llm
            track_agentic_search_completion(
                ctx=self.ctx,
                query=request.query,
                collection_slug=collection_readable_id,
                duration_ms=total_ms,
                mode=request.mode.value,
                total_iterations=total_iterations,
                had_consolidation=had_consolidation,
                exit_reason=exit_reason,
                results_count=len(results),
                answer_length=len(answer.text),
                citations_count=len(answer.citations),
                timings=timings,
                is_streaming=is_streaming,
                has_user_filter=len(request.filter) > 0,
                user_filter_groups_count=len(request.filter),
                user_limit=request.limit,
                total_prompt_tokens=getattr(llm, "total_prompt_tokens", None),
                total_completion_tokens=getattr(llm, "total_completion_tokens", None),
                fallback_stats=getattr(llm, "fallback_stats", None),
            )
        except Exception:
            self.ctx.logger.debug(
                "[AgenticSearchAgent] Failed to track analytics",
                exc_info=True,
            )
