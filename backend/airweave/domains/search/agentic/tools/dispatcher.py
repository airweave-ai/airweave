"""Tool call dispatcher — routes LLM tool calls to handlers with error handling.

All tool errors are caught and converted to ToolError subclasses.
The agent loop catches ToolError and returns the message to the LLM,
allowing it to self-correct.
"""

from __future__ import annotations

from typing import Any, Protocol, Union

from pydantic import ValidationError

from airweave.core.protocols.llm import LLMToolCall
from airweave.domains.search.agentic.exceptions import (
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    ToolValidationError,
)
from airweave.domains.search.agentic.state import AgentState
from airweave.domains.search.agentic.tools.types import (
    CollectToolResult,
    CountToolResult,
    FinishToolResult,
    NavigateToolResult,
    ReadToolResult,
    ReviewToolResult,
    SearchToolResult,
)

ToolResult = Union[
    SearchToolResult,
    ReadToolResult,
    CollectToolResult,
    CountToolResult,
    NavigateToolResult,
    ReviewToolResult,
    FinishToolResult,
]


class Tool(Protocol):
    """Protocol for a tool that can be dispatched."""

    async def execute(
        self,
        arguments: dict[str, Any],
        state: AgentState,
        tool_call_id: str = "",
    ) -> ToolResult:
        """Execute the tool with given arguments and state."""
        ...


class ToolDispatcher:
    """Routes tool calls to the appropriate handler with error handling.

    All exceptions are caught and converted:
    - ToolError subclasses pass through (already typed)
    - Pydantic ValidationError → ToolValidationError
    - Any other exception → ToolExecutionError
    """

    def __init__(self, tools: dict[str, Tool]) -> None:
        """Initialize with a mapping of tool_name -> tool instance."""
        self._tools = tools

    @property
    def tool_names(self) -> list[str]:
        """Available tool names."""
        return sorted(self._tools.keys())

    async def dispatch(
        self,
        tc: LLMToolCall,
        state: AgentState,
    ) -> ToolResult:
        """Dispatch a tool call to the appropriate handler.

        Raises:
            ToolNotFoundError: If the tool name is not registered.
            ToolValidationError: If the LLM arguments fail validation.
            ToolExecutionError: If the tool execution fails.
        """
        tool = self._tools.get(tc.name)
        if not tool:
            raise ToolNotFoundError(
                f"Unknown tool '{tc.name}'. Available tools: {', '.join(self.tool_names)}"
            )
        try:
            return await tool.execute(tc.arguments, state, tool_call_id=tc.id)
        except ToolError:
            raise
        except ValidationError as e:
            raise ToolValidationError(f"Invalid arguments for '{tc.name}': {e}") from e
        except Exception as e:
            raise ToolExecutionError(f"Tool '{tc.name}' failed: {e}") from e
