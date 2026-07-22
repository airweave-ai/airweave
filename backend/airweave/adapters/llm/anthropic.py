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

from anthropic import AsyncAnthropic, AsyncAnthropicBedrock
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
        """Initialize the Anthropic LLM client (direct API or AWS Bedrock)."""
        super().__init__(model_spec, max_retries=max_retries)

        # Bedrock mode: talk to Claude through AWS Bedrock instead of the direct
        # Anthropic API. AWS credentials come from the botocore default chain;
        # the model id is overridden with the Bedrock inference-profile id.
        if settings.ANTHROPIC_USE_BEDROCK:
            model = settings.AWS_BEDROCK_MODEL
            if not model:
                raise ValueError(
                    "ANTHROPIC_USE_BEDROCK is true but AWS_BEDROCK_MODEL is not set. "
                    "Set it to the Bedrock model / inference-profile id "
                    "(e.g. 'us.anthropic.claude-sonnet-4-6')."
                )
            self._model_name = model
            region = settings.BEDROCK_AWS_REGION or settings.STORAGE_AWS_REGION
            # Prefer explicit static IAM keys when configured; otherwise let the
            # SDK resolve credentials via the botocore chain (AWS_PROFILE / SSO).
            bedrock_kwargs: dict[str, Any] = {
                "aws_region": region,
                "timeout": self.DEFAULT_TIMEOUT,
            }
            if settings.AWS_BEDROCK_ACCESS_ID and settings.AWS_BEDROCK_SECRET:
                bedrock_kwargs["aws_access_key"] = settings.AWS_BEDROCK_ACCESS_ID
                bedrock_kwargs["aws_secret_key"] = settings.AWS_BEDROCK_SECRET
            try:
                self._client = AsyncAnthropicBedrock(**bedrock_kwargs)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Anthropic Bedrock client: {e}") from e
        else:
            api_key = settings.ANTHROPIC_API_KEY
            if not api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY not configured. Set it in your environment or .env file."
                )
            self._model_name = model_spec.api_model_name
            try:
                self._client = AsyncAnthropic(api_key=api_key, timeout=self.DEFAULT_TIMEOUT)
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Anthropic client: {e}") from e

        self._effort = model_spec.thinking_config.effort  # e.g., "high"

        thinking_mode = f"adaptive (effort={self._effort})" if self._effort else "on-demand"

        self._logger.debug(
            f"[AnthropicLLM] Initialized model={self._model_name}, "
            f"bedrock={settings.ANTHROPIC_USE_BEDROCK}, "
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
        thinking: bool = False,
    ) -> T:
        tool_name = f"generate_{schema.__name__.lower()}"
        tool = {
            "name": tool_name,
            "description": f"Generate a structured {schema.__name__} response.",
            "input_schema": schema_json,
        }

        api_start = time.monotonic()
        response = await self._client.messages.create(  # type: ignore[call-overload]
            model=self._model_name,
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
        max_tokens: int | None = None,
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
            "model": self._model_name,
            "max_tokens": max_tokens or self._model_spec.max_output_tokens,
            "system": cached_system,
            "messages": anthropic_messages,
            "tools": anthropic_tools,
        }

        # Sonnet 4.6 defaults to adaptive thinking when the parameter is
        # omitted — explicitly disable when not requested.
        if thinking:
            kwargs["thinking"] = {"type": "adaptive"}
            if self._effort:
                kwargs["output_config"] = {"effort": self._effort}
        else:
            kwargs["thinking"] = {"type": "disabled"}

        api_start = time.monotonic()
        response = await self._client.messages.create(**kwargs)
        api_time = time.monotonic() - api_start

        # Parse response content blocks
        thinking_parts, text_parts, tool_calls, thinking_signature = _parse_response_blocks(
            response.content
        )

        thinking_text = "\n".join(thinking_parts) if thinking_parts else None
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
            thinking=thinking_text,
            tool_calls=tool_calls,
            thinking_signature=thinking_signature,
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
) -> tuple[list[str], list[str], list[LLMToolCall], str | None]:
    """Extract thinking parts, text parts, tool calls, and thinking signature.

    Returns the signature from the *last* thinking block so it can be sent
    back in multi-turn conversations (Anthropic requires it).
    """
    thinking_parts: list[str] = []
    text_parts: list[str] = []
    tool_calls: list[LLMToolCall] = []
    thinking_signature: str | None = None

    for block in content:
        if block.type == "thinking":
            thinking_parts.append(block.thinking)
            sig = getattr(block, "signature", None)
            if sig:
                thinking_signature = sig
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

    return thinking_parts, text_parts, tool_calls, thinking_signature


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

    # Native thinking block — only include if we have the Anthropic signature.
    # Without a signature Anthropic rejects the request (HTTP 400).  This
    # happens on cross-provider fallback (e.g. Together → Anthropic) where
    # the reasoning text came from a non-Anthropic model.
    thinking = msg.get("_thinking")
    thinking_signature = msg.get("_thinking_signature")
    if thinking and thinking_signature:
        content_blocks.append(
            {"type": "thinking", "thinking": thinking, "signature": thinking_signature}
        )

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
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                arguments = {}
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
