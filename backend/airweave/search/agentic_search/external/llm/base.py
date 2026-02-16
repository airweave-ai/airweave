"""Base class for agentic search LLM providers.

Contains all shared logic: retry with exponential backoff, retryable error
detection, schema normalization, and the structured_output template method.

Subclasses only need to implement:
- __init__: SDK client initialization (must call super().__init__)
- _call_api: The actual provider-specific API call
- _prepare_schema: (optional) schema transformation before the API call
- close: SDK client cleanup
"""

import asyncio
import copy
import json
import logging
from typing import Any, TypeVar

from pydantic import BaseModel

from airweave.core.logging import logger as _default_logger
from airweave.search.agentic_search.external.llm.interface import AgenticSearchLLMInterface
from airweave.search.agentic_search.external.llm.registry import LLMModelSpec
from airweave.search.agentic_search.external.tokenizer import AgenticSearchTokenizerInterface

T = TypeVar("T", bound=BaseModel)


class BaseLLM(AgenticSearchLLMInterface):
    """Base class for all agentic search LLM providers.

    Explicitly implements the AgenticSearchLLMInterface protocol.

    Provides:
    - model_spec property
    - structured_output() template method (validate → prepare schema → retry loop)
    - Exponential backoff retry logic with configurable max_retries
    - Retryable error detection
    - Strict-mode schema normalization (for OpenAI-compatible APIs)
    - Basic schema cleanup (for Anthropic tool_use)
    """

    # Defaults — subclasses can override as class constants
    MAX_RETRIES = 1
    INITIAL_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 30.0  # seconds
    RETRY_MULTIPLIER = 2.0  # exponential backoff
    DEFAULT_TIMEOUT = 120.0

    # Error strings that indicate a transient, retryable failure
    RETRYABLE_INDICATORS = [
        "rate limit",
        "429",
        "500",
        "502",
        "503",
        "504",
        "timeout",
        "connection",
        "network",
        "overloaded",
    ]

    def __init__(
        self,
        model_spec: LLMModelSpec,
        tokenizer: AgenticSearchTokenizerInterface,
        logger: logging.Logger | logging.LoggerAdapter | None = None,
        max_retries: int | None = None,
    ) -> None:
        """Initialize shared state.

        Args:
            model_spec: Model specification from the registry.
            tokenizer: Tokenizer for token counting.
            logger: Logger instance. Defaults to the module-level logger,
                allowing providers to be long-lived singletons.
            max_retries: Override default retry count. Set to 0 for single-attempt
                mode (used when wrapped in a fallback chain).
        """
        self._model_spec = model_spec
        self._tokenizer = tokenizer
        self._logger = logger or _default_logger
        self._max_retries = max_retries if max_retries is not None else self.MAX_RETRIES

    @property
    def model_spec(self) -> LLMModelSpec:
        """Get the model specification."""
        return self._model_spec

    @property
    def _name(self) -> str:
        """Provider name for log messages (e.g., 'CerebrasLLM')."""
        return self.__class__.__name__

    # ── Template method ──────────────────────────────────────────────────

    async def structured_output(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str,
    ) -> T:
        """Generate structured output matching the schema.

        Template method: validates input, builds schema JSON, calls the
        provider-specific _call_api via the retry loop.

        Args:
            prompt: The user prompt (dynamic context).
            schema: Pydantic model class for the response.
            system_prompt: System prompt (static instructions).

        Returns:
            Parsed response matching schema.

        Raises:
            ValueError: If prompt is empty or schema is invalid.
            RuntimeError: If API call fails after all retries.
        """
        if not prompt:
            raise ValueError("Prompt cannot be empty")

        try:
            schema_json = schema.model_json_schema()
        except Exception as e:
            raise ValueError(f"Failed to build JSON schema from Pydantic model: {e}") from e

        schema_json = self._prepare_schema(schema_json)

        return await self._execute_with_retry(prompt, schema, schema_json, system_prompt)

    # ── Hooks for subclasses ─────────────────────────────────────────────

    def _prepare_schema(self, schema_json: dict[str, Any]) -> dict[str, Any]:
        """Transform schema before the API call. Override in subclass.

        Default: no-op (returns schema unchanged).
        """
        return schema_json

    async def _call_api(
        self,
        prompt: str,
        schema: type[T],
        schema_json: dict[str, Any],
        system_prompt: str,
    ) -> T:
        """Make a single API call. Must be implemented by subclass.

        Args:
            prompt: User prompt text.
            schema: Pydantic model class for response parsing.
            schema_json: Prepared JSON schema.
            system_prompt: System prompt text.

        Returns:
            Parsed and validated response.
        """
        raise NotImplementedError

    async def close(self) -> None:
        """Clean up SDK client. Must be implemented by subclass."""
        raise NotImplementedError

    # ── Retry logic ──────────────────────────────────────────────────────

    async def _execute_with_retry(
        self,
        prompt: str,
        schema: type[T],
        schema_json: dict[str, Any],
        system_prompt: str,
    ) -> T:
        """Execute _call_api with exponential backoff retry."""
        last_error: Exception | None = None
        retry_delay = self.INITIAL_RETRY_DELAY

        for attempt in range(self._max_retries + 1):
            try:
                return await self._call_api(prompt, schema, schema_json, system_prompt)

            except (TimeoutError, asyncio.TimeoutError) as e:
                last_error = e
                self._logger.warning(
                    f"[{self._name}] Timeout on attempt {attempt + 1}/{self._max_retries + 1}: {e}"
                )
            except RuntimeError:
                # Don't retry on parse errors or empty responses
                raise
            except Exception as e:
                last_error = e
                if not self._is_retryable_error(e):
                    raise RuntimeError(f"{self._name} API call failed: {e}") from e

                self._logger.warning(
                    f"[{self._name}] Retryable error on attempt "
                    f"{attempt + 1}/{self._max_retries + 1}: {e}"
                )

            if attempt < self._max_retries:
                self._logger.debug(f"[{self._name}] Retrying in {retry_delay:.1f}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * self.RETRY_MULTIPLIER, self.MAX_RETRY_DELAY)

        raise RuntimeError(
            f"{self._name} API call failed after {self._max_retries + 1} attempts: {last_error}"
        ) from last_error

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if an error is transient and should be retried."""
        error_str = str(error).lower()
        return any(indicator in error_str for indicator in self.RETRYABLE_INDICATORS)

    # ── Schema normalization utilities ────────────────────────────────────

    @staticmethod
    def _normalize_strict_schema(schema_dict: dict[str, Any]) -> dict[str, Any]:
        """Normalize JSON schema for strict mode (Cerebras / Groq with GPT-OSS).

        Removes unsupported constraints (minItems, maxItems, pattern, format),
        strips informational fields, and adds additionalProperties: false.
        """
        normalized = copy.deepcopy(schema_dict)
        BaseLLM._walk_strict(normalized)
        return normalized

    @staticmethod
    def _walk_strict(node: Any) -> None:
        """Recursively normalize a schema node for strict mode."""
        if isinstance(node, dict):
            BaseLLM._strip_strict_constraints(node)
            BaseLLM._simplify_strict_anyof(node)
            for v in node.values():
                BaseLLM._walk_strict(v)
        elif isinstance(node, list):
            for v in node:
                BaseLLM._walk_strict(v)

    @staticmethod
    def _strip_strict_constraints(node: dict[str, Any]) -> None:
        """Strip unsupported type constraints and informational fields for strict mode."""
        # Arrays: drop unsupported constraints
        if node.get("type") == "array":
            node.pop("minItems", None)
            node.pop("maxItems", None)
            if "prefixItems" in node:
                node["items"] = False
            elif node.get("items") is True:
                node.pop("items")

        # Strings: drop unsupported constraints
        if node.get("type") == "string":
            node.pop("pattern", None)
            node.pop("format", None)

        # Strip informational fields
        for key in ("title", "description", "examples", "default"):
            node.pop(key, None)

        # Strict mode: all properties must be required, no additional properties
        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"].keys())

    @staticmethod
    def _simplify_strict_anyof(node: dict[str, Any]) -> None:
        """Simplify anyOf for strict-mode providers that require discriminated branches.

        Strict-mode providers (Groq/Cerebras) require anyOf branches to be
        disambiguated via a const/enum discriminator or key-set exclusion with
        additionalProperties:false. Primitive types can never satisfy that rule,
        so when there are multiple non-null primitive branches we drop the anyOf
        entirely -- the property becomes unconstrained.
        """
        if "anyOf" not in node or not isinstance(node["anyOf"], list):
            return

        _PRIMITIVE_TYPES = {"string", "number", "integer", "boolean", "array"}
        branches = node["anyOf"]
        non_null = [s for s in branches if isinstance(s, dict) and s.get("type") != "null"]
        all_primitive = all(
            isinstance(s, dict) and s.get("type") in _PRIMITIVE_TYPES for s in non_null
        )
        if all_primitive and len(non_null) > 1:
            del node["anyOf"]

    @staticmethod
    def _clean_schema_basic(schema_dict: dict[str, Any]) -> dict[str, Any]:
        """Light schema cleanup (strip title/examples/default). For Anthropic tool_use."""
        normalized = copy.deepcopy(schema_dict)

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                for key in ("title", "examples", "default"):
                    node.pop(key, None)
                for v in node.values():
                    _walk(v)
            elif isinstance(node, list):
                for v in node:
                    _walk(v)

        _walk(normalized)
        return normalized

    # ── Response parsing helper ──────────────────────────────────────────

    @staticmethod
    def _parse_json_response(content: str, schema: type[T], provider_name: str) -> T:
        """Parse JSON string into a Pydantic model.

        Args:
            content: Raw JSON string from the API response.
            schema: Pydantic model class for validation.
            provider_name: Provider name for error messages.

        Returns:
            Validated Pydantic model instance.

        Raises:
            RuntimeError: If JSON is invalid or doesn't match schema.
        """
        try:
            return schema.model_validate(json.loads(content))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"{provider_name} returned invalid JSON: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to parse {provider_name} response: {e}") from e
