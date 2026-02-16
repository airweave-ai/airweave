"""Fallback chain LLM wrapper for agentic search.

Wraps an ordered list of LLM providers. Tries each in sequence until one
succeeds. Uses a circuit breaker to skip providers that recently failed,
avoiding wasted retries on providers known to be down.
"""

import logging
from collections import defaultdict
from typing import Any, TypeVar

from pydantic import BaseModel

from airweave.core.logging import logger as _default_logger
from airweave.core.protocols import CircuitBreaker
from airweave.search.agentic_search.external.llm.interface import AgenticSearchLLMInterface
from airweave.search.agentic_search.external.llm.registry import LLMModelSpec

T = TypeVar("T", bound=BaseModel)


class FallbackChainLLM(AgenticSearchLLMInterface):
    """LLM wrapper that chains multiple providers with automatic fallback.

    Explicitly implements AgenticSearchLLMInterface.
    Exposes the first (primary) provider's model_spec so token budgeting
    stays consistent.

    Tracks per-provider call counts and fallback events for analytics.

    On each structured_output() call:
    1. Skip providers whose circuit breaker is tripped (recently failed).
    2. Try remaining providers in order until one succeeds.
    3. Record success/failure in the circuit breaker for future calls.
    4. If ALL providers are tripped, try them anyway (oldest failure first)
       rather than returning an immediate error.
    """

    def __init__(
        self,
        providers: list[AgenticSearchLLMInterface],
        circuit_breaker: CircuitBreaker,
        logger: logging.Logger | logging.LoggerAdapter | None = None,
    ) -> None:
        """Initialize with an ordered list of LLM providers.

        Args:
            providers: Ordered list of providers to try (first = primary).
                Must contain at least one provider.
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
        """Cumulative fallback statistics for analytics.

        Returns a dict with:
        - total_calls: Total structured_output calls made.
        - fallback_count: Calls where the primary provider failed.
        - fallback_rate: Fraction of calls that required fallback (0.0-1.0).
        - calls_per_provider: Dict of provider_name -> call count.
        - primary_provider: Name of the primary provider.
        """
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
        """Generate structured output, falling through the provider chain.

        Skips providers whose circuit breaker is tripped. If all are tripped,
        tries them all anyway (best-effort). Records success/failure in the
        circuit breaker so subsequent requests benefit.

        Args:
            prompt: The user prompt.
            schema: Pydantic model class for the response.
            system_prompt: System prompt.

        Returns:
            Parsed response matching schema.

        Raises:
            RuntimeError: If all providers in the chain fail.
        """
        self._total_calls += 1

        # Partition providers into available vs tripped
        available: list[AgenticSearchLLMInterface] = []
        tripped: list[AgenticSearchLLMInterface] = []

        for provider in self._providers:
            key = provider.model_spec.api_model_name
            if await self._circuit_breaker.is_available(key):
                available.append(provider)
            else:
                self._logger.debug(f"[FallbackChainLLM] Skipping {key} (circuit breaker tripped)")
                tripped.append(provider)

        # If all providers are tripped, try them all as a last resort
        if not available:
            self._logger.warning(
                "[FallbackChainLLM] All providers tripped — trying all as last resort"
            )
            available = list(self._providers)

        return await self._try_providers(available, prompt, schema, system_prompt)

    async def _try_providers(
        self,
        providers: list[AgenticSearchLLMInterface],
        prompt: str,
        schema: type[T],
        system_prompt: str,
    ) -> T:
        """Try providers in order, recording success/failure in circuit breaker."""
        errors: list[tuple[str, Exception]] = []

        for i, provider in enumerate(providers):
            provider_name = provider.model_spec.api_model_name
            try:
                result = await provider.structured_output(prompt, schema, system_prompt)

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

            except RuntimeError as e:
                # Provider exhausted its retries — trip the circuit breaker
                await self._circuit_breaker.record_failure(provider_name)
                errors.append((provider_name, e))

                if i < len(providers) - 1:
                    next_name = providers[i + 1].model_spec.api_model_name
                    self._logger.warning(
                        f"[FallbackChainLLM] Provider {provider_name} failed: {e}. "
                        f"Trying next: {next_name}..."
                    )
                else:
                    self._logger.error(
                        f"[FallbackChainLLM] Last provider {provider_name} also failed: {e}"
                    )

        error_summary = "; ".join(f"{name}: {err}" for name, err in errors)
        raise RuntimeError(f"All {len(providers)} LLM providers failed. {error_summary}")

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
