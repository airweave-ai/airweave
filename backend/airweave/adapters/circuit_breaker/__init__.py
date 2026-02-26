"""Circuit breaker adapters."""

from airweave.adapters.circuit_breaker.fake import FakeCircuitBreaker
from airweave.adapters.circuit_breaker.in_memory import InMemoryCircuitBreaker

__all__ = ["InMemoryCircuitBreaker", "FakeCircuitBreaker"]
