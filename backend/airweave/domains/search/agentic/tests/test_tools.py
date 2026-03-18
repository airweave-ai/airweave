"""Tests for individual agentic search tools."""

import pytest

from airweave.domains.search.adapters.vector_db.fakes import FakeVectorDB
from airweave.domains.search.agentic.exceptions import ToolValidationError
from airweave.domains.search.agentic.tests.conftest import make_result, make_state
from airweave.domains.search.agentic.tools.collect import AddToResultsTool, RemoveFromResultsTool
from airweave.domains.search.agentic.tools.finish import ReturnResultsTool, ReviewResultsTool
from airweave.domains.search.agentic.tools.read import ReadTool
from airweave.domains.search.agentic.tools.search import SearchTool
from airweave.domains.search.fakes.executor import FakeSearchPlanExecutor
from airweave.domains.search.types import SearchResults

# ── Search tool ───────────────────────────────────────────────────────


class TestSearchTool:
    """Tests for SearchTool."""

    @pytest.mark.asyncio
    async def test_new_results_tracked_in_state(self) -> None:
        """New results are added to state.results."""
        r1 = make_result(entity_id="ent-1")
        r2 = make_result(entity_id="ent-2")
        executor = FakeSearchPlanExecutor()
        executor.seed_result(SearchResults(results=[r1, r2]))

        tool = SearchTool(executor=executor, user_filter=[], collection_id="col-1")
        state = make_state()
        result = await tool.execute(
            {
                "query": {"primary": "test"},
                "limit": 10,
                "offset": 0,
                "retrieval_strategy": "hybrid",
            },
            state,
            tool_call_id="tc-1",
        )

        assert result.new_count == 2
        assert "ent-1" in state.results
        assert "ent-2" in state.results

    @pytest.mark.asyncio
    async def test_duplicate_results_not_counted_as_new(self) -> None:
        """Pre-existing results → new_count excludes them."""
        r1 = make_result(entity_id="ent-1")
        r2 = make_result(entity_id="ent-2")
        executor = FakeSearchPlanExecutor()
        executor.seed_result(SearchResults(results=[r1, r2]))

        state = make_state(results={"ent-1": r1})
        tool = SearchTool(executor=executor, user_filter=[], collection_id="col-1")
        result = await tool.execute(
            {
                "query": {"primary": "test"},
                "limit": 10,
                "offset": 0,
                "retrieval_strategy": "hybrid",
            },
            state,
            tool_call_id="tc-1",
        )

        assert result.new_count == 1

    @pytest.mark.asyncio
    async def test_lineage_tracked(self) -> None:
        """Results tracked in state.results_by_tool_call_id."""
        r1 = make_result(entity_id="ent-1")
        executor = FakeSearchPlanExecutor()
        executor.seed_result(SearchResults(results=[r1]))

        state = make_state()
        tool = SearchTool(executor=executor, user_filter=[], collection_id="col-1")
        await tool.execute(
            {
                "query": {"primary": "test"},
                "limit": 10,
                "offset": 0,
                "retrieval_strategy": "hybrid",
            },
            state,
            tool_call_id="tc-1",
        )

        assert "tc-1" in state.results_by_tool_call_id
        assert len(state.results_by_tool_call_id["tc-1"]) == 1


# ── Read tool ─────────────────────────────────────────────────────────


class TestReadTool:
    """Tests for ReadTool."""

    @pytest.mark.asyncio
    async def test_entity_not_in_state_returns_not_found(self) -> None:
        """Unknown entity ID → returned in not_found."""
        tool = ReadTool(vector_db=FakeVectorDB(), collection_id="col-1")
        state = make_state()
        result = await tool.execute({"entity_ids": ["unknown"]}, state)

        assert result.not_found == ["unknown"]
        assert result.entities == []

    @pytest.mark.asyncio
    async def test_empty_entity_ids_raises_validation(self) -> None:
        """Empty entity_ids → ToolValidationError."""
        tool = ReadTool(vector_db=FakeVectorDB(), collection_id="col-1")
        state = make_state()

        with pytest.raises(ToolValidationError, match="entity_ids"):
            await tool.execute({"entity_ids": []}, state)

    @pytest.mark.asyncio
    async def test_known_entity_returns_content(self) -> None:
        """Entity in state → returned with rendered content."""
        r = make_result(entity_id="ent-1", content="Full document text.")
        vdb = FakeVectorDB()
        vdb.seed_filter_results([r])

        state = make_state(results={"ent-1": r})
        tool = ReadTool(vector_db=vdb, collection_id="col-1")
        result = await tool.execute({"entity_ids": ["ent-1"]}, state, tool_call_id="tc-1")

        assert len(result.entities) == 1
        assert result.not_found == []
        assert "tc-1" in state.reads_by_tool_call_id


