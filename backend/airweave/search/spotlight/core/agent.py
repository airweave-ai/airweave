"""Spotlight search agent."""

# NOTE: to_md()
# NOTE: where to deal with context window

# TODO: add type hints in each step

# X collection_readable_id -> create collection metadata -> collection_metadata
# X user_query, collection_metadata -> initaliaze state -> state
# state.collection_metadata.to_md(), state.user_query, state.history.to_md() -> planner -> plan
# TODO: add user filters to plan (tell the evaluator that these can not be adjusted)
# state.current_iteration.plan.query, state.current_iteration.plan.retrieval_strategy -> embed
# state.current_iteration.plan, query_embeddings, collection_id -> vector_db.compile_query()
# state.current_iteration.compiled_query -> vector_db.execute_query() -> search_results
# state context -> evaluator -> evaluation

# final_results = state.current_iteration.search_results
# composer -> answer

from airweave.api.context import ApiContext
from airweave.search.spotlight.builders import (
    SpotlightCollectionMetadataBuilder,
    SpotlightStateBuilder,
)
from airweave.search.spotlight.core.planner import SpotlightPlanner
from airweave.search.spotlight.schemas import (
    SpotlightAnswer,
    SpotlightCollectionMetadata,
    SpotlightPlan,
    SpotlightRequest,
    SpotlightResponse,
    SpotlightState,
)
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
            _plan: SpotlightPlan = await planner.plan(state)  # TODO: use in next steps

            break

        return SpotlightResponse(
            results=[],
            answer=SpotlightAnswer(
                text="",
                citations=[],
            ),
        )
