"""Types for tool-calling LLM responses."""

from dataclasses import dataclass, field


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
