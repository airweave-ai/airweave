"""Anthropic LLM implementation.

Supports Claude Sonnet 4.5 and Claude Sonnet 4.6 (with extended thinking).
Uses tool_use for structured output since Anthropic doesn't support
json_schema response_format directly.

For tool-calling conversations (chat), translates between the
provider-generic OpenAI-compatible message format and Anthropic's native
tool_use/tool_result content block format.
"""

import json
import time
from typing import Any, TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel

from airweave.adapters.llm.base import BaseLLM
from airweave.adapters.llm.exceptions import LLMTransientError
from airweave.adapters.llm.registry import LLMModelSpec
from airweave.adapters.llm.tool_response import (
    LLMResponse,
    LLMToolCall,
)
from airweave.core.config import settings

T = TypeVar("T", bound=BaseModel)


class AnthropicLLM(BaseLLM):
    """Anthropic LLM provider using tool_use for structured output."""

    def __init__(
        self,
        model_spec: LLMModelSpec,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the Anthropic LLM client with API key validation."""
        super().__init__(model_spec, max_retries=max_retries)

        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not configured. Set it in your environment or .env file."
            )

        try:
            self._client = AsyncAnthropic(api_key=api_key, timeout=self.DEFAULT_TIMEOUT)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Anthropic client: {e}") from e

        self._effort = model_spec.thinking_config.effort  # e.g., "high"

        thinking_mode = f"adaptive (effort={self._effort})" if self._effort else "on-demand"

        self._logger.debug(
            f"[AnthropicLLM] Initialized model={model_spec.api_model_name}, "
            f"context={model_spec.context_window}, "
            f"max_output={model_spec.max_output_tokens}, "
            f"thinking={thinking_mode}"
        )

    def _prepare_schema(self, schema_json: dict[str, Any]) -> dict[str, Any]:
        return self._clean_schema_basic(schema_json)

    async def _call_api(
        self,
        prompt: str,
        schema: type[T],
        schema_json: dict[str, Any],
        system_prompt: str,
    ) -> T:
        tool_name = f"generate_{schema.__name__.lower()}"
        tool = {
            "name": tool_name,
            "description": f"Generate a structured {schema.__name__} response.",
            "input_schema": schema_json,
        }

        api_start = time.monotonic()
        response = await self._client.messages.create(
            model=self._model_spec.api_model_name,
            max_tokens=self._model_spec.max_output_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
        )
        api_time = time.monotonic() - api_start

        # Extract tool_use block
        tool_input = None
        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                tool_input = block.input
                break

        if tool_input is None:
            raise LLMTransientError(
                "Anthropic did not return a tool_use block",
                provider=self._name,
            )

        if response.usage:
            self._logger.debug(
                f"[AnthropicLLM] API call in {api_time:.2f}s, "
                f"tokens: in={response.usage.input_tokens}, "
                f"out={response.usage.output_tokens}"
            )

        try:
            if isinstance(tool_input, str):
                tool_input = json.loads(tool_input)
            return schema.model_validate(tool_input)
        except json.JSONDecodeError as e:
            raise LLMTransientError(
                f"Anthropic returned invalid JSON: {e}",
                provider=self._name,
                cause=e,
            ) from e
        except Exception as e:
            raise LLMTransientError(
                f"Failed to parse Anthropic response: {e}",
                provider=self._name,
                cause=e,
            ) from e

    async def _call_api_chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        thinking: bool = False,
    ) -> LLMResponse:
        """Anthropic tool calling with optional extended thinking."""
        # Convert tool defs and messages to Anthropic format
        anthropic_tools = self._convert_tool_defs(tools)
        anthropic_messages = _convert_messages_to_anthropic(messages)

        # Enable prompt caching
        cached_system = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        if anthropic_tools:
            anthropic_tools[-1]["cache_control"] = {"type": "ephemeral"}

        # Build API kwargs
        kwargs: dict[str, Any] = {
            "model": self._model_spec.api_model_name,
            "max_tokens": self._model_spec.max_output_tokens,
            "system": cached_system,
            "messages": anthropic_messages,
            "tools": anthropic_tools,
        }

        # Enable thinking when requested
        if thinking:
            kwargs["thinking"] = {"type": "adaptive"}
            if self._effort:
                kwargs["output_config"] = {"effort": self._effort}

        api_start = time.monotonic()
        response = await self._client.messages.create(**kwargs)
        api_time = time.monotonic() - api_start

        # Parse response content blocks
        thinking_parts, text_parts, tool_calls = _parse_response_blocks(response.content)

        thinking = "\n".join(thinking_parts) if thinking_parts else None
        text = "\n".join(text_parts) if text_parts else None

        prompt_tokens = 0
        completion_tokens = 0
        cache_creation = 0
        cache_read = 0
        if response.usage:
            prompt_tokens = response.usage.input_tokens
            completion_tokens = response.usage.output_tokens
            cache_creation = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
            cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
            self._logger.debug(
                f"[AnthropicLLM] Tool call in {api_time:.2f}s, "
                f"tokens: in={prompt_tokens}, out={completion_tokens}, "
                f"cache_create={cache_creation}, cache_read={cache_read}"
            )

        return LLMResponse(
            text=text,
            thinking=thinking,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
        )

    def _convert_tool_defs(self, tools: list[dict]) -> list[dict]:
        """Convert OpenAI-format tool definitions to Anthropic format."""
        anthropic_tools = []
        for tool in tools:
            func = tool["function"]
            schema = self._clean_schema_basic(func["parameters"])
            anthropic_tools.append(
                {
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": schema,
                }
            )
        return anthropic_tools

    async def close(self) -> None:
        """Close the Anthropic async client and release resources."""
        if self._client:
            await self._client.close()
            self._logger.debug("[AnthropicLLM] Client closed")


# ── Module-level helpers (reduce method complexity) ───────────────────


def _parse_response_blocks(
    content: list,
) -> tuple[list[str], list[str], list[LLMToolCall]]:
    """Extract thinking parts, text parts and tool calls from Anthropic response blocks."""
    thinking_parts: list[str] = []
    text_parts: list[str] = []
    tool_calls: list[LLMToolCall] = []

    for block in content:
        if block.type == "thinking":
            thinking_parts.append(block.thinking)
        elif block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_input = block.input
            if isinstance(tool_input, str):
                tool_input = json.loads(tool_input)
            tool_calls.append(
                LLMToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=tool_input,
                )
            )

    return thinking_parts, text_parts, tool_calls


def _convert_messages_to_anthropic(messages: list[dict]) -> list[dict]:
    """Convert generic message format to Anthropic's content block format.

    Also merges consecutive user messages since Anthropic rejects consecutive
    same-role messages.
    """
    result: list[dict] = []

    i = 0
    while i < len(messages):
        msg = messages[i]
        role = msg.get("role", "")

        if role == "user":
            content = msg.get("content", "")
            if result and result[-1]["role"] == "user":
                _merge_user_content(result[-1], content)
            else:
                result.append({"role": "user", "content": content})

        elif role == "assistant":
            blocks = _build_assistant_blocks(msg)
            if blocks:
                result.append({"role": "assistant", "content": blocks})

        elif role == "tool":
            blocks, i = _batch_tool_results(messages, i)
            if result and result[-1]["role"] == "user":
                _merge_user_content(result[-1], blocks)
            else:
                result.append({"role": "user", "content": blocks})

        i += 1

    return result


def _merge_user_content(existing_msg: dict, new_content: str | list[dict]) -> None:
    """Merge new content into an existing user message."""
    prev = existing_msg["content"]

    if isinstance(prev, str):
        prev = [{"type": "text", "text": prev}]
    if isinstance(new_content, str):
        new_content = [{"type": "text", "text": new_content}]

    existing_msg["content"] = prev + new_content


def _build_assistant_blocks(msg: dict) -> list[dict]:
    """Build Anthropic content blocks from a generic assistant message."""
    content_blocks: list[dict] = []

    # Native thinking block
    thinking = msg.get("_thinking")
    if thinking:
        content_blocks.append({"type": "thinking", "thinking": thinking})

    # Text content
    text = msg.get("content")
    if isinstance(text, str) and text:
        content_blocks.append({"type": "text", "text": text})
    elif isinstance(text, list):
        content_blocks.extend(text)

    for tc in msg.get("tool_calls", []):
        func = tc.get("function", {})
        arguments = func.get("arguments", {})
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        content_blocks.append(
            {
                "type": "tool_use",
                "id": tc["id"],
                "name": func["name"],
                "input": arguments,
            }
        )

    return content_blocks


def _batch_tool_results(messages: list[dict], start_idx: int) -> tuple[list[dict], int]:
    """Batch consecutive tool result messages into one user message."""
    i = start_idx
    blocks = [
        {
            "type": "tool_result",
            "tool_use_id": messages[i].get("tool_call_id", ""),
            "content": messages[i].get("content", ""),
        }
    ]

    while i + 1 < len(messages) and messages[i + 1].get("role") == "tool":
        i += 1
        blocks.append(
            {
                "type": "tool_result",
                "tool_use_id": messages[i].get("tool_call_id", ""),
                "content": messages[i].get("content", ""),
            }
        )

    return blocks, i
