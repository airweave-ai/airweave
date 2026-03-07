"""Agentic search agent.

Conversation + tool-calling architecture:
  1. Build system prompt with collection metadata
  2. Send initial user message with the search query
  3. Loop: LLM reasons in free text, calls search tool
  4. Context is managed via pruning old tool results
  5. Return accumulated search results

The conversation IS the history — no separate state/history objects needed.
"""

from airweave.api.context import ApiContext
from airweave.search.agentic_search.builders import (
    AgenticSearchCollectionMetadataBuilder,
)
from airweave.search.agentic_search.core.context_manager import summarize_old_search_results
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
from airweave.search.agentic_search.external.llm.tool_response import LLMToolResponse
from airweave.search.agentic_search.schemas import (
    AgenticSearchRequest,
    AgenticSearchResponse,
)
from airweave.search.agentic_search.schemas.events import (
    AgenticSearchDoneEvent,
    AgenticSearchErrorEvent,
    AgenticSearchThinkingEvent,
)
from airweave.search.agentic_search.schemas.state import AgenticSearchState
from airweave.search.agentic_search.services import AgenticSearchServices
from airweave.search.agentic_search.tools import (
    MARK_AS_RELEVANT_TOOL,
    READ_PREVIOUS_RESULTS_TOOL,
    SEARCH_TOOL,
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

    async def _run(
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
        tools = [SEARCH_TOOL, READ_PREVIOUS_RESULTS_TOOL, MARK_AS_RELEVANT_TOOL]

        self.ctx.logger.debug(
            f"[AgenticSearch] Starting agent loop for query: {request.query!r} "
            f"on collection: {collection_readable_id}"
        )

        while True:
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

            # Call LLM with tools
            response = await self.services.llm.create_with_tools(
                messages=state.messages,
                tools=tools,
                system_prompt=system_prompt,
            )

            # Debug: log thinking + tool calls (search plans)
            log_agent_response(state.iteration, response, self.ctx.logger)

            # Emit thinking event (extended thinking + regular text)
            await self._emit_thinking(response, state)

            # Append assistant message (reasoning + tool calls)
            state.messages.append(build_assistant_message(response.text, response.tool_calls))

            if not response.tool_calls:
                self.ctx.logger.debug(
                    f"[AgenticSearch] Agent stopped after {state.iteration} iterations, "
                    f"{len(state.marked_entity_ids)} results marked"
                )
                break

            # Execute each tool call and append result message
            has_new_search = False
            new_search_tool_call_ids: set[str] = set()
            for tc in response.tool_calls:
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
                except Exception as e:
                    content = f"Tool call failed: {e}"

                msg = build_tool_result_message(tc.id, content)
                msg["_tool_name"] = tc.name
                state.messages.append(msg)
                if tc.name == "search":
                    has_new_search = True
                    new_search_tool_call_ids.add(tc.id)

            # Summarize old search results only when new ones just arrived
            if has_new_search:
                state.messages = summarize_old_search_results(
                    state.messages,
                    state.results_by_tool_call_id,
                    skip_tool_call_ids=new_search_tool_call_ids,
                )

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
        await self.emitter.emit(AgenticSearchDoneEvent(response=resp))
        return resp

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
