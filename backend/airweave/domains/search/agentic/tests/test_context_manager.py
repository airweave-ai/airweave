"""Tests for ContextManager — budget, fit, and compress."""

from airweave.domains.search.agentic.context_manager import (
    _format_read_older,
    _format_read_previous,
    _format_search_older,
    _format_search_previous,
)
from airweave.domains.search.agentic.tests.conftest import (
    make_context_mgr,
    make_rendered_result,
    make_result,
    make_state,
)
from airweave.domains.search.agentic.tools.types import (
    CollectToolResult,
    ReadToolResult,
    SearchToolResult,
    ToolErrorResult,
)

# ── Budget calculation ────────────────────────────────────────────────


class TestBudget:
    """Tests for budget calculation properties."""

    def test_fresh_conversation_has_large_budget(self) -> None:
        cm = make_context_mgr(context_window=100_000)
        messages = [{"role": "user", "content": "test"}]
        assert cm.available_budget(messages) > 50_000

    def test_thinking_enabled_reduces_input_budget(self) -> None:
        cm_think = make_context_mgr(thinking_enabled=True, max_output_tokens=40_000)
        cm_no = make_context_mgr(thinking_enabled=False, max_output_tokens=40_000)
        assert cm_think.input_budget < cm_no.input_budget

    def test_check_budget_false_when_exhausted(self) -> None:
        cm = make_context_mgr(context_window=500, max_output_tokens=100)
        messages = [{"role": "user", "content": "x" * 4000}]
        assert cm.check_budget(messages) is False

    def test_check_budget_true_when_healthy(self) -> None:
        cm = make_context_mgr(context_window=100_000)
        messages = [{"role": "user", "content": "test"}]
        assert cm.check_budget(messages) is True

    def test_budget_decreases_as_messages_grow(self) -> None:
        cm = make_context_mgr()
        budget_empty = cm.available_budget([])
        budget_with = cm.available_budget([{"role": "user", "content": "x" * 1000}])
        assert budget_with < budget_empty


# ── Fit tool results ──────────────────────────────────────────────────


class TestFitToolResult:
    """Tests for fitting tool results into budget."""

    def test_fit_search_all_fit(self) -> None:
        cm = make_context_mgr(context_window=100_000)
        summaries = [make_rendered_result(f"ent-{i}") for i in range(5)]
        result = SearchToolResult(summaries=summaries, new_count=5)

        content = cm.fit_tool_result(result, [])

        for s in summaries:
            assert s.text in content
        assert "not shown" not in content

    def test_fit_search_truncated(self) -> None:
        cm = make_context_mgr(context_window=800, max_output_tokens=100)
        summaries = [make_rendered_result(f"ent-{i}", text="x" * 200) for i in range(10)]
        result = SearchToolResult(summaries=summaries, new_count=10)

        content = cm.fit_tool_result(result, [])

        assert "not shown" in content

    def test_fit_search_empty(self) -> None:
        cm = make_context_mgr()
        result = SearchToolResult(summaries=[], new_count=0)

        content = cm.fit_tool_result(result, [])

        assert "No results found" in content

    def test_fit_search_pagination_warning(self) -> None:
        cm = make_context_mgr()
        summaries = [make_rendered_result(f"ent-{i}") for i in range(10)]
        result = SearchToolResult(
            summaries=summaries,
            new_count=10,
            requested_limit=10,
            requested_offset=0,
        )

        content = cm.fit_tool_result(result, [])

        assert "Results hit the limit" in content
        assert "offset=10" in content

    def test_fit_read_triage_nudge(self) -> None:
        cm = make_context_mgr()
        entities = [make_rendered_result("ent-1", text="Full content here.")]
        result = ReadToolResult(entities=entities, not_found=[], read_entity_ids=["ent-1"])

        content = cm.fit_tool_result(result, [])

        assert "Entities read:" in content
        assert "add_to_results" in content

    def test_fit_collect_always_fits(self) -> None:
        cm = make_context_mgr(context_window=500, max_output_tokens=100)
        result = CollectToolResult(added=["ent-1"], total_collected=1)

        content = cm.fit_tool_result(result, [])

        assert "Added 1" in content

    def test_fit_error_always_fits(self) -> None:
        cm = make_context_mgr(context_window=500, max_output_tokens=100)
        result = ToolErrorResult(error="Something went wrong")

        content = cm.fit_tool_result(result, [])

        assert "Something went wrong" in content


