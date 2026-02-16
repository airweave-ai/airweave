"""Agentic search agent.

Flow:
  collection_readable_id -> build collection metadata
  user request + collection_metadata -> initialize state
  state -> planner -> plan (LLM filters only)
  plan + user_filter -> complete_plan (combined filters for execution)
  complete_plan -> compile_query -> execute_query -> search_results
  state context -> evaluator -> evaluation (loop or stop)
  final state -> composer -> answer
"""

import time

from airweave.analytics.agentic_search_analytics import (
    build_iteration_summaries,
    track_agentic_search_completion,
    track_agentic_search_error,
)
from airweave.api.context import ApiContext
from airweave.search.agentic_search.builders import (
    AgenticSearchCollectionMetadataBuilder,
    AgenticSearchCompletePlanBuilder,
    AgenticSearchResultBriefBuilder,
    AgenticSearchStateBuilder,
)
from airweave.search.agentic_search.core.composer import AgenticSearchComposer
from airweave.search.agentic_search.core.embedder import AgenticSearchEmbedder
from airweave.search.agentic_search.core.evaluator import AgenticSearchEvaluator
from airweave.search.agentic_search.core.planner import AgenticSearchPlanner
from airweave.search.agentic_search.emitter import AgenticSearchEmitter
from airweave.search.agentic_search.schemas import (
    AgenticSearchAnswer,
    AgenticSearchCollectionMetadata,
    AgenticSearchCompiledQuery,
    AgenticSearchCurrentIteration,
    AgenticSearchEvaluation,
    AgenticSearchHistory,
    AgenticSearchHistoryIteration,
    AgenticSearchPlan,
    AgenticSearchQueryEmbeddings,
    AgenticSearchRequest,
    AgenticSearchResponse,
    AgenticSearchResult,
    AgenticSearchState,
)
from airweave.search.agentic_search.schemas.events import (
    AgenticSearchDoneEvent,
    AgenticSearchErrorEvent,
    AgenticSearchEvaluatingEvent,
    AgenticSearchingEvent,
    AgenticSearchPlanningEvent,
)
from airweave.search.agentic_search.schemas.request import AgenticSearchMode
from airweave.search.agentic_search.schemas.search_result import AgenticSearchResults
from airweave.search.agentic_search.services import AgenticSearchServices


