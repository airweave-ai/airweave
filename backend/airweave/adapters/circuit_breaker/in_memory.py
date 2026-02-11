"""In-memory circuit breaker implementation.

Tracks provider failures in a dict with TTL-based expiry. Suitable for
single-process deployments. For multi-process (e.g., Kubernetes with
multiple replicas), swap with a Redis-backed implementation.

Thread-safe via asyncio.Lock — safe for concurrent coroutines within
a single event loop.
"""

from __future__ import annotations

import asyncio
import time

from airweave.core.logging import logger


class InMemoryCircuitBreaker:
    """In-memory implementation of the CircuitBreaker protocol.

    Stores failure timestamps in a dict keyed by provider_key.
    A provider is considered unavailable for `cooldown_seconds` after
    a failure is recorded. After the cooldown, is_available() returns
    True again (half-open). A successful call clears the failure state.

    Attributes:
        cooldown_seconds: How long a tripped provider stays unavailable.
    """

    DEFAULT_COOLDOWN_SECONDS = 60.0

    def __init__(self, cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS) -> None:
        """Initialize the in-memory circuit breaker.

        Args:
            cooldown_seconds: Seconds to skip a provider after failure.
                Defaults to 60 seconds.
        """
        self._cooldown = cooldown_seconds
        self._failures: dict[str, float] = {}  # provider_key → monotonic timestamp
        self._lock = asyncio.Lock()

    async def is_available(self, provider_key: str) -> bool:
        """Check if a provider is available (not in cooldown).

        If the cooldown has expired, the failure entry is cleaned up and
        the provider is considered available again (half-open state).

        Args:
            provider_key: Unique identifier for the provider.

        Returns:
            True if the provider should be tried.
        """
        async with self._lock:
            failure_time = self._failures.get(provider_key)
            if failure_time is None:
                return True

            elapsed = time.monotonic() - failure_time
            if elapsed >= self._cooldown:
                # Cooldown expired — clear and allow retry (half-open)
                del self._failures[provider_key]
                logger.info(
                    f"[CircuitBreaker] Cooldown expired for '{provider_key}' "
                    f"after {elapsed:.0f}s, allowing retry"
                )
                return True

            return False

    async def record_failure(self, provider_key: str) -> None:
        """Mark a provider as failed, starting the cooldown.

        Args:
            provider_key: Unique identifier for the provider.
        """
        async with self._lock:
            self._failures[provider_key] = time.monotonic()
            logger.warning(
                f"[CircuitBreaker] Provider '{provider_key}' tripped — "
                f"skipping for {self._cooldown:.0f}s"
            )

    async def record_success(self, provider_key: str) -> None:
        """Clear failure state for a provider (successful recovery).

        Args:
            provider_key: Unique identifier for the provider.
        """
        async with self._lock:
            if provider_key in self._failures:
                del self._failures[provider_key]
                logger.info(
                    f"[CircuitBreaker] Provider '{provider_key}' recovered, clearing failure state"
                )

    @property
    def tripped_providers(self) -> dict[str, float]:
        """Snapshot of currently tripped providers and their failure times.

        Useful for debugging / health endpoints. Not locked — read is
        approximate but safe for diagnostics.

        Returns:
            Dict of provider_key → seconds since failure.
        """
        now = time.monotonic()
        return {key: now - ts for key, ts in self._failures.items() if now - ts < self._cooldown}
