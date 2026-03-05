"""CircuitBreaker protocol for provider failover caching.

When an external provider (e.g., an LLM API) fails, the circuit breaker
records the failure and skips that provider for a cooldown period. This
prevents wasting time and retries on a provider that is known to be down.

After the cooldown expires, the provider is tried again ("half-open" state).
A successful call clears the failure state immediately.

Usage:
    # In a fallback chain
    if await circuit_breaker.is_available("cerebras/zai-glm-4.7"):
        try:
            result = await provider.call(...)
            await circuit_breaker.record_success("cerebras/zai-glm-4.7")
        except ProviderError:
            await circuit_breaker.record_failure("cerebras/zai-glm-4.7")
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class CircuitBreaker(Protocol):
    """Protocol for provider failover caching.

    Implementations track which providers have recently failed and should
    be skipped. The cooldown duration is implementation-defined.
    """

    async def is_available(self, provider_key: str) -> bool:
        """Check if a provider is available (not in cooldown).

        Returns True if the provider has no recent failure, or if the
        cooldown period has expired. Thread-safe.

        Args:
            provider_key: Unique identifier for the provider
                (e.g., api_model_name).

        Returns:
            True if the provider should be tried, False if it should be skipped.
        """
        ...

    async def record_failure(self, provider_key: str) -> None:
        """Mark a provider as failed, starting the cooldown period.

        Subsequent calls to is_available() for this provider will return
        False until the cooldown expires. Thread-safe.

        Args:
            provider_key: Unique identifier for the provider.
        """
        ...

    async def record_success(self, provider_key: str) -> None:
        """Clear failure state for a provider.

        Called after a successful call to immediately make the provider
        available again (exits half-open state). Thread-safe.

        Args:
            provider_key: Unique identifier for the provider.
        """
        ...
