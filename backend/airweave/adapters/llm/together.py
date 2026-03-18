"""Together AI LLM implementation.

Uses the Together Python SDK (OpenAI-compatible) with support for Kimi K2.5
and other models hosted on Together's inference platform.

Key differences from other OpenAI-compatible providers:
- response_format uses {"type": "json_schema", "schema": ...} (no nested
  json_schema wrapper or strict flag)
- Thinking mode enabled via reasoning={"enabled": True} with temperature=1.0
- Reasoning content returned in message.reasoning field
"""

import json
import time
from typing import Any, TypeVar

from pydantic import BaseModel
from together import AsyncTogether

from airweave.adapters.llm.base import BaseLLM
from airweave.adapters.llm.exceptions import LLMTransientError
from airweave.adapters.llm.registry import LLMModelSpec
from airweave.adapters.llm.tool_response import LLMResponse, LLMToolCall
from airweave.core.config import settings

T = TypeVar("T", bound=BaseModel)


class TogetherLLM(BaseLLM):
    """Together AI LLM provider."""

    def __init__(
        self,
        model_spec: LLMModelSpec,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the Together AI LLM client with API key validation."""
        super().__init__(model_spec, max_retries=max_retries)

        api_key = settings.TOGETHER_API_KEY
        if not api_key:
            raise ValueError(
                "TOGETHER_API_KEY not configured. Set it in your environment or .env file."
            )

        try:
            self._client = AsyncTogether(api_key=api_key, timeout=self.DEFAULT_TIMEOUT)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Together client: {e}") from e

        self._logger.debug(
            f"[TogetherLLM] Initialized with model={model_spec.api_model_name}, "
            f"context_window={model_spec.context_window}, "
            f"max_output_tokens={model_spec.max_output_tokens}"
        )

    def _prepare_schema(self, schema_json: dict[str, Any]) -> dict[str, Any]:
        return self._normalize_strict_schema(schema_json)

    @staticmethod
    def _build_reasoning_kwargs(thinking: bool) -> dict[str, Any]:
        """Build reasoning kwargs for Together AI models."""
        return {"reasoning": {"enabled": thinking}}

    async def _call_api(
        self,
        prompt: str,
        schema: type[T],
        schema_json: dict[str, Any],
        system_prompt: str,
        thinking: bool = False,
    ) -> T:
        api_start = time.monotonic()
        response = await self._client.chat.completions.create(
            model=self._model_spec.api_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.6,
            response_format={
                "type": "json_schema",
                "schema": schema_json,
            },
            max_tokens=self._model_spec.max_output_tokens,
            **self._build_reasoning_kwargs(False),
        )
        api_time = time.monotonic() - api_start

        content = response.choices[0].message.content
        if not content:
            raise LLMTransientError(
                "Together AI returned empty response content",
                provider=self._name,
            )

        if response.usage:
            self._logger.debug(
                f"[TogetherLLM] API call completed in {api_time:.2f}s, "
                f"tokens: prompt={response.usage.prompt_tokens}, "
                f"completion={response.usage.completion_tokens}, "
                f"total={response.usage.total_tokens}"
            )

        return self._parse_json_response(content, schema)

    def _prepare_messages_for_api(self, messages: list[dict]) -> list[dict]:
        """Together AI: pass reasoning as a separate field on assistant messages.

        Together AI expects ``reasoning`` as a sibling of ``content`` on
        assistant messages (not embedded in content).  This enables
        preserved thinking and KV cache reuse in agentic workflows.
        """
        result = []
        for msg in messages:
            thinking = msg.get("_thinking")
            cleaned = {k: v for k, v in msg.items() if not k.startswith("_")}
            if thinking and msg.get("role") == "assistant":
                cleaned["reasoning"] = thinking
            result.append(cleaned)
        return result

    async def _call_api_chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        thinking: bool = False,
    ) -> LLMResponse:
        """Together AI tool calling (OpenAI-compatible format)."""
        converted = self._prepare_messages_for_api(messages)
        api_messages = [{"role": "system", "content": system_prompt}, *converted]

        kwargs: dict[str, Any] = {
            "model": self._model_spec.api_model_name,
            "messages": api_messages,
            "tools": tools,
            "tool_choice": "required",
            "temperature": 1.0 if thinking else 0.6,
            "max_tokens": self._model_spec.max_output_tokens,
            **self._build_reasoning_kwargs(thinking),
        }

        # Preserve thinking across turns for agentic tool-calling loops.
        # Models that don't recognize this kwarg simply ignore it.
        if thinking:
            kwargs["chat_template_kwargs"] = {"clear_thinking": False}

        api_start = time.monotonic()
        response = await self._client.chat.completions.create(**kwargs)
        api_time = time.monotonic() - api_start

        choice = response.choices[0]
        message = choice.message

        text = message.content if message.content else None
        thinking_text = getattr(message, "reasoning", None) or None

        tool_calls: list[LLMToolCall] = []
        if message.tool_calls:
            for tc in message.tool_calls:
                arguments = tc.function.arguments
                if isinstance(arguments, str):
                    arguments = json.loads(arguments)
                tool_calls.append(
                    LLMToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=arguments,
                    )
                )

        prompt_tokens = 0
        completion_tokens = 0
        if response.usage:
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            self._logger.debug(
                f"[TogetherLLM] Tool call completed in {api_time:.2f}s, "
                f"tokens: prompt={prompt_tokens}, completion={completion_tokens}"
            )

        return LLMResponse(
            text=text,
            thinking=thinking_text,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def close(self) -> None:
        """Close the Together async client and release resources."""
        if self._client:
            await self._client.close()
            self._logger.debug("[TogetherLLM] Client closed")
