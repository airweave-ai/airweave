"""Cerebras LLM implementation.

Uses the Cerebras Cloud SDK for structured output generation with reasoning models.
"""

import json
import time
from typing import Any, TypeVar

from cerebras.cloud.sdk import AsyncCerebras
from pydantic import BaseModel

from airweave.adapters.llm.base import BaseLLM
from airweave.adapters.llm.exceptions import LLMTransientError
from airweave.adapters.llm.registry import LLMModelSpec
from airweave.adapters.llm.tool_response import LLMResponse, LLMToolCall
from airweave.core.config import settings

T = TypeVar("T", bound=BaseModel)


class CerebrasLLM(BaseLLM):
    """Cerebras LLM provider with strict JSON schema mode."""

    def __init__(
        self,
        model_spec: LLMModelSpec,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the Cerebras LLM client with API key validation."""
        super().__init__(model_spec, max_retries=max_retries)

        api_key = settings.CEREBRAS_API_KEY
        if not api_key:
            raise ValueError(
                "CEREBRAS_API_KEY not configured. Set it in your environment or .env file."
            )

        try:
            self._client = AsyncCerebras(api_key=api_key, timeout=self.DEFAULT_TIMEOUT)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Cerebras client: {e}") from e

        # GLM/Qwen models use <think> tags; GPT-OSS prepends reasoning raw.
        self._uses_think_tags = model_spec.thinking_config.param_name == "disable_reasoning"

        self._logger.debug(
            f"[CerebrasLLM] Initialized with model={model_spec.api_model_name}, "
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
        # Reasoning params from model spec
        tc = self._model_spec.thinking_config
        reasoning_params = {tc.param_name: tc.param_value}

        api_start = time.monotonic()
        response = await self._client.chat.completions.create(
            model=self._model_spec.api_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__.lower(),
                    "strict": True,
                    "schema": schema_json,
                },
            },
            max_completion_tokens=self._model_spec.max_output_tokens,
            **reasoning_params,
        )
        api_time = time.monotonic() - api_start

        content = response.choices[0].message.content
        if not content:
            raise LLMTransientError(
                "Cerebras returned empty response content",
                provider=self._name,
            )

        if response.usage:
            self._logger.debug(
                f"[CerebrasLLM] API call completed in {api_time:.2f}s, "
                f"tokens: prompt={response.usage.prompt_tokens}, "
                f"completion={response.usage.completion_tokens}, "
                f"total={response.usage.total_tokens}"
            )

        return self._parse_json_response(content, schema)

    def _prepare_tools_strict(self, tools: list[dict]) -> list[dict]:
        """Add strict: true and normalize tool parameter schemas for Cerebras."""
        strict_tools = []
        for tool in tools:
            func = tool["function"]
            strict_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "strict": True,
                        "parameters": self._normalize_strict_schema(func["parameters"]),
                    },
                }
            )
        return strict_tools

    def _prepare_messages_for_api(self, messages: list[dict]) -> list[dict]:
        """Cerebras: embed thinking in content for multi-turn reasoning continuity.

        GPT-OSS models: prepend reasoning directly before the answer.
        GLM / Qwen models: wrap reasoning in ``<think>...</think>`` tags.
        """
        result = []
        for msg in messages:
            thinking = msg.get("_thinking")
            cleaned = {k: v for k, v in msg.items() if not k.startswith("_")}
            if thinking and msg.get("role") == "assistant":
                content = cleaned.get("content") or ""
                if self._uses_think_tags:
                    cleaned["content"] = f"<think>{thinking}</think>\n{content}"
                else:
                    cleaned["content"] = f"{thinking}\n{content}" if content else thinking
            result.append(cleaned)
        return result

    def _build_reasoning_params(self, thinking: bool) -> dict[str, Any]:
        """Build provider-specific reasoning params from the thinking flag."""
        tc = self._model_spec.thinking_config
        if tc.param_name == "reasoning_effort":
            # GPT-OSS: reasoning_effort="high" when thinking, "low" when not
            return {tc.param_name: "high" if thinking else "low"}
        if tc.param_name == "disable_reasoning":
            # GLM: disable_reasoning=False when thinking, True when not
            return {tc.param_name: not thinking}
        return {}

    async def _call_api_chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
        thinking: bool = False,
    ) -> LLMResponse:
        """Cerebras tool calling (OpenAI-compatible format)."""
        converted = self._prepare_messages_for_api(messages)
        api_messages = [{"role": "system", "content": system_prompt}, *converted]
        strict_tools = self._prepare_tools_strict(tools)

        reasoning_params = self._build_reasoning_params(thinking)

        api_start = time.monotonic()
        response = await self._client.chat.completions.create(
            model=self._model_spec.api_model_name,
            messages=api_messages,
            tools=strict_tools,
            tool_choice="required",
            temperature=0.3,
            max_completion_tokens=self._model_spec.max_output_tokens,
            **reasoning_params,
        )
        api_time = time.monotonic() - api_start

        choice = response.choices[0]
        message = choice.message

        text = message.content if message.content else None
        thinking = getattr(message, "reasoning", None) or None

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
                f"[CerebrasLLM] Tool call completed in {api_time:.2f}s, "
                f"tokens: prompt={prompt_tokens}, completion={completion_tokens}"
            )

        return LLMResponse(
            text=text,
            thinking=thinking,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def close(self) -> None:
        """Close the Cerebras async client and release resources."""
        if self._client:
            await self._client.close()
            self._logger.debug("[CerebrasLLM] Client closed")
