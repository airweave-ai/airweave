"""Cerebras LLM implementation for agentic search.

Uses the Cerebras Cloud SDK for structured output generation with reasoning models.
Implements rate limiting based on model spec and exponential backoff retry logic.
"""

import asyncio
import copy
import json
import time
from typing import Any, TypeVar

from cerebras.cloud.sdk import AsyncCerebras
from pydantic import BaseModel

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.search.agentic_search.external.llm.rate_limiter import get_shared_rate_limiter
from airweave.search.agentic_search.external.llm.registry import LLMModelSpec
from airweave.search.agentic_search.external.tokenizer import AgenticSearchTokenizerInterface

T = TypeVar("T", bound=BaseModel)


class CerebrasLLM:
    """Cerebras LLM implementation for agentic search.

    Uses the AsyncCerebras client for async operations.
    Features:
    - Structured output with JSON schema enforcement
    - Model-specific reasoning configuration (from ModelSpec.reasoning)
    - Rate limiting based on model spec (RPM/TPM)
    - Exponential backoff retry logic
    - Schema normalization for Cerebras compatibility
    """

    # Retry configuration
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 30.0  # seconds
    RETRY_MULTIPLIER = 2.0  # exponential backoff

    # Timeout configuration
    DEFAULT_TIMEOUT = 120.0

    def __init__(
        self,
        model_spec: LLMModelSpec,
        tokenizer: AgenticSearchTokenizerInterface,
        logger: ContextualLogger,
    ) -> None:
        """Initialize Cerebras LLM.

        Args:
            model_spec: The model specification from the registry.
                Contains api_model_name, context limits, and rate limits.
            tokenizer: Tokenizer for accurate token counting (must match model spec).
            logger: Contextual logger for debug output.

        Raises:
            ValueError: If CEREBRAS_API_KEY is not configured.
            RuntimeError: If client initialization fails.
        """
        self._model_spec = model_spec
        self._tokenizer = tokenizer
        self._logger = logger

        api_key = settings.CEREBRAS_API_KEY
        if not api_key:
            raise ValueError(
                "CEREBRAS_API_KEY not configured. Set it in your environment or .env file."
            )

        try:
            self._client = AsyncCerebras(
                api_key=api_key,
                timeout=self.DEFAULT_TIMEOUT,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Cerebras client: {e}") from e

        # Get shared rate limiter (singleton, created on first use)
        self._rate_limiter = get_shared_rate_limiter(
            model_spec=model_spec,
            logger=logger,
        )

        self._logger.debug(
            f"[CerebrasLLM] Initialized with model={model_spec.api_model_name}, "
            f"context_window={model_spec.context_window}, "
            f"max_output_tokens={model_spec.max_output_tokens}"
        )

    @property
    def model_spec(self) -> LLMModelSpec:
        """Get the model specification."""
        return self._model_spec

    async def structured_output(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str,
    ) -> T:
        """Generate structured output matching the schema.

        Uses Cerebras JSON schema mode with strict enforcement.
        Applies model-specific reasoning configuration from ModelSpec.

        Implements exponential backoff retry on transient failures.

        Args:
            prompt: The user prompt (dynamic context).
            schema: Pydantic model class for the response.
            system_prompt: System prompt (static instructions). Sent as a system message
                before the user message, giving the instructions higher priority in the
                model's attention.

        Returns:
            Parsed response matching schema.

        Raises:
            ValueError: If prompt is empty or schema is invalid.
            RuntimeError: If API call fails after all retries.
        """
        if not prompt:
            raise ValueError("Prompt cannot be empty")

        # Build JSON schema from Pydantic model
        try:
            schema_json = schema.model_json_schema()
        except Exception as e:
            raise ValueError(f"Failed to build JSON schema from Pydantic model: {e}") from e

        # Normalize schema for Cerebras compatibility
        schema_json = self._normalize_schema_for_cerebras(schema_json)

        # Build messages: system (instructions) + user (context)
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

        # Count tokens accurately using the tokenizer
        input_tokens = self._tokenizer.count_tokens(system_prompt) + self._tokenizer.count_tokens(
            prompt
        )

        # Execute with retry logic
        return await self._execute_with_retry(messages, schema, schema_json, input_tokens)

    async def _execute_with_retry(
        self,
        messages: list[dict[str, str]],
        schema: type[T],
        schema_json: dict[str, Any],
        input_tokens: int,
    ) -> T:
        """Execute API call with exponential backoff retry.

        Args:
            messages: Chat messages to send.
            schema: Pydantic model class for response parsing.
            schema_json: Normalized JSON schema for Cerebras.
            input_tokens: Token count for rate limiting.

        Returns:
            Parsed response matching schema.

        Raises:
            RuntimeError: If API call fails after all retries.
        """
        last_error: Exception | None = None
        retry_delay = self.INITIAL_RETRY_DELAY

        for attempt in range(self.MAX_RETRIES + 1):
            try:
                return await self._make_api_call(messages, schema, schema_json, input_tokens)

            except (TimeoutError, asyncio.TimeoutError) as e:
                last_error = e
                self._logger.warning(
                    f"[CerebrasLLM] Timeout on attempt {attempt + 1}/{self.MAX_RETRIES + 1}: {e}"
                )
            except RuntimeError:
                # Don't retry on parse errors or empty responses
                raise
            except Exception as e:
                last_error = e
                if not self._is_retryable_error(e):
                    raise RuntimeError(f"Cerebras API call failed: {e}") from e

                self._logger.warning(
                    f"[CerebrasLLM] Retryable error on attempt "
                    f"{attempt + 1}/{self.MAX_RETRIES + 1}: {e}"
                )

            # Retry with exponential backoff
            if attempt < self.MAX_RETRIES:
                self._logger.debug(f"[CerebrasLLM] Retrying in {retry_delay:.1f}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * self.RETRY_MULTIPLIER, self.MAX_RETRY_DELAY)

        raise RuntimeError(
            f"Cerebras API call failed after {self.MAX_RETRIES + 1} attempts: {last_error}"
        ) from last_error

    async def _make_api_call(
        self,
        messages: list[dict[str, str]],
        schema: type[T],
        schema_json: dict[str, Any],
        input_tokens: int,
    ) -> T:
        """Make a single API call to Cerebras.

        Args:
            messages: Chat messages to send.
            schema: Pydantic model class for response parsing.
            schema_json: Normalized JSON schema for Cerebras.
            input_tokens: Token count for rate limiting.

        Returns:
            Parsed response matching schema.

        Raises:
            RuntimeError: If response is empty or invalid.
        """
        # Acquire rate limit slot
        await self._rate_limiter.acquire(input_tokens)

        # Build reasoning params from model spec
        reasoning_params = {
            self._model_spec.reasoning.param_name: self._model_spec.reasoning.param_value
        }

        # Make API call
        api_start = time.monotonic()
        response = await self._client.chat.completions.create(
            model=self._model_spec.api_model_name,
            messages=messages,
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

        # Extract content from response
        content = response.choices[0].message.content
        if not content:
            raise TimeoutError("Cerebras returned empty response content (retryable)")

        # Record actual token usage
        if response.usage:
            self._rate_limiter.record_tokens(response.usage.total_tokens)
            self._logger.debug(
                f"[CerebrasLLM] API call completed in {api_time:.2f}s, "
                f"tokens: prompt={response.usage.prompt_tokens}, "
                f"completion={response.usage.completion_tokens}, "
                f"total={response.usage.total_tokens}"
            )

        # Parse and validate against schema
        try:
            return schema.model_validate(json.loads(content))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Cerebras returned invalid JSON: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to parse Cerebras response: {e}") from e

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is retryable.

        Args:
            error: The exception to check.

        Returns:
            True if the error is transient and should be retried.
        """
        error_str = str(error).lower()
        retryable_indicators = [
            "rate limit",
            "429",
            "500",
            "502",
            "503",
            "504",
            "timeout",
            "connection",
            "network",
        ]
        return any(indicator in error_str for indicator in retryable_indicators)

    def _normalize_schema_for_cerebras(self, schema_dict: dict[str, Any]) -> dict[str, Any]:
        """Normalize JSON schema for Cerebras compatibility.

        Cerebras strict mode has specific requirements and unsupported features.
        This normalizes the schema to ensure compatibility.

        Unsupported features that are removed/normalized:
        - minItems/maxItems: Not supported for arrays
        - pattern: Regex constraints on strings not supported
        - format: Format validation (email, date-time, uuid) not supported
        - items: true: Not supported (use explicit schema or items: false with prefixItems)

        Note: Some features cannot be automatically normalized:
        - Recursive schemas: Must be avoided in Pydantic model design
        - External $ref: Must use local $defs instead
        - $anchor keyword: Must use relative paths

        Args:
            schema_dict: The JSON schema dictionary from Pydantic.

        Returns:
            Normalized schema dictionary safe for Cerebras.

        Example:
            Input (Pydantic generates this for Tuple[str, int]):
            {
                "type": "array",
                "prefixItems": [{"type": "string"}, {"type": "integer"}],
                "minItems": 2,
                "maxItems": 2
            }

            Output (normalized for Cerebras):
            {
                "type": "array",
                "prefixItems": [{"type": "string"}, {"type": "integer"}],
                "items": false
            }

            Input (string with format):
            {"type": "string", "format": "email"}

            Output (format removed):
            {"type": "string"}
        """
        normalized = copy.deepcopy(schema_dict)
        self._walk_schema(normalized)
        return normalized

    def _walk_schema(self, node: Any) -> None:
        """Recursively walk and normalize all nodes in a JSON schema."""
        if isinstance(node, dict):
            self._normalize_schema_node(node)
            for v in node.values():
                self._walk_schema(v)
        elif isinstance(node, list):
            for v in node:
                self._walk_schema(v)

    @staticmethod
    def _normalize_schema_node(node: dict) -> None:
        """Normalize a single dict node for Cerebras compatibility."""
        # Handle arrays: remove unsupported constraints
        if node.get("type") == "array":
            node.pop("minItems", None)
            node.pop("maxItems", None)
            if "prefixItems" in node:
                node["items"] = False
            elif node.get("items") is True:
                node.pop("items")

        # Handle strings: remove unsupported constraints
        if node.get("type") == "string":
            node.pop("pattern", None)
            node.pop("format", None)

        # Remove informational-only fields
        for key in ("title", "description", "examples", "default"):
            node.pop(key, None)

        # Cerebras strict mode requires additionalProperties: false on all objects
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False

    async def close(self) -> None:
        """Clean up resources.

        Closes the underlying HTTP client.
        """
        if self._client:
            await self._client.close()
            self._logger.debug("[CerebrasLLM] Client closed")
