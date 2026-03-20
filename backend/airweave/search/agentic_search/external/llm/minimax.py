"""MiniMax LLM implementation for agentic search.

Fallback provider using the MiniMax Cloud API (OpenAI-compatible). Uses
json_object response format with schema instructions in the system prompt,
since MiniMax does not support strict json_schema mode.
"""

import json
import time
from typing import Any, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from airweave.core.config import settings
from airweave.search.agentic_search.external.llm.base import BaseLLM
from airweave.search.agentic_search.external.llm.registry import LLMModelSpec
from airweave.search.agentic_search.external.tokenizer import AgenticSearchTokenizerInterface

T = TypeVar("T", bound=BaseModel)

MINIMAX_BASE_URL = "https://api.minimax.io/v1"


class MiniMaxLLM(BaseLLM):
    """MiniMax LLM provider with json_object structured output."""

    def __init__(
        self,
        model_spec: LLMModelSpec,
        tokenizer: AgenticSearchTokenizerInterface,
        max_retries: int | None = None,
    ) -> None:
        """Initialize the MiniMax LLM client via OpenAI-compatible SDK."""
        super().__init__(model_spec, tokenizer, max_retries=max_retries)

        api_key = settings.MINIMAX_API_KEY
        if not api_key:
            raise ValueError(
                "MINIMAX_API_KEY not configured. Set it in your environment or .env file."
            )

        try:
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=MINIMAX_BASE_URL,
                timeout=self.DEFAULT_TIMEOUT,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize MiniMax client: {e}") from e

        self._logger.debug(
            f"[MiniMaxLLM] Initialized with model={model_spec.api_model_name}, "
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
        # Embed JSON schema in the system prompt so the model knows the
        # expected output structure (MiniMax does not support strict
        # json_schema mode, so we use json_object + prompt guidance).
        schema_instruction = (
            f"\n\nYou MUST respond with valid JSON matching this schema:\n"
            f"```json\n{json.dumps(schema_json, indent=2)}\n```\n"
            f"Do not include any text outside the JSON object."
        )
        augmented_system_prompt = system_prompt + schema_instruction

        api_start = time.monotonic()
        response = await self._client.chat.completions.create(
            model=self._model_spec.api_model_name,
            messages=[
                {"role": "system", "content": augmented_system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
            max_tokens=self._model_spec.max_output_tokens,
        )
        api_time = time.monotonic() - api_start

        content = response.choices[0].message.content
        if not content:
            raise TimeoutError("MiniMax returned empty response content (retryable)")

        # Strip <think>...</think> blocks that MiniMax M2.7 may include
        # before the JSON payload.
        content = self._strip_think_tags(content)

        if response.usage:
            self._logger.debug(
                f"[MiniMaxLLM] API call completed in {api_time:.2f}s, "
                f"tokens: prompt={response.usage.prompt_tokens}, "
                f"completion={response.usage.completion_tokens}, "
                f"total={response.usage.total_tokens}"
            )

        return self._parse_json_response(content, schema, "MiniMax")

    @staticmethod
    def _strip_think_tags(text: str) -> str:
        """Remove <think>...</think> blocks from MiniMax M2.7 responses."""
        import re

        return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()

    async def close(self) -> None:
        """Close the MiniMax async client and release resources."""
        if self._client:
            await self._client.close()
            self._logger.debug("[MiniMaxLLM] Client closed")
