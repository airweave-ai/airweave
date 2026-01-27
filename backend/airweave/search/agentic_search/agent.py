"""Agentic search agent."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from airweave.api.context import ApiContext
from airweave.search.agentic_search.builder import AgenticQueryBuilder
from airweave.search.agentic_search.openai import AgenticEmbedder
from airweave.search.agentic_search.planner import Planner
from airweave.search.agentic_search.state import AgenticSearchState


def _format_params_for_logging(params: dict[str, Any]) -> str:
    """Format query params for readable logging, summarizing embedding vectors.

    Args:
        params: The query parameters dict

    Returns:
        A formatted string representation
    """
    lines = []
    for key, value in params.items():
        if isinstance(value, dict) and "values" in value:
            # This is an embedding vector - summarize it
            vec = value["values"]
            dim = len(vec) if isinstance(vec, list) else "?"
            lines.append(f"  {key}: <vector dim={dim}>")
        elif key == "input.query(q_sparse)" and isinstance(value, dict):
            # Sparse vector - show token count
            cells = value.get("cells", {})
            lines.append(f"  {key}: <sparse tokens={len(cells)}>")
        else:
            lines.append(f"  {key}: {value}")
    return "\n".join(lines)


# Test configuration
COLLECTION_READABLE_ID = "evalfirstcc3aa2122e17-blc406"
ORIGINAL_QUERY = "Why is Daan interested in trading?"


async def run(
    query: str,
    collection_id: str,
    db: AsyncSession,
    ctx: ApiContext,
) -> None:
    """Run the agentic search loop.

    Args:
        query: The user's search query
        collection_id: The collection's readable ID
        db: Database session
        ctx: API context with logger
    """
    ctx.logger.info(f"[AgenticSearch] Starting for query: {query}")

    # Create state
    state = AgenticSearchState(
        original_query=query,
        collection_id=collection_id,
    )

    # Log initial state
    ctx.logger.info(f"[AgenticSearch] Initial state:{state.format_for_logging()}")

    # Create components
    planner = Planner(ctx=ctx)
    embedder = AgenticEmbedder(ctx=ctx)
    builder = AgenticQueryBuilder(ctx=ctx)

    # === ITERATION LOOP ===
    while not state.has_reached_max_iterations:
        ctx.logger.info(f"[AgenticSearch] === ITERATION {state.iteration + 1} ===")

        # Step 1: PLANNER - Generate search plan
        ctx.logger.debug("[AgenticSearch] Step 1: PLANNER")
        plan = await planner.plan(state, db, ctx)
        ctx.logger.debug(f"[AgenticSearch] Plan: {plan.queries} ({plan.retrieval_strategy.value})")

        # Step 2: EMBEDDER - Generate embeddings for queries
        ctx.logger.debug("[AgenticSearch] Step 2: EMBEDDER")
        embeddings = await embedder.embed(
            queries=plan.queries,
            strategy=plan.retrieval_strategy,
        )
        state.embeddings[state.iteration] = embeddings
        dense_count = len(embeddings.dense) if embeddings.dense else 0
        has_sparse = "yes" if embeddings.sparse else "no"
        ctx.logger.debug(f"[AgenticSearch] Embeddings: dense={dense_count}, sparse={has_sparse}")

        # Step 3: BUILDER - Build YQL from plan + embeddings
        ctx.logger.debug("[AgenticSearch] Step 3: BUILDER")
        yql, params = builder.build(plan, embeddings, state.collection_id)
        state.yqls[state.iteration] = yql
        ctx.logger.info(f"[AgenticSearch] Generated YQL:\n{yql}")
        ctx.logger.debug(f"[AgenticSearch] Generated params:\n{_format_params_for_logging(params)}")

        # Step 4: EXECUTOR - Fire YQL at Vespa
        # TODO: Implement executor
        ctx.logger.debug("[AgenticSearch] Step 4: EXECUTOR (TODO)")

        # Step 5: JUDGE - Evaluate results
        # TODO: Implement judge
        ctx.logger.debug("[AgenticSearch] Step 5: JUDGE (TODO)")

        # Log state after iteration
        ctx.logger.info(f"[AgenticSearch] State:{state.format_for_logging()}")

        # Increment iteration (TODO: break based on judge decision)
        state.iteration += 1
        break  # Temporary: stop after first iteration until judge is implemented

    ctx.logger.info("[AgenticSearch] Search complete")