# ── Collect tools ─────────────────────────────────────────────────────


class TestAddToResultsTool:
    """Tests for AddToResultsTool."""

    @pytest.mark.asyncio
    async def test_add_known_entity(self) -> None:
        """Entity in results pool → added."""
        r = make_result(entity_id="ent-1")
        state = make_state(results={"ent-1": r})
        tool = AddToResultsTool()

        result = await tool.execute({"entity_ids": ["ent-1"]}, state)

        assert result.added == ["ent-1"]
        assert result.total_collected == 1
        assert "ent-1" in state.collected_ids

    @pytest.mark.asyncio
    async def test_add_unknown_entity(self) -> None:
        """Unknown entity → not_found."""
        state = make_state()
        tool = AddToResultsTool()

        result = await tool.execute({"entity_ids": ["unknown"]}, state)

        assert result.not_found == ["unknown"]
        assert result.total_collected == 0

    @pytest.mark.asyncio
    async def test_empty_raises_validation(self) -> None:
        """Empty entity_ids → ToolValidationError."""
        tool = AddToResultsTool()
        with pytest.raises(ToolValidationError):
            await tool.execute({"entity_ids": []}, make_state())


class TestRemoveFromResultsTool:
    """Tests for RemoveFromResultsTool."""

    @pytest.mark.asyncio
    async def test_remove_all(self) -> None:
        """entity_ids=['all'] → clears all."""
        r = make_result(entity_id="ent-1")
        state = make_state(results={"ent-1": r}, collected_ids={"ent-1"})
        tool = RemoveFromResultsTool()

        result = await tool.execute({"entity_ids": ["all"]}, state)

        assert result.removed == ["all"]
        assert result.total_collected == 0
        assert len(state.collected_ids) == 0


# ── Finish tools ──────────────────────────────────────────────────────


class TestReturnResultsTool:
    """Tests for ReturnResultsTool with soft gate."""

    @pytest.mark.asyncio
    async def test_soft_gate_warns_first_time(self) -> None:
        """< 20 collected, > 100 seen → warning, not accepted."""
        results = {f"ent-{i}": make_result(entity_id=f"ent-{i}") for i in range(101)}
        collected = {f"ent-{i}" for i in range(5)}
        state = make_state(results=results, collected_ids=collected)

        tool = ReturnResultsTool()
        result = await tool.execute({}, state)

        assert not result.accepted
        assert result.warning is not None
        assert state.return_warned is True
        assert not state.should_finish

    @pytest.mark.asyncio
    async def test_soft_gate_accepts_second_time(self) -> None:
        """After warning → accepted."""
        results = {f"ent-{i}": make_result(entity_id=f"ent-{i}") for i in range(101)}
        collected = {f"ent-{i}" for i in range(5)}
        state = make_state(results=results, collected_ids=collected)
        state.return_warned = True

        tool = ReturnResultsTool()
        result = await tool.execute({}, state)

        assert result.accepted
        assert state.should_finish is True

    @pytest.mark.asyncio
    async def test_enough_collected_accepts_immediately(self) -> None:
        """≥ 20 collected → accepted without warning."""
        results = {f"ent-{i}": make_result(entity_id=f"ent-{i}") for i in range(25)}
        collected = {f"ent-{i}" for i in range(20)}
        state = make_state(results=results, collected_ids=collected)

        tool = ReturnResultsTool()
        result = await tool.execute({}, state)

        assert result.accepted
        assert state.should_finish is True


class TestReviewResultsTool:
    """Tests for ReviewResultsTool."""

    @pytest.mark.asyncio
    async def test_returns_collected_entities(self) -> None:
        """Returns rendered content for collected entities."""
        r = make_result(entity_id="ent-1")
        state = make_state(results={"ent-1": r}, collected_ids={"ent-1"})

        tool = ReviewResultsTool()
        result = await tool.execute({}, state)

        assert result.total_collected == 1
        assert len(result.entities) == 1

    @pytest.mark.asyncio
    async def test_empty_collection(self) -> None:
        """No collected entities → empty list."""
        state = make_state()

        tool = ReviewResultsTool()
        result = await tool.execute({}, state)

        assert result.total_collected == 0
        assert result.entities == []
