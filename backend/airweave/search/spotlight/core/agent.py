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
from airweave.search.spotlight.schemas.request import SpotlightSearchMode
from airweave.search.spotlight.schemas.search_result import SpotlightSearchResults
from airweave.search.spotlight.services import SpotlightServices


class SpotlightAgent:
    """Spotlight search agent."""

    def __init__(self, services: SpotlightServices, ctx: ApiContext):
        """Initialize the agent."""
        self.services: SpotlightServices = services
        self.ctx: ApiContext = ctx

    async def run(self, collection_readable_id: str, request: SpotlightRequest):
        """Run the agent."""
        # Build collection metadata
        collection_metadata_builder = SpotlightCollectionMetadataBuilder(self.services.db)
        collection_metadata: SpotlightCollectionMetadata = await collection_metadata_builder.build(
            collection_readable_id
        )

        # Build initial state
        state_builder = SpotlightStateBuilder()
        state: SpotlightState = state_builder.build_initial(
            request=request,
            collection_metadata=collection_metadata,
        )

        while True:
            # Create search plan
            planner = SpotlightPlanner(
                llm=self.services.llm,
                tokenizer=self.services.tokenizer,
                logger=self.ctx.logger,
            )
            plan: SpotlightPlan = await planner.plan(state)
            state.current_iteration.plan = plan

            # Build complete plan (LLM filters + user filters) for execution
            complete_plan_builder = SpotlightCompletePlanBuilder()
            complete_plan: SpotlightPlan = complete_plan_builder.build(plan, state.user_filter)

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

            # Compile query
            compiled_query: SpotlightCompiledQuery = await self.services.vector_db.compile_query(
                plan=complete_plan,
                embeddings=state.current_iteration.query_embeddings,
                collection_id=state.collection_metadata.collection_id,
            )
            state.current_iteration.compiled_query = compiled_query

            # Execute query
            search_results: SpotlightSearchResults = await self.services.vector_db.execute_query(
                compiled_query
            )
            state.current_iteration.search_results = search_results

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

        return SpotlightResponse(
            results=state.current_iteration.search_results.results,
            answer=answer,
        )
