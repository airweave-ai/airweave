"""Spotlight search agent.

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

from airweave.api.context import ApiContext
from airweave.search.spotlight.builders import (
    SpotlightCollectionMetadataBuilder,
    SpotlightCompletePlanBuilder,
    SpotlightStateBuilder,
)
from airweave.search.spotlight.core.composer import SpotlightComposer
from airweave.search.spotlight.core.embedder import SpotlightEmbedder
from airweave.search.spotlight.core.evaluator import SpotlightEvaluator
from airweave.search.spotlight.core.planner import SpotlightPlanner
from airweave.search.spotlight.emitter import SpotlightEmitter
from airweave.search.spotlight.schemas import (
    SpotlightAnswer,
    SpotlightCollectionMetadata,
    SpotlightCompiledQuery,
    SpotlightCurrentIteration,
    SpotlightEvaluation,
    SpotlightHistory,
    SpotlightHistoryIteration,
    SpotlightPlan,
    SpotlightQueryEmbeddings,
    SpotlightRequest,
    SpotlightResponse,
    SpotlightState,
)
from airweave.search.spotlight.schemas.events import (
    SpotlightDoneEvent,
    SpotlightErrorEvent,
    SpotlightEvaluatingEvent,
    SpotlightPlanningEvent,
    SpotlightSearchingEvent,
)
from airweave.search.spotlight.schemas.request import SpotlightSearchMode
from airweave.search.spotlight.schemas.search_result import SpotlightSearchResults
from airweave.search.spotlight.services import SpotlightServices


class SpotlightAgent:
    """Spotlight search agent."""

    def __init__(self, services: SpotlightServices, ctx: ApiContext, emitter: SpotlightEmitter):
        """Initialize the agent."""
        self.services: SpotlightServices = services
        self.ctx: ApiContext = ctx
        self.emitter: SpotlightEmitter = emitter

    async def run(
        self, collection_readable_id: str, request: SpotlightRequest
    ) -> SpotlightResponse:
        """Run the agent."""
        try:
            return await self._run(collection_readable_id, request)
        except Exception as e:
            await self.emitter.emit(SpotlightErrorEvent(message=str(e)))
            raise

    async def _run(
        self, collection_readable_id: str, request: SpotlightRequest
    ) -> SpotlightResponse:
        """Internal run method with event emission."""
        timings: list[tuple[str, int]] = []
        total_start = time.monotonic()
        t = total_start

        # Build collection metadata
        collection_metadata_builder = SpotlightCollectionMetadataBuilder(self.services.db)
        collection_metadata: SpotlightCollectionMetadata = await collection_metadata_builder.build(
            collection_readable_id
        )
        t = self._lap(timings, "build_collection_metadata", t)

        # Build initial state
        state_builder = SpotlightStateBuilder()
        state: SpotlightState = state_builder.build_initial(
            request=request,
            collection_metadata=collection_metadata,
        )
        t = self._lap(timings, "build_initial_state", t)

        while True:
            prefix = f"iter_{state.iteration_number}"

            # Create search plan
            planner = SpotlightPlanner(
                llm=self.services.llm,
                tokenizer=self.services.tokenizer,
                logger=self.ctx.logger,
            )
            plan: SpotlightPlan = await planner.plan(state)
            state.current_iteration.plan = plan
            t = self._lap(timings, f"{prefix}/plan", t)

            # Emit planning event
            await self.emitter.emit(
                SpotlightPlanningEvent(
                    iteration=state.iteration_number,
                    plan=plan,
                )
            )

            # Build complete plan (LLM filters + user filters) for execution
            complete_plan = SpotlightCompletePlanBuilder.build(plan, state.user_filter)

            # Embed queries based on retrieval strategy
            embedder = SpotlightEmbedder(
                dense_embedder=self.services.dense_embedder,
                sparse_embedder=self.services.sparse_embedder,
            )
            embeddings: SpotlightQueryEmbeddings = await embedder.embed(
                query=state.current_iteration.plan.query,
                strategy=state.current_iteration.plan.retrieval_strategy,
            )
            state.current_iteration.query_embeddings = embeddings
            t = self._lap(timings, f"{prefix}/embed", t)

            # Compile query
            compiled_query: SpotlightCompiledQuery = await self.services.vector_db.compile_query(
                plan=complete_plan,
                embeddings=state.current_iteration.query_embeddings,
                collection_id=state.collection_metadata.collection_id,
            )
            state.current_iteration.compiled_query = compiled_query
            t = self._lap(timings, f"{prefix}/compile", t)

            # Execute query
            search_results: SpotlightSearchResults = await self.services.vector_db.execute_query(
                compiled_query
            )
            state.current_iteration.search_results = search_results
            t = self._lap(timings, f"{prefix}/execute", t)

            # Emit searching event (compile + execute combined for user-facing latency)
            compile_ms = timings[-2][1]
            execute_ms = timings[-1][1]
            await self.emitter.emit(
                SpotlightSearchingEvent(
                    iteration=state.iteration_number,
                    result_count=len(search_results),
                    duration_ms=compile_ms + execute_ms,
                )
            )

            if state.mode == SpotlightSearchMode.DIRECT:
                break

            # Evaluate results
            evaluator = SpotlightEvaluator(
                llm=self.services.llm,
                tokenizer=self.services.tokenizer,
                logger=self.ctx.logger,
            )
            evaluation: SpotlightEvaluation = await evaluator.evaluate(state)
            state.current_iteration.evaluation = evaluation
            self.ctx.logger.debug(f"[SpotlightAgent] Evaluation: {evaluation.to_md()}")
            t = self._lap(timings, f"{prefix}/evaluate", t)

            # Emit evaluating event
            await self.emitter.emit(
                SpotlightEvaluatingEvent(
                    iteration=state.iteration_number,
                    evaluation=evaluation,
                )
            )

            if not state.current_iteration.evaluation.should_continue:
                break

            # Create history iteration from completed current iteration
            history_iteration = SpotlightHistoryIteration(
                plan=state.current_iteration.plan,
                compiled_query=state.current_iteration.compiled_query,
                evaluation=state.current_iteration.evaluation,
            )

            # Initialize or add to history
            if state.history is None:
                state.history = SpotlightHistory(
                    iterations={state.iteration_number: history_iteration}
                )
            else:
                state.history.add_iteration(state.iteration_number, history_iteration)

            # Prepare for next iteration
            state.iteration_number += 1
            state.current_iteration = SpotlightCurrentIteration()

        # Compose final answer
        composer = SpotlightComposer(
            llm=self.services.llm,
            tokenizer=self.services.tokenizer,
            logger=self.ctx.logger,
        )
        answer: SpotlightAnswer = await composer.compose(state)
        self._lap(timings, "compose", t)

        response = SpotlightResponse(
            results=state.current_iteration.search_results.results,
            answer=answer,
        )

        # Emit done event
        await self.emitter.emit(SpotlightDoneEvent(response=response))

        # Log final timing summary
        self._log_timings(timings, total_start)

        return response

    def _lap(self, timings: list, label: str, start: float) -> float:
        """Record a timing and return the new start time."""
        now = time.monotonic()
        timings.append((label, int((now - start) * 1000)))
        return now

    def _log_timings(self, timings: list, total_start: float) -> None:
        """Log all step timings in a single summary."""
        total_ms = int((time.monotonic() - total_start) * 1000)
        lines = [f"{'Step':<30} {'Duration':>8}"]
        lines.append("─" * 40)
        for label, ms in timings:
            lines.append(f"{label:<30} {ms:>6}ms")
        lines.append("─" * 40)
        lines.append(f"{'Total':<30} {total_ms:>6}ms")
        self.ctx.logger.info("[SpotlightAgent] Timings:\n" + "\n".join(lines))
