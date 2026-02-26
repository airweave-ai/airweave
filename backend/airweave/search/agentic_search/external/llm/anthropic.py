"""Anthropic LLM implementation for agentic search.

Fallback provider (Claude 4.5 Sonnet). Uses tool_use for structured output
since Anthropic doesn't support json_schema response_format directly.
"""

import json
import time
from typing import Any, TypeVar

from anthropic import AsyncAnthropic
from pydantic import BaseModel

from airweave.core.config import settings
from airweave.search.agentic_search.external.llm.base import BaseLLM
from airweave.search.agentic_search.external.llm.registry import LLMModelSpec
from airweave.search.agentic_search.external.tokenizer import AgenticSearchTokenizerInterface

T = TypeVar("T", bound=BaseModel)


class AnthropicLLM(BaseLLM):
    """Anthropic LLM provider using tool_use for structured output."""

    def __init__(
        self,
        model_spec: LLMModelSpec,
        tokenizer: AgenticSearchTokenizerInterface,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the Anthropic LLM client with API key validation."""
        super().__init__(model_spec, tokenizer, max_retries=max_retries)

        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not configured. Set it in your environment or .env file."
            )

        try:
            self._client = AsyncAnthropic(api_key=api_key, timeout=self.DEFAULT_TIMEOUT)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Anthropic client: {e}") from e

        self._logger.debug(
            f"[AnthropicLLM] Initialized with model={model_spec.api_model_name}, "
            f"context_window={model_spec.context_window}, "
            f"max_output_tokens={model_spec.max_output_tokens}"
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
        # Build tool definition from schema
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
            raise TimeoutError("Anthropic did not return a tool_use block (retryable)")

        if response.usage:
            self._logger.debug(
                f"[AnthropicLLM] API call completed in {api_time:.2f}s, "
                f"tokens: input={response.usage.input_tokens}, "
                f"output={response.usage.output_tokens}"
            )

        # tool_input is already a dict (Anthropic SDK parses it)
        try:
            if isinstance(tool_input, str):
                tool_input = json.loads(tool_input)
            return schema.model_validate(tool_input)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Anthropic returned invalid JSON: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to parse Anthropic response: {e}") from e

    async def close(self) -> None:
        """Close the Anthropic async client and release resources."""
        if self._client:
            await self._client.close()
            self._logger.debug("[AnthropicLLM] Client closed")
