"""LLM provider protocol.

Defines the structural typing contract that any LLM backend must satisfy.
Uses :class:`typing.Protocol` so implementations don't need to inherit.

Usage::

    from airweave.core.protocols.llm import LLMProtocol, LLMToolResponse


    async def search(llm: LLMProtocol) -> LLMToolResponse:
        return await llm.create_with_tools(messages, tools, system_prompt)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMToolCall:
    """A tool call from the model."""

    id: str
    name: str
    arguments: dict


@dataclass
class LLMToolResponse:
    """Response from create_with_tools.

    Attributes:
        text: Model's text output (reasoning before tool calls). None if no text.
        thinking: Extended thinking / chain-of-thought text (Anthropic only). None
            if the provider doesn't support it or thinking wasn't produced.
        tool_calls: Tool calls the model wants to make. Empty if end_turn.
        stop_reason: Why the model stopped: "tool_use", "end_turn", "stop", etc.
        usage: Token usage dict with at least "prompt_tokens" and "completion_tokens".
    """

    text: str | None
    thinking: str | None
    tool_calls: list[LLMToolCall]
    stop_reason: str
    usage: dict = field(default_factory=dict)


@runtime_checkable
class LLMProtocol(Protocol):
    """Structural protocol for LLM providers.

    Any class that implements these methods with matching signatures is
    considered a valid LLM provider -- no subclassing required.
    """

    @property
    def model_spec(self) -> Any:
        """Get the model specification."""
        ...

    async def structured_output(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str,
    ) -> T:
        """Generate structured output matching the schema."""
        ...

    async def create_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMToolResponse:
        """Send a conversation with tools and get a response."""
        ...

    async def close(self) -> None:
        """Clean up resources (e.g., close HTTP client)."""
        ...