class AgenticSearchAgent:
    """Agentic search agent."""

    def __init__(
        self, services: AgenticSearchServices, ctx: ApiContext, emitter: AgenticSearchEmitter
    ):
        """Initialize the agent."""
        self.services: AgenticSearchServices = services
        self.ctx: ApiContext = ctx
        self.emitter: AgenticSearchEmitter = emitter

    async def run(
        self,
        collection_readable_id: str,
        request: AgenticSearchRequest,
        is_streaming: bool = False,
    ) -> AgenticSearchResponse:
        """Run the agent."""
        start_time = time.monotonic()
        try:
            return await self._run(collection_readable_id, request, is_streaming)
        except Exception as e:
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
                    "[AgenticSearchAgent] Failed to track error analytics", exc_info=True
                )
            raise

    async def _run(
        self,
        collection_readable_id: str,
        request: AgenticSearchRequest,
        is_streaming: bool = False,
    ) -> AgenticSearchResponse:
        """Internal run method with event emission."""
        timings: list[tuple[str, int]] = []
        total_start = time.monotonic()
        t = total_start

        # Build collection metadata
        collection_metadata_builder = AgenticSearchCollectionMetadataBuilder(self.services.db)
        collection_metadata: AgenticSearchCollectionMetadata = (
            await collection_metadata_builder.build(collection_readable_id)
        )
        t = self._lap(timings, "build_collection_metadata", t)

        # Build initial state
        state_builder = AgenticSearchStateBuilder()
        state: AgenticSearchState = state_builder.build_initial(
            request=request,
            collection_metadata=collection_metadata,
        )
        t = self._lap(timings, "build_initial_state", t)

        # Collect per-iteration context window stats for analytics
        context_stats: list[dict[str, int]] = []

        while True:
            prefix = f"iter_{state.iteration_number}"
            iter_stats: dict[str, int] = {}

            # Create search plan
            planner = AgenticSearchPlanner(
                llm=self.services.llm,
                tokenizer=self.services.tokenizer,
                logger=self.ctx.logger,
            )
            plan: AgenticSearchPlan = await planner.plan(state)
            state.current_iteration.plan = plan
            t = self._lap(timings, f"{prefix}/plan", t)

            # Capture planner context window stats
            iter_stats["planner_history_shown"] = planner.history_shown
            iter_stats["planner_history_total"] = planner.history_total

            # Emit planning event (includes how much history fit in the prompt)
            await self.emitter.emit(
                AgenticSearchPlanningEvent(
                    iteration=state.iteration_number,
                    plan=plan,
                    is_consolidation=state.is_consolidation,
                    history_shown=planner.history_shown,
                    history_total=planner.history_total,
                )
            )

            # Build complete plan (LLM filters + user filters) for execution
            complete_plan = AgenticSearchCompletePlanBuilder.build(plan, state.user_filter)

            # Embed queries based on retrieval strategy
            embedder = AgenticSearchEmbedder(
                dense_embedder=self.services.dense_embedder,
                sparse_embedder=self.services.sparse_embedder,
            )
            embeddings: AgenticSearchQueryEmbeddings = await embedder.embed(
                query=state.current_iteration.plan.query,
                strategy=state.current_iteration.plan.retrieval_strategy,
            )
            state.current_iteration.query_embeddings = embeddings
            t = self._lap(timings, f"{prefix}/embed", t)

            # Compile and execute query (gracefully handle search errors)
            search_error: str | None = None
            try:
                compiled_query: AgenticSearchCompiledQuery = (
                    await self.services.vector_db.compile_query(
                        plan=complete_plan,
                        embeddings=state.current_iteration.query_embeddings,
                        collection_id=state.collection_metadata.collection_id,
                    )
                )
                state.current_iteration.compiled_query = compiled_query
                t = self._lap(timings, f"{prefix}/compile", t)

                search_results: AgenticSearchResults = await self.services.vector_db.execute_query(
                    compiled_query
                )
                state.current_iteration.search_results = search_results
                t = self._lap(timings, f"{prefix}/execute", t)
            except Exception as e:
                search_error = str(e)
                self.ctx.logger.warning(
                    f"[AgenticSearchAgent] Search failed at iteration "
                    f"{state.iteration_number}: {search_error}"
                )
                # Treat as empty results and record the error so the evaluator knows
                state.current_iteration.search_results = AgenticSearchResults(results=[])
                state.current_iteration.search_error = search_error
                t = self._lap(timings, f"{prefix}/search_error", t)

            # Emit searching event
            search_ms = timings[-1][1]
            await self.emitter.emit(
                AgenticSearchingEvent(
                    iteration=state.iteration_number,
                    result_count=len(state.current_iteration.search_results),
                    duration_ms=search_ms,
                )
            )

            if state.mode == AgenticSearchMode.FAST:
                context_stats.append(iter_stats)
                break

            # Consolidation pass: after search, skip evaluation and break
            if state.is_consolidation:
                context_stats.append(iter_stats)
                break

            # Build result brief deterministically (no LLM)
            result_brief = AgenticSearchResultBriefBuilder.build(
                state.current_iteration.search_results
            )

            # Evaluate results
            evaluator = AgenticSearchEvaluator(
                llm=self.services.llm,
                tokenizer=self.services.tokenizer,
                logger=self.ctx.logger,
            )
            evaluation: AgenticSearchEvaluation = await evaluator.evaluate(state)
            state.current_iteration.evaluation = evaluation
            self.ctx.logger.debug(f"[AgenticSearchAgent] Evaluation: {evaluation.to_md()}")
            t = self._lap(timings, f"{prefix}/evaluate", t)

            # Capture evaluator context window stats
            iter_stats["evaluator_results_shown"] = evaluator.results_shown
            iter_stats["evaluator_results_total"] = evaluator.results_total
            iter_stats["evaluator_history_shown"] = evaluator.history_shown
            iter_stats["evaluator_history_total"] = evaluator.history_total

            context_stats.append(iter_stats)

            # Emit evaluating event (includes how many results/history fit in the prompt)
            await self.emitter.emit(
                AgenticSearchEvaluatingEvent(
                    iteration=state.iteration_number,
                    evaluation=evaluation,
                    results_shown=evaluator.results_shown,
                    results_total=evaluator.results_total,
                    history_shown=evaluator.history_shown,
                    history_total=evaluator.history_total,
                )
            )

            # Answer found — break cleanly
            if not evaluation.should_continue and evaluation.answer_found:
                break

            # Answer NOT found but search exhausted — trigger consolidation.
            # Don't break: fall through to add this iteration to history, set
            # consolidation mode, and let the loop do one more plan+search cycle.
            if not evaluation.should_continue and not evaluation.answer_found:
                self.ctx.logger.debug(
                    "[AgenticSearchAgent] Consolidation pass: answer not found, "
                    "running one more targeted search."
                )
                state.is_consolidation = True

            # Create history iteration from completed current iteration
            history_iteration = AgenticSearchHistoryIteration(
                plan=state.current_iteration.plan,
                result_brief=result_brief,
                evaluation=state.current_iteration.evaluation,
                evaluator_results_shown=evaluator.results_shown,
                search_error=state.current_iteration.search_error,
            )

            # Initialize or add to history
            if state.history is None:
                state.history = AgenticSearchHistory(
                    iterations={state.iteration_number: history_iteration}
                )
            else:
                state.history.add_iteration(state.iteration_number, history_iteration)

            # Prepare for next iteration
            state.iteration_number += 1
            state.current_iteration = AgenticSearchCurrentIteration()

        # Compose final answer
        composer = AgenticSearchComposer(
            llm=self.services.llm,
            tokenizer=self.services.tokenizer,
            logger=self.ctx.logger,
        )
        answer: AgenticSearchAnswer = await composer.compose(state)
        self._lap(timings, "compose", t)

        # Truncate results to user-requested limit (if set)
        results: list[AgenticSearchResult] = state.current_iteration.search_results.results
        if request.limit is not None and len(results) > request.limit:
            self.ctx.logger.debug(
                f"[AgenticSearchAgent] Truncating results from {len(results)} "
                f"to user limit of {request.limit}"
            )
            results = results[: request.limit]

        response = AgenticSearchResponse(
            results=results,
            answer=answer,
        )

        # Emit done event
        await self.emitter.emit(AgenticSearchDoneEvent(response=response))

        # Log final timing summary
        total_ms = self._log_timings(timings, total_start)

        # Track analytics (non-blocking, errors logged and swallowed)
        self._track_analytics(
            state,
            request,
            collection_readable_id,
            results,
            answer,
            timings,
            total_ms,
            is_streaming,
            context_stats,
        )

        return response

    def _lap(self, timings: list, label: str, start: float) -> float:
        """Record a timing and return the new start time."""
        now = time.monotonic()
        timings.append((label, int((now - start) * 1000)))
        return now

    def _log_timings(self, timings: list, total_start: float) -> int:
        """Log all step timings in a single summary.

        Returns:
            Total elapsed time in milliseconds.
        """
        total_ms = int((time.monotonic() - total_start) * 1000)
        lines = [f"{'Step':<30} {'Duration':>8}"]
        lines.append("─" * 40)
        for label, ms in timings:
            lines.append(f"{label:<30} {ms:>6}ms")
        lines.append("─" * 40)
        lines.append(f"{'Total':<30} {total_ms:>6}ms")
        self.ctx.logger.debug("[AgenticSearchAgent] Timings:\n" + "\n".join(lines))
        return total_ms

    def _track_analytics(
        self,
        state: AgenticSearchState,
        request: AgenticSearchRequest,
        collection_readable_id: str,
        results: list[AgenticSearchResult],
        answer: AgenticSearchAnswer,
        timings: list[tuple[str, int]],
        total_ms: int,
        is_streaming: bool,
        context_stats: list[dict[str, int]],
    ) -> None:
        """Track agentic search completion analytics via PostHog.

        Non-blocking: errors are logged but never affect the response.
        """
        try:
            # Determine exit reason
            if state.mode == AgenticSearchMode.FAST:
                exit_reason = "fast_mode"
            elif state.is_consolidation:
                exit_reason = "consolidation"
            else:
                exit_reason = "answer_found"

            # Build per-iteration summaries (includes context window stats)
            iteration_summaries, search_error_count = build_iteration_summaries(
                history=state.history,
                current_iteration=state.current_iteration,
                current_iteration_number=state.iteration_number,
                is_fast_mode=(state.mode == AgenticSearchMode.FAST),
                context_stats=context_stats,
            )

            # Read cumulative token usage and fallback stats from the LLM (if available)
            llm = self.services.llm
            total_prompt_tokens = getattr(llm, "total_prompt_tokens", None)
            total_completion_tokens = getattr(llm, "total_completion_tokens", None)
            fallback_stats = getattr(llm, "fallback_stats", None)

            track_agentic_search_completion(
                ctx=self.ctx,
                query=state.user_query,
                collection_slug=collection_readable_id,
                duration_ms=total_ms,
                mode=state.mode.value,
                total_iterations=state.iteration_number + 1,
                had_consolidation=state.is_consolidation,
                exit_reason=exit_reason,
                results_count=len(results),
                answer_length=len(answer.text),
                citations_count=len(answer.citations),
                timings=timings,
                is_streaming=is_streaming,
                has_user_filter=len(request.filter) > 0,
                user_filter_groups_count=len(request.filter),
                user_limit=request.limit,
                iteration_summaries=iteration_summaries,
                search_error_count=search_error_count,
                total_prompt_tokens=total_prompt_tokens,
                total_completion_tokens=total_completion_tokens,
                fallback_stats=fallback_stats,
            )
        except Exception:
            self.ctx.logger.debug(
                "[AgenticSearchAgent] Failed to track completion analytics", exc_info=True
            )
