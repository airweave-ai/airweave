"""Fake circuit breaker for testing.

Records availability decisions and allows manual control of provider
state without real cooldown timers.
"""


class FakeCircuitBreaker:
    """Test implementation of CircuitBreaker.

    Tracks failures in a set and exposes helpers for assertions.
    No real cooldown — providers stay tripped until manually cleared
    via record_success() or clear().

    Usage:
        fake = FakeCircuitBreaker()
        await some_operation(circuit_breaker=fake)

        # Assert a provider was tripped
        assert fake.is_tripped("cerebras/zai-glm-4.7")
        assert fake.failure_count == 1
    """

    def __init__(self) -> None:
        """Initialize with empty state."""
        self._tripped: set[str] = set()
        self.failures: list[str] = []  # ordered log of all record_failure calls
        self.successes: list[str] = []  # ordered log of all record_success calls

    async def is_available(self, provider_key: str) -> bool:
        """Return False if the provider has been tripped."""
        return provider_key not in self._tripped

    async def record_failure(self, provider_key: str) -> None:
        """Mark provider as tripped and log the failure."""
        self._tripped.add(provider_key)
        self.failures.append(provider_key)

    async def record_success(self, provider_key: str) -> None:
        """Clear tripped state and log the success."""
        self._tripped.discard(provider_key)
        self.successes.append(provider_key)

    # Test helpers

    def is_tripped(self, provider_key: str) -> bool:
        """Check if a provider is currently tripped."""
        return provider_key in self._tripped

    @property
    def failure_count(self) -> int:
        """Total number of failures recorded (including duplicates)."""
        return len(self.failures)

    @property
    def success_count(self) -> int:
        """Total number of successes recorded."""
        return len(self.successes)

    def clear(self) -> None:
        """Reset all state."""
        self._tripped.clear()
        self.failures.clear()
        self.successes.clear()
