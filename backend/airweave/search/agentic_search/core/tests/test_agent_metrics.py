"""Unit tests for Prometheus metrics wiring in AgenticSearchAgent."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from airweave.adapters.metrics import FakeAgenticSearchMetrics
from airweave.search.agentic_search.core.agent import (
    AgenticSearchAgent,
    _STEP_LABEL_MAP,
)
from airweave.search.agentic_search.emitter import AgenticSearchNoOpEmitter
from airweave.search.agentic_search.schemas.answer import (
    AgenticSearchAnswer,
    AgenticSearchCitation,
)
from airweave.search.agentic_search.schemas.collection_metadata import (
    AgenticSearchCollectionMetadata,
)
from airweave.search.agentic_search.schemas.plan import (
    AgenticSearchPlan,
    AgenticSearchQuery,
)
from airweave.search.agentic_search.schemas.query_embeddings import (
    AgenticSearchQueryEmbeddings,
)
from airweave.search.agentic_search.schemas.request import (
    AgenticSearchMode,
    AgenticSearchRequest,
)
from airweave.search.agentic_search.schemas.response import AgenticSearchResponse
from airweave.search.agentic_search.schemas.retrieval_strategy import (
    AgenticSearchRetrievalStrategy,
)
from airweave.search.agentic_search.schemas.search_result import (
    AgenticSearchAccessControl,
    AgenticSearchBreadcrumb,
    AgenticSearchResult,
    AgenticSearchResults,
    AgenticSearchSystemMetadata,
)
from airweave.search.agentic_search.schemas.state import (
    AgenticSearchCurrentIteration,
    AgenticSearchState,
)
from airweave.search.agentic_search.services import AgenticSearchServices

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fake_metrics():
    return FakeAgenticSearchMetrics()


@pytest.fixture
def mock_ctx():
    ctx = MagicMock()
    ctx.logger = MagicMock(spec=logging.Logger)
    ctx.request_id = "test-req-001"
    return ctx


@pytest.fixture
def mock_emitter():
    return AgenticSearchNoOpEmitter()


@pytest.fixture
def mock_services():
    svc = MagicMock(spec=AgenticSearchServices)
    svc.db = AsyncMock()
    svc.llm = AsyncMock()
    svc.tokenizer = MagicMock()
    svc.dense_embedder = AsyncMock()
    svc.sparse_embedder = AsyncMock()
    svc.vector_db = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# Canned data helpers
# ---------------------------------------------------------------------------

_CANNED_METADATA = AgenticSearchCollectionMetadata(
    collection_id="col-1",
    collection_readable_id="test-collection",
    sources=[],
)

_CANNED_PLAN = AgenticSearchPlan(
    reasoning="test reasoning",
    query=AgenticSearchQuery(primary="test query"),
    filter_groups=[],
    limit=10,
    offset=0,
    retrieval_strategy=AgenticSearchRetrievalStrategy.HYBRID,
)

_CANNED_EMBEDDINGS = AgenticSearchQueryEmbeddings(
    dense_embeddings=None,
    sparse_embedding=None,
)


def _make_result(entity_id: str = "ent-1") -> AgenticSearchResult:
    return AgenticSearchResult(
        entity_id=entity_id,
        name="Test Entity",
        relevance_score=0.95,
        breadcrumbs=[
            AgenticSearchBreadcrumb(
                entity_id="parent-1", name="Parent", entity_type="FolderEntity"
            )
        ],
        textual_representation="some text",
        airweave_system_metadata=AgenticSearchSystemMetadata(
            source_name="test",
            entity_type="DocEntity",
            sync_id="sync-1",
            sync_job_id="job-1",
            chunk_index=0,
            original_entity_id="orig-1",
        ),
        access=AgenticSearchAccessControl(),
        web_url="https://example.com",
        raw_source_fields={},
    )


_CANNED_ANSWER = AgenticSearchAnswer(
    text="Here is the answer.",
    citations=[AgenticSearchCitation(entity_id="ent-1")],
)


# ===================================================================
# 2a. _record_metrics() unit tests
# ===================================================================


class TestRecordMetrics:
    """Direct tests for AgenticSearchAgent._record_metrics()."""

    def _make_agent(self, metrics, ctx, emitter, services):
        return AgenticSearchAgent(services, ctx, emitter, metrics=metrics)

    def test_noop_when_metrics_is_none(
        self, mock_ctx, mock_emitter, mock_services
    ):
        agent = self._make_agent(None, mock_ctx, mock_emitter, mock_services)
        # Should return without error
        agent._record_metrics(
            timings=[("iter_0/plan", 50)], mode="fast", iteration_count=1, result_count=5
        )

    def test_observes_iterations_and_results(
        self, fake_metrics, mock_ctx, mock_emitter, mock_services
    ):
        agent = self._make_agent(fake_metrics, mock_ctx, mock_emitter, mock_services)
        agent._record_metrics(
            timings=[], mode="fast", iteration_count=3, result_count=7
        )
        assert fake_metrics.iterations == [("fast", 3)]
        assert fake_metrics.results_counts == [7]

    def test_maps_timing_labels_to_steps(
        self, fake_metrics, mock_ctx, mock_emitter, mock_services
    ):
        agent = self._make_agent(fake_metrics, mock_ctx, mock_emitter, mock_services)
        timings = [
            ("iter_0/plan", 10),
            ("iter_0/embed", 20),
            ("iter_0/compile", 30),
            ("iter_0/execute", 40),
            ("iter_0/evaluate", 50),
            ("compose", 60),
        ]
        agent._record_metrics(
            timings=timings, mode="thinking", iteration_count=1, result_count=0
        )
        recorded_steps = [r.step for r in fake_metrics.step_durations]
        assert recorded_steps == ["plan", "embed", "search", "search", "evaluate", "compose"]

    def test_ignores_unknown_labels(
        self, fake_metrics, mock_ctx, mock_emitter, mock_services
    ):
        agent = self._make_agent(fake_metrics, mock_ctx, mock_emitter, mock_services)
        timings = [
            ("build_collection_metadata", 5),
            ("build_initial_state", 3),
            ("iter_0/plan", 10),
        ]
        agent._record_metrics(
            timings=timings, mode="fast", iteration_count=1, result_count=0
        )
        # Only "plan" should be recorded; the others don't appear in _STEP_LABEL_MAP
        assert len(fake_metrics.step_durations) == 1
        assert fake_metrics.step_durations[0].step == "plan"

    def test_search_error_label_maps_to_search(
        self, fake_metrics, mock_ctx, mock_emitter, mock_services
    ):
        agent = self._make_agent(fake_metrics, mock_ctx, mock_emitter, mock_services)
        timings = [("iter_0/search_error", 100)]
        agent._record_metrics(
            timings=timings, mode="fast", iteration_count=1, result_count=0
        )
        assert fake_metrics.step_durations[0].step == "search"

    def test_swallows_exceptions(
        self, mock_ctx, mock_emitter, mock_services
    ):
        broken_metrics = MagicMock()
        broken_metrics.observe_iterations.side_effect = RuntimeError("boom")
        agent = self._make_agent(broken_metrics, mock_ctx, mock_emitter, mock_services)
        # Should not raise
        agent._record_metrics(
            timings=[], mode="fast", iteration_count=1, result_count=0
        )
        mock_ctx.logger.debug.assert_called()


# ===================================================================
# 2b. run() try/except/finally wrapper tests
# ===================================================================


class TestRunMetricsWrapper:
    """Tests for the metrics instrumentation in AgenticSearchAgent.run()."""

    @pytest.fixture
    def agent(self, fake_metrics, mock_ctx, mock_emitter, mock_services):
        return AgenticSearchAgent(
            mock_services, mock_ctx, mock_emitter, metrics=fake_metrics
        )

    @pytest.fixture
    def fast_request(self):
        return AgenticSearchRequest(query="test", mode=AgenticSearchMode.FAST)

    @pytest.mark.asyncio
    async def test_success_records_request_and_duration(
        self, agent, fast_request, fake_metrics
    ):
        response = AgenticSearchResponse(results=[], answer=_CANNED_ANSWER)
        with patch.object(agent, "_run", new_callable=AsyncMock, return_value=response):
            result = await agent.run("col-1", fast_request)

        assert result is response
        assert len(fake_metrics.search_requests) == 1
        assert fake_metrics.search_requests[0] == ("fast", False)
        assert len(fake_metrics.durations) == 1
        assert fake_metrics.durations[0][0] == "fast"
        assert fake_metrics.durations[0][1] > 0

    @pytest.mark.asyncio
    @patch(
        "airweave.search.agentic_search.core.agent.track_agentic_search_error",
        new_callable=MagicMock,
    )
    async def test_error_records_error_request_and_duration(
        self, _mock_track, agent, fast_request, fake_metrics
    ):
        with patch.object(
            agent, "_run", new_callable=AsyncMock, side_effect=RuntimeError("fail")
        ):
            with pytest.raises(RuntimeError, match="fail"):
                await agent.run("col-1", fast_request)

        # Error counter incremented
        assert len(fake_metrics.search_errors) == 1
        assert fake_metrics.search_errors[0] == ("fast", False)
        # finally block still fires
        assert len(fake_metrics.search_requests) == 1
        assert len(fake_metrics.durations) == 1

    @pytest.mark.asyncio
    async def test_none_metrics_success(
        self, mock_ctx, mock_emitter, mock_services
    ):
        agent = AgenticSearchAgent(
            mock_services, mock_ctx, mock_emitter, metrics=None
        )
        request = AgenticSearchRequest(query="test", mode=AgenticSearchMode.FAST)
        response = AgenticSearchResponse(results=[], answer=_CANNED_ANSWER)
        with patch.object(agent, "_run", new_callable=AsyncMock, return_value=response):
            result = await agent.run("col-1", request)
        assert result is response

    @pytest.mark.asyncio
    @patch(
        "airweave.search.agentic_search.core.agent.track_agentic_search_error",
        new_callable=MagicMock,
    )
    async def test_none_metrics_error(
        self, _mock_track, mock_ctx, mock_emitter, mock_services
    ):
        agent = AgenticSearchAgent(
            mock_services, mock_ctx, mock_emitter, metrics=None
        )
        request = AgenticSearchRequest(query="test", mode=AgenticSearchMode.FAST)
        with patch.object(
            agent, "_run", new_callable=AsyncMock, side_effect=ValueError("bad")
        ):
            with pytest.raises(ValueError, match="bad"):
                await agent.run("col-1", request)


# ===================================================================
# 2c. _run() pipeline tests — FAST mode
# ===================================================================

_AGENT_MODULE = "airweave.search.agentic_search.core.agent"


class TestRunPipelineFastMode:
    """Integration-style tests for _run() in FAST mode.

    These patch the internal builders and components to isolate the
    orchestration logic and verify that metrics are recorded correctly.
    """

    @pytest.fixture
    def fast_request(self):
        return AgenticSearchRequest(query="test query", mode=AgenticSearchMode.FAST)

    @pytest.fixture
    def canned_results(self):
        return AgenticSearchResults(results=[_make_result("ent-1"), _make_result("ent-2")])

    def _build_patches(self, canned_results):
        """Return a dict of patch targets for the FAST-mode pipeline."""
        # Planner mock
        planner_instance = AsyncMock()
        planner_instance.plan = AsyncMock(return_value=_CANNED_PLAN)
        planner_instance.history_shown = 0
        planner_instance.history_total = 0

        # Embedder mock
        embedder_instance = AsyncMock()
        embedder_instance.embed = AsyncMock(return_value=_CANNED_EMBEDDINGS)

        # Composer mock
        composer_instance = AsyncMock()
        composer_instance.compose = AsyncMock(return_value=_CANNED_ANSWER)

        return {
            "metadata_builder": patch(
                f"{_AGENT_MODULE}.AgenticSearchCollectionMetadataBuilder",
                return_value=MagicMock(
                    build=AsyncMock(return_value=_CANNED_METADATA)
                ),
            ),
            "state_builder": patch(
                f"{_AGENT_MODULE}.AgenticSearchStateBuilder",
                return_value=MagicMock(
                    build_initial=MagicMock(
                        return_value=AgenticSearchState(
                            user_query="test query",
                            mode=AgenticSearchMode.FAST,
                            collection_metadata=_CANNED_METADATA,
                            iteration_number=0,
                            current_iteration=AgenticSearchCurrentIteration(),
                        )
                    )
                ),
            ),
            "planner": patch(
                f"{_AGENT_MODULE}.AgenticSearchPlanner",
                return_value=planner_instance,
            ),
            "embedder": patch(
                f"{_AGENT_MODULE}.AgenticSearchEmbedder",
                return_value=embedder_instance,
            ),
            "complete_plan": patch(
                f"{_AGENT_MODULE}.AgenticSearchCompletePlanBuilder.build",
                return_value=_CANNED_PLAN,
            ),
            "composer": patch(
                f"{_AGENT_MODULE}.AgenticSearchComposer",
                return_value=composer_instance,
            ),
            "track_completion": patch(
                f"{_AGENT_MODULE}.track_agentic_search_completion",
            ),
            "build_summaries": patch(
                f"{_AGENT_MODULE}.build_iteration_summaries",
                return_value=([], 0),
            ),
        }

    @pytest.mark.asyncio
    async def test_fast_mode_records_all_metrics(
        self,
        fake_metrics,
        mock_ctx,
        mock_emitter,
        mock_services,
        fast_request,
        canned_results,
    ):
        mock_services.vector_db.compile_query = AsyncMock(
            return_value=MagicMock()
        )
        mock_services.vector_db.execute_query = AsyncMock(
            return_value=canned_results
        )

        agent = AgenticSearchAgent(
            mock_services, mock_ctx, mock_emitter, metrics=fake_metrics
        )

        patches = self._build_patches(canned_results)
        with (
            patches["metadata_builder"],
            patches["state_builder"],
            patches["planner"],
            patches["embedder"],
            patches["complete_plan"],
            patches["composer"],
            patches["track_completion"],
            patches["build_summaries"],
        ):
            response = await agent.run("test-collection", fast_request)

        assert isinstance(response, AgenticSearchResponse)

        # Search requests counter
        assert len(fake_metrics.search_requests) == 1
        assert fake_metrics.search_requests[0] == ("fast", False)

        # Duration observed
        assert len(fake_metrics.durations) == 1
        assert fake_metrics.durations[0][1] > 0

        # Iterations observed
        assert len(fake_metrics.iterations) == 1
        assert fake_metrics.iterations[0] == ("fast", 1)

        # Results per search
        assert len(fake_metrics.results_counts) == 1
        assert fake_metrics.results_counts[0] == 2

        # Step durations recorded for known steps
        recorded_steps = {r.step for r in fake_metrics.step_durations}
        assert "plan" in recorded_steps
        assert "embed" in recorded_steps
        assert "search" in recorded_steps
        assert "compose" in recorded_steps

        # No errors
        assert len(fake_metrics.search_errors) == 0

    @pytest.mark.asyncio
    async def test_fast_mode_search_error_fallback(
        self,
        fake_metrics,
        mock_ctx,
        mock_emitter,
        mock_services,
        fast_request,
        canned_results,
    ):
        """When compile_query raises, the pipeline should produce empty results
        and map the search_error timing to the 'search' step."""
        mock_services.vector_db.compile_query = AsyncMock(
            side_effect=RuntimeError("search broke")
        )

        agent = AgenticSearchAgent(
            mock_services, mock_ctx, mock_emitter, metrics=fake_metrics
        )

        patches = self._build_patches(canned_results)
        with (
            patches["metadata_builder"],
            patches["state_builder"],
            patches["planner"],
            patches["embedder"],
            patches["complete_plan"],
            patches["composer"],
            patches["track_completion"],
            patches["build_summaries"],
        ):
            response = await agent.run("test-collection", fast_request)

        assert isinstance(response, AgenticSearchResponse)
        # Results should be empty due to search failure
        assert len(response.results) == 0

        # "search_error" timing should map to "search" step
        search_steps = [r for r in fake_metrics.step_durations if r.step == "search"]
        assert len(search_steps) >= 1

        # Pipeline still completes — requests + duration recorded
        assert len(fake_metrics.search_requests) == 1
        assert len(fake_metrics.durations) == 1
