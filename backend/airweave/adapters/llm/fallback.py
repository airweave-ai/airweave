"""Fallback chain LLM wrapper.

Wraps an ordered list of LLM providers. Tries each in sequence until one
succeeds. Uses a circuit breaker to skip providers that recently failed.

Follows the same pattern as adapters/ocr/fallback.py — a single try-chain
method handles the provider iteration for all LLM operations.
"""

import logging
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from pydantic import BaseModel

from airweave.adapters.llm.exceptions import (
    LLMAllProvidersFailedError,
    LLMError,
)
from airweave.adapters.llm.registry import LLMModelSpec
from airweave.adapters.llm.tool_response import LLMToolResponse
from airweave.core.logging import logger as _default_logger
from airweave.core.protocols import CircuitBreaker
from airweave.core.protocols.llm import LLMProtocol

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")


class FallbackChainLLM(LLMProtocol):
    """LLM wrapper that chains multiple providers with automatic fallback.

    Explicitly implements LLMProtocol.
    Exposes the first (primary) provider's model_spec so token budgeting
    stays consistent.

    On each call:
    1. Skip providers whose circuit breaker is tripped (recently failed).
    2. Try remaining providers in order until one succeeds.
    3. Record success/failure in the circuit breaker for future calls.
    4. If ALL providers are tripped, try them anyway (best-effort).
    """

    def __init__(
        self,
        providers: list[LLMProtocol],
        circuit_breaker: CircuitBreaker,
        logger: logging.Logger | logging.LoggerAdapter | None = None,
    ) -> None:
        """Initialize with an ordered list of LLM providers.

        Args:
            providers: Ordered list of providers to try (first = primary).
            circuit_breaker: Circuit breaker for provider failover caching.
            logger: Logger instance. Defaults to module-level logger.

        Raises:
            ValueError: If providers list is empty.
        """
        if not providers:
            raise ValueError("FallbackChainLLM requires at least one provider")

        self._providers = providers
        self._circuit_breaker = circuit_breaker
        self._logger = logger or _default_logger

        # Analytics tracking
        self._calls_per_provider: dict[str, int] = defaultdict(int)
        self._fallback_count: int = 0
        self._total_calls: int = 0

        self._primary_name = providers[0].model_spec.api_model_name
        names = [p.model_spec.api_model_name for p in providers]
        self._logger.debug(f"[FallbackChainLLM] Chain initialized: {' → '.join(names)}")

    @property
    def model_spec(self) -> LLMModelSpec:
        """Expose primary provider's model spec for consistent token budgeting."""
        return self._providers[0].model_spec

    @property
    def fallback_stats(self) -> dict[str, Any]:
        """Cumulative fallback statistics for analytics."""
        rate = self._fallback_count / self._total_calls if self._total_calls > 0 else 0.0
        return {
            "total_calls": self._total_calls,
            "fallback_count": self._fallback_count,
            "fallback_rate": round(rate, 3),
            "calls_per_provider": dict(self._calls_per_provider),
            "primary_provider": self._primary_name,
        }

    async def structured_output(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str,
    ) -> T:
        """Generate structured output, falling through the provider chain."""
        return await self._try_chain(lambda p: p.structured_output(prompt, schema, system_prompt))

    async def create_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        system_prompt: str,
    ) -> LLMToolResponse:
        """Send a tool-calling conversation, falling through the provider chain."""
        return await self._try_chain(lambda p: p.create_with_tools(messages, tools, system_prompt))

    async def close(self) -> None:
        """Clean up all providers in the chain."""
        for provider in self._providers:
            try:
                await provider.close()
            except Exception as e:
                self._logger.warning(
                    f"[FallbackChainLLM] Error closing {provider.model_spec.api_model_name}: {e}"
                )

        self._logger.debug(f"[FallbackChainLLM] All {len(self._providers)} providers closed")

    # ── Core fallback logic ──────────────────────────────────────────────

    async def _try_chain(
        self,
        call_fn: Callable[[LLMProtocol], Awaitable[R]],
    ) -> R:
        """Try providers in order until one succeeds.

        Skips circuit-broken providers. On failure, records the failure
        and tries the next provider. If all are tripped, tries them all
        as a last resort.

        Args:
            call_fn: Async callable that takes a provider and returns a result.

        Raises:
            LLMAllProvidersFailedError: If all providers in the chain fail.
        """
        self._total_calls += 1

        # Partition providers into available vs tripped
        available: list[LLMProtocol] = []
        for provider in self._providers:
            key = provider.model_spec.api_model_name
            if await self._circuit_breaker.is_available(key):
                available.append(provider)
            else:
                self._logger.debug(f"[FallbackChainLLM] Skipping {key} (circuit breaker tripped)")

        # If all providers are tripped, try them all as a last resort
        if not available:
            self._logger.warning(
                "[FallbackChainLLM] All providers tripped — trying all as last resort"
            )
            available = list(self._providers)

        errors: list[tuple[str, LLMError]] = []

        for i, provider in enumerate(available):
            provider_name = provider.model_spec.api_model_name
            try:
                result = await call_fn(provider)

                # Success — update analytics and circuit breaker
                self._calls_per_provider[provider_name] += 1
                if provider_name != self._primary_name:
                    self._fallback_count += 1
                await self._circuit_breaker.record_success(provider_name)

                if i > 0:
                    self._logger.info(
                        f"[FallbackChainLLM] Provider #{i + 1} ({provider_name}) succeeded "
                        f"after {i} failed provider(s)."
                    )
                return result

            except LLMError as e:
                # Provider failed — trip circuit breaker and try next
                await self._circuit_breaker.record_failure(provider_name)
                errors.append((provider_name, e))

                if i < len(available) - 1:
                    next_name = available[i + 1].model_spec.api_model_name
                    self._logger.warning(
                        f"[FallbackChainLLM] Provider {provider_name} failed: {e}. "
                        f"Trying next: {next_name}..."
                    )
                else:
                    self._logger.error(
                        f"[FallbackChainLLM] Last provider {provider_name} also failed: {e}"
                    )

        raise LLMAllProvidersFailedError(errors)
