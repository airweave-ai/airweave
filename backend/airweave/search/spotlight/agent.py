"""Spotlight search agent."""

# =============================================================================
# Agent Flow (pseudocode)
# =============================================================================
#
# 1. collection_readable_id -> build_collection_metadata() -> collection_metadata
# 2. user_query, collection_metadata -> initialize state -> state
# 3. state.collection_metadata, state.user_query, state.history -> planner -> plan
# 4. plan.query, plan.retrieval_strategy -> embed -> query_embeddings
# 5. plan, query_embeddings, collection_id -> vector_db.compile_query() -> compiled_query
# 6. compiled_query -> vector_db.execute_query() -> search_results
# 7. state (all context) -> evaluator -> evaluation
# 8. loop back to step 3 if evaluation.should_continue
# 9. final_results -> composer -> answer
#
# NOTE: to_md() methods for context formatting
# NOTE: tokenizer for context window management
