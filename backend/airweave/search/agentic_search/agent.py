"""Agentic search agent."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from airweave import crud
from airweave.api.context import ApiContext
from airweave.schemas.search_result import AirweaveSearchResult
from airweave.search.agentic_search.builder import AgenticQueryBuilder
from airweave.search.agentic_search.emitter import (
    AgenticSearchEvent,
    EventEmitter,
    NoOpEmitter,
)
from airweave.search.agentic_search.executor import Executor
from airweave.search.agentic_search.judge import Judge
from airweave.search.agentic_search.openai import AgenticEmbedder
from airweave.search.agentic_search.planner import Planner
from airweave.search.agentic_search.state import AgenticSearchState

# TODO: fire multiple queries at once


async def run(  # noqa: C901 - orchestration function, complexity acceptable
    query: str,
    collection_id: str,
    db: AsyncSession,
    ctx: ApiContext,
    emitter: Optional[EventEmitter] = None,
) -> AgenticSearchState:
    """Run the agentic search loop.

    Args:
        query: The user's search query
        collection_id: The collection's readable ID
        db: Database session
        ctx: API context with logger
        emitter: Optional event emitter for streaming progress to user

    Returns:
        The final AgenticSearchState with all results
    """
    # Use no-op emitter if none provided
    if emitter is None:
        emitter = NoOpEmitter()
    ctx.logger.info(f"[AgenticSearch] Starting for query: {query}")

    # Look up the collection to get the UUID (needed for Vespa filtering)
    collection = await crud.collection.get_by_readable_id(db, readable_id=collection_id, ctx=ctx)
    if not collection:
        raise ValueError(f"Collection not found: {collection_id}")

    # Get collection UUID as string for Vespa filtering
    collection_uuid_str = str(collection.id)

    # Create state (collection_id is readable_id for context, collection_uuid is for Vespa)
    state = AgenticSearchState(
        original_query=query,
        collection_id=collection_id,
        collection_uuid=collection_uuid_str,
    )

    # Log initial state
    ctx.logger.info(f"[AgenticSearch] Initial state:{state.format_for_logging()}")

    # Create components
    planner = Planner(ctx=ctx)
    embedder = AgenticEmbedder(ctx=ctx)
    builder = AgenticQueryBuilder(ctx=ctx)
    executor = Executor(ctx=ctx)
    judge = Judge(ctx=ctx)

    try:
        # === ITERATION LOOP ===
        while not state.has_reached_max_iterations:
            iteration_num = state.iteration + 1
            ctx.logger.info(f"[AgenticSearch] === ITERATION {iteration_num} ===")

            # Step 1: PLANNER - Generate search plan
            ctx.logger.debug("[AgenticSearch] Step 1: PLANNER")

            plan = await planner.plan(state, db, ctx)

            # Emit: Collection summary (first iteration only, after planner populates it)
            if state.is_first_iteration and state.collection_summary:
                summary = state.collection_summary
                # Build a detailed message with counts per source per entity type
                source_parts = []
                for source_name, entity_counts in summary.get("sources", {}).items():
                    entity_parts = [f"{count} {etype}" for etype, count in entity_counts.items()]
                    source_parts.append(f"{source_name}: {', '.join(entity_parts)}")
                sources_detail = "; ".join(source_parts)
                total = summary["total_entities"]
                await emitter.emit(
                    AgenticSearchEvent(
                        message=f"Searching {total} entities ({sources_detail})",
                    )
                )

            # Emit: Plan reasoning
            await emitter.emit(AgenticSearchEvent(message=plan.reasoning))

            # Step 2: EMBEDDER - Generate embeddings for queries
            ctx.logger.debug("[AgenticSearch] Step 2: EMBEDDER")
            embeddings = await embedder.embed(
                queries=plan.queries,
                strategy=plan.retrieval_strategy,
            )
            state.embeddings[state.iteration] = embeddings
            dense_count = len(embeddings.dense) if embeddings.dense else 0
            has_sparse = "yes" if embeddings.sparse else "no"
            ctx.logger.debug(
                f"[AgenticSearch] Embeddings: dense={dense_count}, sparse={has_sparse}"
            )

            # Step 3: BUILDER - Build VespaQuery from plan + embeddings
            ctx.logger.debug("[AgenticSearch] Step 3: BUILDER")

            vespa_query = builder.build(plan, embeddings, state.collection_uuid)
            state.vespa_queries[state.iteration] = vespa_query
            ctx.logger.info(f"[AgenticSearch] Generated YQL:\n{vespa_query.yql}")
            ctx.logger.debug(
                f"[AgenticSearch] Generated params:\n{vespa_query.format_params_for_logging()}"
            )

            # Step 4: EXECUTOR - Execute query against Vespa
            ctx.logger.debug("[AgenticSearch] Step 4: EXECUTOR")

            try:
                results = await executor.execute(vespa_query)
                state.results[state.iteration] = results
                ctx.logger.info(f"[AgenticSearch] Got {len(results)} results")
                ctx.logger.info(
                    f"[AgenticSearch] Results:"
                    f"{AirweaveSearchResult.format_results_for_logging(results)}"
                )

                # Emit: Results count
                await emitter.emit(AgenticSearchEvent(message=f"Found {len(results)} documents"))

            except Exception as e:
                error_msg = f"Query execution failed: {e}"
                state.errors[state.iteration] = error_msg
                ctx.logger.error(f"[AgenticSearch] {error_msg}")

                # Emit: Error
                await emitter.emit(AgenticSearchEvent(message=str(e), error=True))

            # Step 5: JUDGE - Evaluate results
            ctx.logger.debug("[AgenticSearch] Step 5: JUDGE")

            judgement = await judge.judge(state, ctx)

            # Emit: Judge evaluation
            await emitter.emit(AgenticSearchEvent(message=judgement.reasoning))

            # Emit: Judge advice (if continuing)
            if judgement.should_continue and judgement.advice:
                await emitter.emit(AgenticSearchEvent(message=judgement.advice))

            # Log state after iteration
            ctx.logger.info(f"[AgenticSearch] State:{state.format_for_logging()}")

            # Check if we should continue
            if not judgement.should_continue:
                ctx.logger.info("[AgenticSearch] Judge decided to stop searching")
                # Set final results to the useful results from current iteration
                current_results = state.results.get(state.iteration, [])
                useful_ids = set(judgement.useful_result_ids)
                state.final_results = [r for r in current_results if r.entity_id in useful_ids]
                # If no useful results identified, use all results
                if not state.final_results:
                    state.final_results = current_results

                # Emit: Answer snippet (highlighted key quote)
                if judgement.answer_snippet:
                    await emitter.emit(
                        AgenticSearchEvent(
                            message=f">>> {judgement.answer_snippet}",
                        )
                    )
                break

            # Increment iteration for next loop
            state.iteration += 1

        ctx.logger.info("[AgenticSearch] Search complete")

        # Emit: Final results (use mode='json' to handle datetime serialization)
        await emitter.emit(
            AgenticSearchEvent(
                message="",
                data={
                    "answer_snippet": state.latest_judgement.answer_snippet
                    if state.latest_judgement
                    else None,
                    "results": [r.model_dump(mode="json") for r in state.final_results]
                    if state.final_results
                    else [],
                },
                done=True,
            )
        )

        return state

    except Exception as e:
        # Emit: Fatal error
        await emitter.emit(
            AgenticSearchEvent(
                message=f"Search failed: {e}",
                error=True,
                done=True,
            )
        )
        raise

    finally:
        # Clean up executor connection
        await executor.close()
