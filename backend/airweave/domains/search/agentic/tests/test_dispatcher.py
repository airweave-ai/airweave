"""Tests for ToolDispatcher — exception handling and routing."""

from typing import Any

import pytest
from pydantic import ValidationError

from airweave.core.protocols.llm import LLMToolCall
from airweave.domains.search.agentic.exceptions import (
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
)
from airweave.domains.search.agentic.state import AgentState
from airweave.domains.search.agentic.tests.conftest import make_state
from airweave.domains.search.agentic.tools.dispatcher import ToolDispatcher
from airweave.domains.search.agentic.tools.types import CollectToolResult


class _FakeTool:
    """Minimal fake tool for dispatcher tests."""

    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple] = []

    async def execute(self, arguments: dict, state: AgentState, tool_call_id: str = "") -> Any:
        """Execute and return result or raise error."""
        self.calls.append(("execute", arguments, state, tool_call_id))
        if self._error:
            raise self._error
        return self._result


class TestDispatcher:
    """Tests for ToolDispatcher."""

    @pytest.mark.asyncio
    async def test_dispatches_to_correct_tool(self) -> None:
        """Tool call routes to the registered tool by name."""
        expected = CollectToolResult(added=["ent-1"], total_collected=1)
        tool = _FakeTool(result=expected)
        dispatcher = ToolDispatcher({"my_tool": tool})
        state = make_state()
        tc = LLMToolCall(id="tc-1", name="my_tool", arguments={"x": 1})

        result = await dispatcher.dispatch(tc, state)

        assert result == expected
        assert len(tool.calls) == 1

    @pytest.mark.asyncio
    async def test_unknown_tool_raises_not_found(self) -> None:
        """Unknown tool name → ToolNotFoundError."""
        dispatcher = ToolDispatcher({})
        state = make_state()
        tc = LLMToolCall(id="tc-1", name="nonexistent", arguments={})

        with pytest.raises(ToolNotFoundError, match="Unknown tool"):
            await dispatcher.dispatch(tc, state)

    @pytest.mark.asyncio
    async def test_validation_error_wrapped(self) -> None:
        """Pydantic ValidationError from tool → ToolValidationError."""
        # Create a real ValidationError
        from pydantic import BaseModel

        class Dummy(BaseModel):
            x: int

        try:
            Dummy(x="not_an_int")  # type: ignore[arg-type]
        except ValidationError as ve:
            error = ve

        tool = _FakeTool(error=error)
        dispatcher = ToolDispatcher({"bad_tool": tool})
        state = make_state()
        tc = LLMToolCall(id="tc-1", name="bad_tool", arguments={})

        with pytest.raises(ToolValidationError, match="Invalid arguments"):
            await dispatcher.dispatch(tc, state)

    @pytest.mark.asyncio
    async def test_tool_error_passes_through(self) -> None:
        """ToolValidationError from tool → passes through, not double-wrapped."""
        tool = _FakeTool(error=ToolValidationError("entity_ids required"))
        dispatcher = ToolDispatcher({"strict_tool": tool})
        state = make_state()
        tc = LLMToolCall(id="tc-1", name="strict_tool", arguments={})

        with pytest.raises(ToolValidationError, match="entity_ids required"):
            await dispatcher.dispatch(tc, state)

    @pytest.mark.asyncio
    async def test_unexpected_error_wrapped(self) -> None:
        """RuntimeError from tool → ToolExecutionError."""
        tool = _FakeTool(error=RuntimeError("db connection lost"))
        dispatcher = ToolDispatcher({"broken_tool": tool})
        state = make_state()
        tc = LLMToolCall(id="tc-1", name="broken_tool", arguments={})

        with pytest.raises(ToolExecutionError, match="failed"):
            await dispatcher.dispatch(tc, state)

    def test_tool_names_property(self) -> None:
        """tool_names returns sorted list of registered names."""
        dispatcher = ToolDispatcher({"b_tool": _FakeTool(), "a_tool": _FakeTool()})
        assert dispatcher.tool_names == ["a_tool", "b_tool"]
