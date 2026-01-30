"""Spotlight search agent."""

# NOTE: to_md()
# NOTE: where to deal with context window

# collection_readable_id -> create collection metadata -> collection_metadata
# user_query, collection_metadata -> initaliaze state -> state
# state.collection_metadata.to_md(), state.user_query, state.history.to_md() ->  planner -> plan
# state.current_iteration.plan.query, state.current_iteration.plan.retrieval_strategy -> embed -> query_embeddings
# state.current_iteration.plan, state.current_iteration.query_embeddings, state.collection_metadata.collection_id -> vector_db.compile_query() -> compiled_query
# state.current_iteration.compiled_query -> vector_db.execute_query() -> search_results
# state.collection_metadata.to_md(), state.user_query, state.current_iteration.plan.to_md(), state.current_iteration.compiled_query.to_md(), state.current_iteration.search_results.to_md() -> evaluator -> evaluation

# final_results = state.current_iteration.search_results
# composer -> answer
