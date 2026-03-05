"""Groq LLM implementation for agentic search.

Fallback provider using the Groq Cloud SDK. Supports the same GPT-OSS model
as Cerebras with strict JSON schema mode and reasoning parameters.
"""

import time
from typing import Any, TypeVar

from groq import AsyncGroq
from pydantic import BaseModel

from airweave.core.config import settings
from airweave.search.agentic_search.external.llm.base import BaseLLM
from airweave.search.agentic_search.external.llm.registry import LLMModelSpec
from airweave.search.agentic_search.external.tokenizer import AgenticSearchTokenizerInterface

T = TypeVar("T", bound=BaseModel)


class GroqLLM(BaseLLM):
    """Groq LLM provider with strict JSON schema mode."""

    def __init__(
        self,
        model_spec: LLMModelSpec,
        tokenizer: AgenticSearchTokenizerInterface,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the Groq LLM client with API key validation."""
        super().__init__(model_spec, tokenizer, max_retries=max_retries)

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
            raise TimeoutError("Groq returned empty response content (retryable)")

        if response.usage:
            self._logger.debug(
                f"[GroqLLM] API call completed in {api_time:.2f}s, "
                f"tokens: prompt={response.usage.prompt_tokens}, "
                f"completion={response.usage.completion_tokens}, "
                f"total={response.usage.total_tokens}"
            )

        return self._parse_json_response(content, schema, "Groq")

    async def close(self) -> None:
        """Close the Groq async client and release resources."""
        if self._client:
            await self._client.close()
            self._logger.debug("[GroqLLM] Client closed")
