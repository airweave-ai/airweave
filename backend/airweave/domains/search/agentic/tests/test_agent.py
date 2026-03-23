"""Hardening tests for the Agent loop.

Uses FakeLLM with seeded response sequences to test the full
orchestration: setup → iteration → tool dispatch → context
management → finalization → event emission.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from airweave.adapters.event_bus.fake import FakeEventBus
from airweave.adapters.llm.exceptions import LLMAllProvidersFailedError, LLMFatalError
from airweave.adapters.llm.fakes import FakeLLM
from airweave.adapters.tokenizer.fakes import FakeTokenizer
from airweave.api.context import ApiContext
from airweave.core.events.search import (
    SearchCompletedEvent,
    SearchFailedEvent,
)
from airweave.core.logging import logger
from airweave.core.protocols.llm import LLMResponse, LLMToolCall
from airweave.core.shared_models import AuthMethod
from airweave.domains.collections.fakes.repository import FakeCollectionRepository
from airweave.domains.search.agentic.agent import Agent
from airweave.domains.search.agentic.exceptions import ContextBudgetExhaustedError
from airweave.domains.search.agentic.tests.conftest import make_model_spec, make_result
from airweave.domains.search.config import SearchConfig
from airweave.domains.search.fakes.executor import FakeSearchPlanExecutor
from airweave.domains.search.fakes.metadata_builder import FakeCollectionMetadataBuilder
from airweave.domains.search.types import SearchResults
from airweave.models.collection import Collection
from airweave.schemas.search_v2 import AgenticSearchRequest

# ── Test constants ────────────────────────────────────────────────────

DEFAULT_ORG_ID = uuid4()
DEFAULT_COLLECTION_ID = uuid4()
DEFAULT_READABLE_ID = "test-col"


# ── Helpers ───────────────────────────────────────────────────────────


def _make_ctx() -> ApiContext:
    """Build a minimal ApiContext for tests."""
    from airweave.schemas.organization import Organization

    now = datetime.now(timezone.utc)
    org = Organization(
        id=str(DEFAULT_ORG_ID),
        name="Test Org",
        created_at=now,
        modified_at=now,
        enabled_features=[],
    )
    return ApiContext(
        request_id="test-req-001",
        organization=org,
        auth_method=AuthMethod.SYSTEM,
        auth_metadata={},
        logger=logger.with_context(request_id="test-req-001"),
    )


def _make_collection() -> Collection:
    """Build a minimal Collection model."""
    now = datetime.now(timezone.utc)
    col = Collection(
        id=DEFAULT_COLLECTION_ID,
        name="Test Collection",
        readable_id=DEFAULT_READABLE_ID,
        organization_id=DEFAULT_ORG_ID,
        vector_db_deployment_metadata_id=uuid4(),
    )
    col.created_at = now
    col.modified_at = now
    return col


def _make_request(query: str = "find test documents") -> AgenticSearchRequest:
    """Build a search request."""
    return AgenticSearchRequest(query=query)


def _make_search_response(
    tool_calls: list[LLMToolCall] | None = None,
    text: str | None = None,
    thinking: str | None = None,
) -> LLMResponse:
    """Build an LLMResponse with optional tool calls."""
    return LLMResponse(
        text=text,
        thinking=thinking,
        tool_calls=tool_calls or [],
        prompt_tokens=100,
        completion_tokens=50,
    )


def _search_tool_call(
    tc_id: str = "tc-search",
    query: str = "test",
    limit: int = 10,
) -> LLMToolCall:
    """Build a search tool call."""
    return LLMToolCall(
        id=tc_id,
        name="search",
        arguments={
            "query": {"primary": query},
            "limit": limit,
            "offset": 0,
            "retrieval_strategy": "hybrid",
        },
    )


def _add_results_tool_call(
    tc_id: str = "tc-add",
    entity_ids: list[str] | None = None,
) -> LLMToolCall:
    """Build an add_to_results tool call."""
    return LLMToolCall(
        id=tc_id,
        name="add_to_results",
        arguments={"entity_ids": entity_ids or ["ent-1"]},
    )


def _return_results_tool_call(tc_id: str = "tc-return") -> LLMToolCall:
    """Build a return_results_to_user tool call."""
    return LLMToolCall(
        id=tc_id,
        name="return_results_to_user",
        arguments={},
    )


def _build_agent(
    llm: FakeLLM | None = None,
    executor: FakeSearchPlanExecutor | None = None,
    event_bus: FakeEventBus | None = None,
    collection_repo: FakeCollectionRepository | None = None,
    metadata_builder: FakeCollectionMetadataBuilder | None = None,
    config: SearchConfig | None = None,
) -> Agent:
    """Build an Agent with fakes for all dependencies."""
    from airweave.domains.search.adapters.vector_db.fakes import FakeVectorDB

    model_spec = make_model_spec()

    if collection_repo is None:
        collection_repo = FakeCollectionRepository()
        collection_repo.seed_readable(DEFAULT_READABLE_ID, _make_collection())

    if metadata_builder is None:
        metadata_builder = FakeCollectionMetadataBuilder()

    return Agent(
        llm=llm or FakeLLM(model_spec),
        tokenizer=FakeTokenizer(),
        reranker=None,
        executor=executor or FakeSearchPlanExecutor(),
        vector_db=FakeVectorDB(),
        metadata_builder=metadata_builder,
        collection_repo=collection_repo,
        event_bus=event_bus or FakeEventBus(),
        config=config or SearchConfig(),
    )


# ── Happy path tests ──────────────────────────────────────────────────


class TestAgentHappyPath:
    """Tests for normal agent execution."""

    @pytest.mark.asyncio
    async def test_search_collect_return(self) -> None:
        """Agent searches, collects results, and returns them."""
        r1 = make_result(entity_id="ent-1", name="Doc A")
        executor = FakeSearchPlanExecutor()
        executor.seed_result(SearchResults(results=[r1]))

        model_spec = make_model_spec()
        llm = FakeLLM(model_spec)

        # Iteration 1: search
        llm.seed_tool_response(_make_search_response(tool_calls=[_search_tool_call()]))
        # Iteration 2: collect + return
        llm.seed_tool_response(
            _make_search_response(
                tool_calls=[
                    _add_results_tool_call(entity_ids=["ent-1"]),
                    _return_results_tool_call(),
                ]
            )
        )

        agent = _build_agent(llm=llm, executor=executor)
        results = await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        assert len(results.results) == 1
        assert results.results[0].entity_id == "ent-1"

    @pytest.mark.asyncio
    async def test_empty_collection_returns_empty(self) -> None:
        """Agent returns immediately with no results."""
        llm = FakeLLM(make_model_spec())
        llm.seed_tool_response(_make_search_response(tool_calls=[_return_results_tool_call()]))

        agent = _build_agent(llm=llm)
        results = await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        assert results.results == []


# ── Error path tests ──────────────────────────────────────────────────


class TestAgentErrorPaths:
    """Tests for error handling in the agent loop."""

    @pytest.mark.asyncio
    async def test_max_iterations_returns_partial(self) -> None:
        """Agent hits max iterations → returns whatever was collected."""
        config = SearchConfig()
        config.MAX_ITERATIONS = 3

        executor = FakeSearchPlanExecutor()
        executor.seed_result(SearchResults(results=[]))

        llm = FakeLLM(make_model_spec())
        # 3 iterations of searching, never finishes
        for _ in range(3):
            llm.seed_tool_response(_make_search_response(tool_calls=[_search_tool_call()]))

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, executor=executor, event_bus=event_bus, config=config)
        results = await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        assert results.results == []
        # Completed event should have max_iterations_hit
        completed = event_bus.get_events("search.completed")
        assert len(completed) == 1
        assert completed[0].diagnostics.max_iterations_hit is True

    @pytest.mark.asyncio
    async def test_no_tool_calls_forced_finish(self) -> None:
        """LLM responds with text only 3 times → forced finish."""
        llm = FakeLLM(make_model_spec())
        for _ in range(3):
            llm.seed_tool_response(_make_search_response(text="I'm thinking about this..."))

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, event_bus=event_bus)
        results = await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        assert results.results == []
        # 3 thinking events emitted
        thinking = event_bus.get_events("search.thinking")
        assert len(thinking) == 3

    @pytest.mark.asyncio
    async def test_tool_error_does_not_crash(self) -> None:
        """Bad tool args → error returned to LLM → agent continues."""
        llm = FakeLLM(make_model_spec())
        # Iteration 1: bad search args
        llm.seed_tool_response(
            _make_search_response(
                tool_calls=[
                    LLMToolCall(
                        id="tc-bad",
                        name="search",
                        arguments={"invalid": "args"},
                    )
                ]
            )
        )
        # Iteration 2: give up
        llm.seed_tool_response(_make_search_response(tool_calls=[_return_results_tool_call()]))

        agent = _build_agent(llm=llm)
        results = await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        # Should complete without crashing
        assert results.results == []

    @pytest.mark.asyncio
    async def test_collection_not_found_raises_404(self) -> None:
        """Unknown readable_id → CollectionNotFoundException."""
        from airweave.core.exceptions import CollectionNotFoundException

        empty_repo = FakeCollectionRepository()
        agent = _build_agent(collection_repo=empty_repo)

        with pytest.raises(CollectionNotFoundException):
            await agent.run(AsyncMock(), _make_ctx(), "nonexistent", _make_request())


# ── Event emission tests ──────────────────────────────────────────────


class TestAgentEvents:
    """Tests for event emission during the agent loop."""

    @pytest.mark.asyncio
    async def test_completed_event_has_diagnostics(self) -> None:
        """SearchCompletedEvent emitted with token counts and iteration info."""
        llm = FakeLLM(make_model_spec())
        llm.seed_tool_response(_make_search_response(tool_calls=[_return_results_tool_call()]))

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, event_bus=event_bus)
        await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        completed = event_bus.get_events("search.completed")
        assert len(completed) == 1
        event = completed[0]
        assert isinstance(event, SearchCompletedEvent)
        assert event.diagnostics is not None
        assert event.diagnostics.prompt_tokens == 100
        assert event.diagnostics.completion_tokens == 50
        assert event.diagnostics.total_iterations == 1

    @pytest.mark.asyncio
    async def test_thinking_event_per_iteration(self) -> None:
        """Each LLM call emits one SearchThinkingEvent."""
        llm = FakeLLM(make_model_spec())
        llm.seed_tool_response(
            _make_search_response(
                text="Searching...",
                thinking="I should look for documents",
                tool_calls=[_search_tool_call()],
            )
        )
        llm.seed_tool_response(_make_search_response(tool_calls=[_return_results_tool_call()]))

        executor = FakeSearchPlanExecutor()
        executor.seed_result(SearchResults(results=[]))

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, executor=executor, event_bus=event_bus)
        await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        thinking = event_bus.get_events("search.thinking")
        assert len(thinking) == 2
        assert thinking[0].thinking == "I should look for documents"
        assert thinking[0].text == "Searching..."

    @pytest.mark.asyncio
    async def test_tool_called_event_per_tool(self) -> None:
        """Each tool execution emits one SearchToolCalledEvent."""
        r1 = make_result(entity_id="ent-1")
        executor = FakeSearchPlanExecutor()
        executor.seed_result(SearchResults(results=[r1]))

        llm = FakeLLM(make_model_spec())
        llm.seed_tool_response(
            _make_search_response(
                tool_calls=[
                    _search_tool_call("tc-1"),
                    _add_results_tool_call("tc-2", ["ent-1"]),
                ]
            )
        )
        llm.seed_tool_response(
            _make_search_response(tool_calls=[_return_results_tool_call("tc-3")])
        )

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, executor=executor, event_bus=event_bus)
        await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        tool_events = event_bus.get_events("search.tool_called")
        assert len(tool_events) == 3  # search + add + return
        tool_names = [e.tool_name for e in tool_events]
        assert "search" in tool_names
        assert "add_to_results" in tool_names
        assert "return_results_to_user" in tool_names

    @pytest.mark.asyncio
    async def test_failed_event_on_crash(self) -> None:
        """Unhandled exception → SearchFailedEvent with diagnostics."""
        llm = FakeLLM(make_model_spec())
        # No responses seeded → FakeLLM raises RuntimeError

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, event_bus=event_bus)

        with pytest.raises(RuntimeError, match="no seeded"):
            await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        failed = event_bus.get_events("search.failed")
        assert len(failed) == 1
        assert isinstance(failed[0], SearchFailedEvent)
        assert failed[0].diagnostics.iteration == 0

    @pytest.mark.asyncio
    async def test_token_counts_accumulated(self) -> None:
        """Token counts from multiple iterations are summed in diagnostics."""
        llm = FakeLLM(make_model_spec())
        executor = FakeSearchPlanExecutor()
        executor.seed_result(SearchResults(results=[]))

        # 2 iterations, 100 prompt + 50 completion each
        llm.seed_tool_response(_make_search_response(tool_calls=[_search_tool_call()]))
        llm.seed_tool_response(_make_search_response(tool_calls=[_return_results_tool_call()]))

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, executor=executor, event_bus=event_bus)
        await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        completed = event_bus.get_events("search.completed")
        assert completed[0].diagnostics.prompt_tokens == 200  # 100 × 2
        assert completed[0].diagnostics.completion_tokens == 100  # 50 × 2


# ── LLM error tests ──────────────────────────────────────────────────


class TestAgentLLMErrors:
    """Tests for LLM-level errors propagated through the agent loop."""

    @pytest.mark.asyncio
    async def test_llm_fatal_error_emits_failed_event(self) -> None:
        """LLMFatalError from the LLM → SearchFailedEvent published."""
        llm = FakeLLM(make_model_spec())
        llm.seed_error(LLMFatalError("context too large", provider="test"))

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, event_bus=event_bus)

        with pytest.raises(LLMFatalError, match="context too large"):
            await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        failed = event_bus.get_events("search.failed")
        assert len(failed) == 1
        assert isinstance(failed[0], SearchFailedEvent)

    @pytest.mark.asyncio
    async def test_llm_all_providers_failed_emits_failed_event(self) -> None:
        """LLMAllProvidersFailedError → SearchFailedEvent published."""
        llm = FakeLLM(make_model_spec())
        llm.seed_error(
            LLMAllProvidersFailedError([("p1", LLMFatalError("down", provider="p1"))])
        )

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, event_bus=event_bus)

        with pytest.raises(LLMAllProvidersFailedError):
            await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        failed = event_bus.get_events("search.failed")
        assert len(failed) == 1
        assert isinstance(failed[0], SearchFailedEvent)

    @pytest.mark.asyncio
    async def test_partial_results_in_failed_diagnostics(self) -> None:
        """LLM crash after collecting results → diagnostics.partial_results_count > 0."""
        r1 = make_result(entity_id="ent-1", name="Doc A")
        executor = FakeSearchPlanExecutor()
        executor.seed_result(SearchResults(results=[r1]))

        llm = FakeLLM(make_model_spec())
        # Iteration 1: search + collect
        llm.seed_tool_response(
            _make_search_response(
                tool_calls=[
                    _search_tool_call(),
                    _add_results_tool_call(entity_ids=["ent-1"]),
                ]
            )
        )
        # Iteration 2: LLM crashes
        llm.seed_error(LLMFatalError("overloaded", provider="test"))

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, executor=executor, event_bus=event_bus)

        with pytest.raises(LLMFatalError, match="overloaded"):
            await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        failed = event_bus.get_events("search.failed")
        assert len(failed) == 1
        assert failed[0].diagnostics.partial_results_count > 0


# ── Context budget tests ─────────────────────────────────────────────


class TestAgentContextBudget:
    """Tests for context budget exhaustion."""

    @pytest.mark.asyncio
    async def test_budget_exhausted_raises(self) -> None:
        """Tiny context window → ContextBudgetExhaustedError after first tool call."""
        # A very small context window: after system prompt + tools + user message,
        # the budget check (check_budget) should return False.
        small_spec = make_model_spec(context_window=500, max_output_tokens=100)
        llm = FakeLLM(small_spec)
        # Seed one response with a tool call — the budget check happens AFTER
        # compress_history and BEFORE tool execution within the iteration.
        llm.seed_tool_response(_make_search_response(tool_calls=[_search_tool_call()]))

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, event_bus=event_bus)

        with pytest.raises(ContextBudgetExhaustedError):
            await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        # Should also emit a failed event
        failed = event_bus.get_events("search.failed")
        assert len(failed) == 1
        assert isinstance(failed[0], SearchFailedEvent)


# ── Tool recovery tests ──────────────────────────────────────────────


class TestAgentToolRecovery:
    """Tests for the agent loop recovering from tool-level errors."""

    @pytest.mark.asyncio
    async def test_tool_error_returned_to_llm_loop_continues(self) -> None:
        """Executor error during search → error fed back to LLM → loop finishes."""
        executor = FakeSearchPlanExecutor()
        executor.seed_error(RuntimeError("vector DB timeout"))

        llm = FakeLLM(make_model_spec())
        # Iteration 1: search (will fail via executor error)
        llm.seed_tool_response(_make_search_response(tool_calls=[_search_tool_call()]))
        # Iteration 2: give up gracefully
        llm.seed_tool_response(_make_search_response(tool_calls=[_return_results_tool_call()]))

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, executor=executor, event_bus=event_bus)
        results = await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        assert results.results == []
        completed = event_bus.get_events("search.completed")
        assert len(completed) == 1
        assert isinstance(completed[0], SearchCompletedEvent)

    @pytest.mark.asyncio
    async def test_unknown_tool_error_returned_to_llm(self) -> None:
        """LLM calls a nonexistent tool → error returned → loop finishes."""
        llm = FakeLLM(make_model_spec())
        # Iteration 1: call a tool that doesn't exist
        llm.seed_tool_response(
            _make_search_response(
                tool_calls=[
                    LLMToolCall(
                        id="tc-bad",
                        name="nonexistent_tool",
                        arguments={},
                    )
                ]
            )
        )
        # Iteration 2: finish normally
        llm.seed_tool_response(_make_search_response(tool_calls=[_return_results_tool_call()]))

        event_bus = FakeEventBus()
        agent = _build_agent(llm=llm, event_bus=event_bus)
        results = await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        assert results.results == []
        completed = event_bus.get_events("search.completed")
        assert len(completed) == 1
        assert isinstance(completed[0], SearchCompletedEvent)


# ── Reranker tests ───────────────────────────────────────────────────


class TestAgentReranker:
    """Tests for reranker behavior in the agent loop."""

    @pytest.mark.asyncio
    async def test_no_reranker_returns_unranked(self) -> None:
        """Agent with reranker=None returns results in collection order."""
        r1 = make_result(entity_id="ent-1", name="Doc A", score=0.80)
        r2 = make_result(entity_id="ent-2", name="Doc B", score=0.95)
        executor = FakeSearchPlanExecutor()
        executor.seed_result(SearchResults(results=[r1, r2]))

        llm = FakeLLM(make_model_spec())
        # Iteration 1: search + collect both
        llm.seed_tool_response(
            _make_search_response(
                tool_calls=[
                    _search_tool_call(),
                    _add_results_tool_call("tc-add-1", ["ent-1"]),
                    _add_results_tool_call("tc-add-2", ["ent-2"]),
                    _return_results_tool_call(),
                ]
            )
        )

        event_bus = FakeEventBus()
        # _build_agent already passes reranker=None
        agent = _build_agent(llm=llm, executor=executor, event_bus=event_bus)
        results = await agent.run(AsyncMock(), _make_ctx(), DEFAULT_READABLE_ID, _make_request())

        # Results should be present — no reranking event emitted
        assert len(results.results) == 2
        result_ids = {r.entity_id for r in results.results}
        assert result_ids == {"ent-1", "ent-2"}

        # No reranking event should have been published
        reranking = event_bus.get_events("search.reranking")
        assert len(reranking) == 0

        # Completed event should still be emitted
        completed = event_bus.get_events("search.completed")
        assert len(completed) == 1
