"""Groq LLM implementation.

Fallback provider using the Groq Cloud SDK. Supports the same GPT-OSS model
as Cerebras with strict JSON schema mode and reasoning parameters.
"""

import json
import time
from typing import Any, TypeVar

from groq import AsyncGroq
from pydantic import BaseModel

from airweave.adapters.llm.base import BaseLLM
from airweave.adapters.llm.exceptions import LLMTransientError
from airweave.adapters.llm.registry import LLMModelSpec
from airweave.adapters.llm.tool_response import LLMResponse, LLMToolCall
from airweave.core.config import settings

T = TypeVar("T", bound=BaseModel)


class GroqLLM(BaseLLM):
    """Groq LLM provider with strict JSON schema mode."""

    def __init__(
        self,
        model_spec: LLMModelSpec,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the Groq LLM client with API key validation."""
        super().__init__(model_spec, max_retries=max_retries)

        api_key = settings.GROQ_API_KEY
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not configured. Set it in your environment or .env file."
            )

        try:
            self._client = AsyncGroq(api_key=api_key, timeout=self.DEFAULT_TIMEOUT)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Groq client: {e}") from e

        self._logger.debug(
            f"[GroqLLM] Initialized with model={model_spec.api_model_name}, "
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
    ) -> T:
        # Reasoning params (e.g., reasoning_effort for GPT-OSS)
        reasoning_params: dict[str, Any] = {}
        if self._model_spec.reasoning and self._model_spec.reasoning.param_name != "_noop":
            reasoning_params[self._model_spec.reasoning.param_name] = (
                self._model_spec.reasoning.param_value
            )

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
                "Groq returned empty response content",
                provider=self._name,
            )

        if response.usage:
            self._logger.debug(
                f"[GroqLLM] API call completed in {api_time:.2f}s, "
                f"tokens: prompt={response.usage.prompt_tokens}, "
                f"completion={response.usage.completion_tokens}, "
                f"total={response.usage.total_tokens}"
            )

        return self._parse_json_response(content, schema)

    def _prepare_tools_strict(self, tools: list[dict]) -> list[dict]:
        """Add strict: true and normalize tool parameter schemas for Groq.

        Groq-specific: also collapses primitive anyOf unions to string, since
        Groq only supports anyOf with object branches.
        """
        strict_tools = []
        for tool in tools:
            func = tool["function"]
            params = self._normalize_strict_schema(func["parameters"])
            self._collapse_primitive_anyof(params)
            strict_tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": func["name"],
                        "description": func.get("description", ""),
                        "strict": True,
                        "parameters": params,
                    },
                }
            )
        return strict_tools

    @staticmethod
    def _collapse_primitive_anyof(node: Any) -> None:
        """Recursively simplify anyOf with primitive branches for Groq strict mode."""
        if isinstance(node, dict):
            if "anyOf" in node and isinstance(node["anyOf"], list):
                GroqLLM._simplify_anyof_node(node)
            for v in node.values():
                GroqLLM._collapse_primitive_anyof(v)
        elif isinstance(node, list):
            for v in node:
                GroqLLM._collapse_primitive_anyof(v)

    @staticmethod
    def _simplify_anyof_node(node: dict[str, Any]) -> None:
        """Simplify a single anyOf node by collapsing primitive branches."""
        branches = node["anyOf"]
        has_object_branch = any(isinstance(b, dict) and "properties" in b for b in branches)
        if has_object_branch or len(branches) <= 1:
            return

        non_null = [b for b in branches if not (isinstance(b, dict) and b.get("type") == "null")]
        null_branches = [b for b in branches if isinstance(b, dict) and b.get("type") == "null"]

        if len(non_null) <= 1:
            return  # Simple nullable — Groq handles this

        scalar_types = {"string", "integer", "number", "boolean"}
        has_scalar = any(isinstance(b, dict) and b.get("type") in scalar_types for b in non_null)
        has_array = any(isinstance(b, dict) and b.get("type") == "array" for b in non_null)

        new_branches: list[dict[str, Any]] = []
        if has_scalar:
            new_branches.append({"type": "string"})
        if has_array:
            new_branches.append({"type": "array", "items": {"type": "string"}})
        new_branches.extend(null_branches)

        if len(new_branches) == 1:
            del node["anyOf"]
            node.update(new_branches[0])
        else:
            node["anyOf"] = new_branches

    async def _call_api_chat(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMResponse:
        """Groq tool calling (OpenAI-compatible format)."""
        converted = self._embed_thinking_in_messages(messages)
        api_messages = [{"role": "system", "content": system_prompt}, *converted]
        strict_tools = self._prepare_tools_strict(tools)

        reasoning_params: dict[str, Any] = {}
        if self._model_spec.reasoning and self._model_spec.reasoning.param_name != "_noop":
            reasoning_params[self._model_spec.reasoning.param_name] = (
                self._model_spec.reasoning.param_value
            )

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
                f"[GroqLLM] Tool call completed in {api_time:.2f}s, "
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
        """Close the Groq async client and release resources."""
        if self._client:
            await self._client.close()
            self._logger.debug("[GroqLLM] Client closed")
