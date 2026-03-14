"""Base class for LLM providers.

Contains all shared logic: retry with exponential backoff, error
classification, schema normalization, and the structured_output template method.

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
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

from pydantic import BaseModel

from airweave.adapters.llm.exceptions import (
    LLMFatalError,
    LLMProviderExhaustedError,
    LLMTransientError,
)
from airweave.adapters.llm.registry import LLMModelSpec
from airweave.adapters.llm.tool_response import LLMToolResponse
from airweave.core.logging import logger as _default_logger
from airweave.core.protocols.llm import LLMProtocol

T = TypeVar("T", bound=BaseModel)


class BaseLLM(LLMProtocol):
    """Base class for all LLM providers.

    Explicitly implements the LLMProtocol.

    Provides:
    - model_spec property
    - structured_output() template method (validate → prepare schema → retry loop)
    - Exponential backoff retry logic with typed error classification
    - Strict-mode schema normalization (for OpenAI-compatible APIs)
    - Basic schema cleanup (for Anthropic tool_use)
    """

    # Defaults — subclasses can override as class constants
    MAX_RETRIES = 1
    INITIAL_RETRY_DELAY = 1.0  # seconds
    MAX_RETRY_DELAY = 30.0  # seconds
    RETRY_MULTIPLIER = 2.0  # exponential backoff
    DEFAULT_TIMEOUT = 120.0

    # Error classification — checked against str(error).lower()
    FATAL_INDICATORS = [
        "401",
        "403",
        "authentication",
        "unauthorized",
        "invalid_api_key",
        "model_not_found",
        "invalid_request_error",
        "permission",
        "forbidden",
    ]

    TRANSIENT_INDICATORS = [
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
        logger: logging.Logger | logging.LoggerAdapter | None = None,
        max_retries: int | None = None,
    ) -> None:
        """Initialize shared state.

        Args:
            model_spec: Model specification from the registry.
            logger: Logger instance. Defaults to the module-level logger.
            max_retries: Override default retry count. Set to 0 for single-attempt
                mode (used when wrapped in a fallback chain).
        """
        self._model_spec = model_spec
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
        """
        if not prompt:
            raise ValueError("Prompt cannot be empty")

        try:
            schema_json = schema.model_json_schema()
        except Exception as e:
            raise ValueError(f"Failed to build JSON schema from Pydantic model: {e}") from e

        schema_json = self._prepare_schema(schema_json)

        return await self._with_retry(
            "API call", self._call_api, prompt, schema, schema_json, system_prompt
        )

    async def create_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMToolResponse:
        """Send a conversation with tools and get a response.

        Template method: wraps the provider-specific _call_api_with_tools
        with the same retry logic used by structured_output.
        """
        return await self._with_retry(
            "tool API call", self._call_api_with_tools, messages, tools, system_prompt
        )

    # ── Hooks for subclasses ─────────────────────────────────────────────

    def _prepare_schema(self, schema_json: dict[str, Any]) -> dict[str, Any]:
        """Transform schema before the API call. Override in subclass."""
        return schema_json

    async def _call_api(
        self,
        prompt: str,
        schema: type[T],
        schema_json: dict[str, Any],
        system_prompt: str,
    ) -> T:
        """Make a single API call. Must be implemented by subclass."""
        raise NotImplementedError

    async def _call_api_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMToolResponse:
        """Make a single API call with tools. Must be implemented by subclass."""
        raise NotImplementedError

    async def close(self) -> None:
        """Clean up SDK client. Must be implemented by subclass."""
        raise NotImplementedError

    # ── Retry logic ──────────────────────────────────────────────────────

    async def _with_retry(
        self,
        label: str,
        fn: Callable[..., Coroutine[Any, Any, Any]],
        *args: Any,
    ) -> Any:
        """Execute an async callable with exponential backoff retry.

        Error handling:
        - LLMFatalError: raised immediately, no retry
        - LLMTransientError: retried up to max_retries
        - TimeoutError: wrapped as LLMTransientError, retried
        - Other exceptions: classified via _classify_error, then
          either raised immediately (fatal) or retried (transient)

        Raises:
            LLMFatalError: If the error is non-retryable.
            LLMProviderExhaustedError: If all retries are exhausted.
        """
        last_error: LLMTransientError | None = None
        retry_delay = self.INITIAL_RETRY_DELAY

        for attempt in range(self._max_retries + 1):
            try:
                return await fn(*args)

            except LLMFatalError:
                raise

            except LLMTransientError as e:
                last_error = e
                self._logger.warning(
                    f"[{self._name}] {label} transient error on attempt "
                    f"{attempt + 1}/{self._max_retries + 1}: {e}"
                )

            except (TimeoutError, asyncio.TimeoutError) as e:
                last_error = LLMTransientError(
                    f"{self._name} {label} timed out: {e}",
                    provider=self._name,
                    cause=e,
                )
                self._logger.warning(
                    f"[{self._name}] {label} timeout on attempt "
                    f"{attempt + 1}/{self._max_retries + 1}: {e}"
                )

            except Exception as e:
                classified = self._classify_error(e, label)
                if isinstance(classified, LLMFatalError):
                    raise classified from e
                last_error = classified
                self._logger.warning(
                    f"[{self._name}] {label} transient error on attempt "
                    f"{attempt + 1}/{self._max_retries + 1}: {e}"
                )

            if attempt < self._max_retries:
                self._logger.debug(f"[{self._name}] Retrying in {retry_delay:.1f}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * self.RETRY_MULTIPLIER, self.MAX_RETRY_DELAY)

        raise LLMProviderExhaustedError(
            f"{self._name} {label} failed after {self._max_retries + 1} attempts: {last_error}",
            provider=self._name,
            cause=last_error,
        )

    def _classify_error(self, error: Exception, label: str) -> LLMTransientError | LLMFatalError:
        """Classify an unknown exception as transient or fatal.

        Checks the error message against known indicator strings.
        Fatal indicators are checked first (more specific). If neither
        matches, defaults to transient (safer to retry than to fail).
        """
        error_str = str(error).lower()

        if any(indicator in error_str for indicator in self.FATAL_INDICATORS):
            return LLMFatalError(
                f"{self._name} {label} fatal error: {error}",
                provider=self._name,
                cause=error,
            )

        # Transient (explicit match or unknown → default to transient)
        return LLMTransientError(
            f"{self._name} {label} transient error: {error}",
            provider=self._name,
            cause=error,
        )

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
            for v in node.values():
                BaseLLM._walk_strict(v)
        elif isinstance(node, list):
            for v in node:
                BaseLLM._walk_strict(v)

    @staticmethod
    def _strip_strict_constraints(node: dict[str, Any]) -> None:
        """Strip unsupported type constraints and informational fields for strict mode."""
        if node.get("type") == "array":
            node.pop("minItems", None)
            node.pop("maxItems", None)
            if "prefixItems" in node:
                node["items"] = False
            elif node.get("items") is True:
                node.pop("items")

        if node.get("type") == "string":
            node.pop("pattern", None)
            node.pop("format", None)

        node.pop("title", None)

        if node.get("type") == "object" and "properties" in node:
            node["additionalProperties"] = False
            node["required"] = list(node["properties"].keys())

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

    def _parse_json_response(self, content: str, schema: type[T]) -> T:
        """Parse JSON string into a Pydantic model.

        Raises LLMTransientError on parse failure (retry may produce valid output).
        """
        try:
            return schema.model_validate(json.loads(content))
        except json.JSONDecodeError as e:
            raise LLMTransientError(
                f"{self._name} returned invalid JSON: {e}",
                provider=self._name,
                cause=e,
            ) from e
        except Exception as e:
            raise LLMTransientError(
                f"Failed to parse {self._name} response: {e}",
                provider=self._name,
                cause=e,
            ) from e
