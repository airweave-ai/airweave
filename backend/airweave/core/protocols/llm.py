"""LLM provider protocol.

Defines the structural typing contract that any LLM backend must satisfy.
Uses :class:`typing.Protocol` so implementations don't need to inherit.

Usage::

    from airweave.core.protocols.llm import LLMProtocol, LLMResponse


    async def search(llm: LLMProtocol) -> LLMResponse:
        return await llm.chat(messages, tools, system_prompt)
"""

from __future__ import annotations

from dataclasses import dataclass
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
class LLMResponse:
    """Response from LLM chat.

    Attributes:
        text: Model's text output (conversational text before tool calls).
            None if the model produced no text.
        thinking: Extended thinking / chain-of-thought text. None if the
            provider doesn't support it or thinking wasn't produced.
        tool_calls: Tool calls the model wants to make. Empty if end_turn.
        prompt_tokens: Input tokens used by this LLM call.
        completion_tokens: Output tokens used by this LLM call.
        cache_creation_input_tokens: Tokens written to prompt cache (Anthropic).
        cache_read_input_tokens: Tokens read from prompt cache (Anthropic).
    """

    text: str | None
    thinking: str | None
    tool_calls: list[LLMToolCall]
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


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

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMResponse:
        """Send a conversation with tools and get a response."""
        ...

    async def close(self) -> None:
        """Clean up resources (e.g., close HTTP client)."""
        ...
