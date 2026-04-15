"""Mistral LLM implementation.

Uses the native mistralai SDK for chat completions with json_schema
structured output and OpenAI-compatible tool/function calling.

Supports reasoning/thinking via two mechanisms:
- Magistral models: native thinking (always-on), returned as ThinkChunk content blocks
- Mistral Small 4: adjustable reasoning via reasoning_effort parameter
"""

import json
import time
from typing import Any, TypeVar

from mistralai import Mistral
from mistralai.models.jsonschema import JSONSchema
from mistralai.models.responseformat import ResponseFormat
from mistralai.models.textchunk import TextChunk
from mistralai.models.thinkchunk import ThinkChunk
from pydantic import BaseModel

from airweave.adapters.llm.base import BaseLLM
from airweave.adapters.llm.exceptions import LLMTransientError
from airweave.adapters.llm.registry import LLMModelSpec
from airweave.adapters.llm.tool_response import LLMResponse, LLMToolCall
from airweave.core.config import settings

T = TypeVar("T", bound=BaseModel)


class MistralLLM(BaseLLM):
    """Mistral LLM provider with json_schema structured output and tool calling."""

    def __init__(
        self,
        model_spec: LLMModelSpec,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the Mistral LLM client with API key validation."""
        super().__init__(model_spec, max_retries=max_retries)

        api_key = settings.MISTRAL_API_KEY
        if not api_key:
            raise ValueError(
                "MISTRAL_API_KEY not configured. Set it in your environment or .env file."
            )

        try:
            self._client = Mistral(api_key=api_key)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Mistral client: {e}") from e

        self._logger.debug(
            f"[MistralLLM] Initialized with model={model_spec.api_model_name}, "
            f"context_window={model_spec.context_window}, "
            f"max_output_tokens={model_spec.max_output_tokens}"
        )

    def _prepare_schema(self, schema_json: dict[str, Any]) -> dict[str, Any]:
        return self._normalize_strict_schema(schema_json)

    async def _call_api(
        self,
        prompt: str,
        schema: type[T],
        schema_json: dict[str, Any],
        system_prompt: str,
        thinking: bool = False,
    ) -> T:
        api_start = time.monotonic()
        response = await self._client.chat.complete_async(
            model=self._model_spec.api_model_name,
            messages=[  # type: ignore[arg-type]
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format=ResponseFormat(  # type: ignore[arg-type]
                type="json_schema",
                json_schema=JSONSchema(
                    name=schema.__name__.lower(),
                    strict=True,
                    schema_definition=schema_json,
                ),
            ),
            max_tokens=self._model_spec.max_output_tokens,
        )
        api_time = time.monotonic() - api_start

        raw_content = response.choices[0].message.content
        if not raw_content:
            raise LLMTransientError(
                "Mistral returned empty response content",
                provider=self._name,
            )

        # Extract text, ignoring thinking chunks for structured output
        content = _extract_text(raw_content)

        if response.usage:
            self._logger.debug(
                f"[MistralLLM] API call completed in {api_time:.2f}s, "
                f"tokens: prompt={response.usage.prompt_tokens}, "
                f"completion={response.usage.completion_tokens}, "
                f"total={response.usage.total_tokens}"
            )

        return self._parse_json_response(content, schema)

    async def _call_api_chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        thinking: bool = False,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Mistral tool calling with OpenAI-compatible format."""
        converted = self._prepare_messages_for_api(messages)
        api_messages = [{"role": "system", "content": system_prompt}, *converted]

        # Mistral uses OpenAI-compatible tool definitions directly
        strict_tools = self._prepare_tools_strict(tools)

        # Build reasoning params based on thinking config
        reasoning_params: dict[str, Any] = {}
        tc = self._model_spec.thinking_config
        if tc and tc.param_name == "reasoning_effort":
            reasoning_params[tc.param_name] = "high" if thinking else "none"

        api_start = time.monotonic()
        response = await self._client.chat.complete_async(
            model=self._model_spec.api_model_name,
            messages=api_messages,  # type: ignore[arg-type]
            tools=strict_tools,  # type: ignore[arg-type]
            tool_choice="any",
            temperature=0.3,
            max_tokens=max_tokens or self._model_spec.max_output_tokens,
            **reasoning_params,
        )
        api_time = time.monotonic() - api_start

        choice = response.choices[0]
        message = choice.message

        # Parse content — may contain thinking chunks for reasoning models
        raw_content = message.content
        text, thinking_text = _extract_text_and_thinking(raw_content)

        # Only surface thinking when the caller requested it
        if not thinking:
            thinking_text = None

        tool_calls: list[LLMToolCall] = []
        if message.tool_calls:
            for tc_item in message.tool_calls:
                arguments = tc_item.function.arguments
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                tool_calls.append(
                    LLMToolCall(
                        id=tc_item.id or "",
                        name=tc_item.function.name,
                        arguments=arguments,
                    )
                )

        prompt_tokens = 0
        completion_tokens = 0
        if response.usage:
            prompt_tokens = response.usage.prompt_tokens or 0
            completion_tokens = response.usage.completion_tokens or 0
            self._logger.debug(
                f"[MistralLLM] Tool call completed in {api_time:.2f}s, "
                f"tokens: prompt={prompt_tokens}, completion={completion_tokens}"
            )

        return LLMResponse(
            text=text,
            thinking=thinking_text,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def _prepare_tools_strict(self, tools: list[dict]) -> list[dict]:
        """Normalize tool parameter schemas for Mistral's json_schema strict mode."""
        strict_tools = []
        for tool in tools:
            func = tool["function"]
            params = self._normalize_strict_schema(func["parameters"])
            strict_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "parameters": params,
                    },
                }
            )
        return strict_tools

    async def close(self) -> None:
        """Close the Mistral client and release resources."""
        if self._client:
            # Mistral SDK uses context manager protocol (__aexit__) for cleanup
            await self._client.__aexit__(None, None, None)
            self._logger.debug("[MistralLLM] Client closed")


# ── Module-level helpers ───────────────────────────────────────────────


def _extract_text(raw_content: Any) -> str:
    """Extract text from content, which may be a string or list of typed chunks."""
    if isinstance(raw_content, str):
        return raw_content

    # List of content chunks — collect only text chunks
    text_parts: list[str] = []
    if isinstance(raw_content, list):
        for chunk in raw_content:
            if isinstance(chunk, TextChunk):
                text_parts.append(chunk.text)

    return "\n".join(text_parts) if text_parts else str(raw_content)


def _extract_text_and_thinking(raw_content: Any) -> tuple[str | None, str | None]:
    """Extract text and thinking from content chunks.

    Mistral reasoning models (Magistral, Mistral Small 4 with reasoning_effort)
    return ThinkChunk blocks alongside TextChunk blocks in the content array.
    ThinkChunk.thinking is a list of TextChunk/ReferenceChunk sub-items.
    """
    if raw_content is None:
        return None, None

    if isinstance(raw_content, str):
        return raw_content if raw_content else None, None

    text_parts: list[str] = []
    thinking_parts: list[str] = []

    if isinstance(raw_content, list):
        for chunk in raw_content:
            if isinstance(chunk, ThinkChunk):
                # ThinkChunk.thinking is List[Union[TextChunk, ReferenceChunk]]
                for sub in chunk.thinking:
                    if isinstance(sub, TextChunk):
                        thinking_parts.append(sub.text)
            elif isinstance(chunk, TextChunk):
                text_parts.append(chunk.text)

    text = "\n".join(text_parts) if text_parts else None
    thinking_text = "\n".join(thinking_parts) if thinking_parts else None
    return text, thinking_text