# ── Compress history ──────────────────────────────────────────────────


class TestCompressHistory:
    """Tests for 3-tier context compression."""

    def test_current_iteration_untouched(self) -> None:
        cm = make_context_mgr()
        r = make_result(entity_id="ent-1")
        state = make_state(results={"ent-1": r})
        state.results_by_tool_call_id["tc-1"] = [r]

        messages = [
            {"role": "tool", "tool_call_id": "tc-1", "_tool_name": "search", "content": "full"},
        ]

        result = cm.compress_history(
            messages,
            state,
            current_search_ids={"tc-1"},
            current_read_ids=set(),
            previous_search_ids=set(),
            previous_read_ids=set(),
        )

        assert result[0]["content"] == "full"

    def test_previous_search_compressed(self) -> None:
        cm = make_context_mgr()
        r = make_result(entity_id="ent-1", name="Doc A")
        state = make_state(results={"ent-1": r})
        state.results_by_tool_call_id["tc-old"] = [r]

        messages = [
            {"role": "tool", "tool_call_id": "tc-old", "_tool_name": "search", "content": "full"},
        ]

        result = cm.compress_history(
            messages,
            state,
            current_search_ids=set(),
            current_read_ids=set(),
            previous_search_ids={"tc-old"},
            previous_read_ids=set(),
        )

        assert "IDs only" in result[0]["content"]
        assert "Doc A" in result[0]["content"]

    def test_older_search_compressed_to_oneliner(self) -> None:
        cm = make_context_mgr()
        r = make_result(entity_id="ent-1")
        state = make_state(results={"ent-1": r})
        state.results_by_tool_call_id["tc-old"] = [r]

        messages = [
            {"role": "tool", "tool_call_id": "tc-old", "_tool_name": "search", "content": "full"},
        ]

        result = cm.compress_history(
            messages,
            state,
            current_search_ids=set(),
            current_read_ids=set(),
            previous_search_ids=set(),
            previous_read_ids=set(),
        )

        assert "*[Searched:" in result[0]["content"]

    def test_no_compressible_messages_unchanged(self) -> None:
        cm = make_context_mgr()
        state = make_state()

        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]

        result = cm.compress_history(
            messages,
            state,
            current_search_ids=set(),
            current_read_ids=set(),
            previous_search_ids=set(),
            previous_read_ids=set(),
        )

        assert result is messages  # same object, no copy needed

    def test_does_not_mutate_input(self) -> None:
        cm = make_context_mgr()
        r = make_result(entity_id="ent-1")
        state = make_state(results={"ent-1": r})
        state.results_by_tool_call_id["tc-old"] = [r]

        messages = [
            {"role": "tool", "tool_call_id": "tc-old", "_tool_name": "search", "content": "full"},
        ]
        original_content = messages[0]["content"]

        cm.compress_history(
            messages,
            state,
            current_search_ids=set(),
            current_read_ids=set(),
            previous_search_ids=set(),
            previous_read_ids=set(),
        )

        assert messages[0]["content"] == original_content


# ── Compression formatters ────────────────────────────────────────────


class TestCompressionFormatters:
    """Tests for the standalone formatting functions."""

    def test_search_previous_format(self) -> None:
        r = make_result(entity_id="ent-1", name="Doc A", score=0.95)
        result = _format_search_previous([r])
        assert "1 search results" in result
        assert "`ent-1`" in result
        assert "Doc A" in result

    def test_search_older_format(self) -> None:
        r = make_result()
        result = _format_search_older([r])
        assert "*[Searched: 1 results returned]*" == result

    def test_read_previous_format(self) -> None:
        r = make_result(entity_id="ent-1", name="Doc A")
        result = _format_read_previous([r])
        assert "Read 1 entities" in result
        assert "metadata only" in result

    def test_read_older_format(self) -> None:
        r = make_result()
        result = _format_read_older([r])
        assert "*[Read 1 entities]*" == result

    def test_empty_results(self) -> None:
        assert "No results found" in _format_search_previous([])
        assert "No results found" in _format_search_older([])
        assert "*[Read: no results]*" == _format_read_previous([])
        assert "*[Read: no results]*" == _format_read_older([])
