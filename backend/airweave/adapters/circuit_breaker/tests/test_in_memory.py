"""Unit tests for InMemoryCircuitBreaker — cooldown, half-open, and recovery."""

import time
from unittest.mock import patch

import pytest

from airweave.adapters.circuit_breaker.in_memory import InMemoryCircuitBreaker

PROVIDER = "cerebras/llama-4-scout"


class TestInitialState:
    @pytest.mark.asyncio
    async def test_available_by_default(self):
        cb = InMemoryCircuitBreaker()
        assert await cb.is_available(PROVIDER) is True

    @pytest.mark.asyncio
    async def test_no_tripped_providers_initially(self):
        cb = InMemoryCircuitBreaker()
        assert cb.tripped_providers == {}


class TestRecordFailure:
    @pytest.mark.asyncio
    async def test_failure_trips_provider(self):
        cb = InMemoryCircuitBreaker()

        await cb.record_failure(PROVIDER)

        assert await cb.is_available(PROVIDER) is False

    @pytest.mark.asyncio
    async def test_failure_shows_in_tripped(self):
        cb = InMemoryCircuitBreaker()

        await cb.record_failure(PROVIDER)

        tripped = cb.tripped_providers
        assert PROVIDER in tripped
        assert tripped[PROVIDER] < 1.0  # just recorded, should be <1s ago

    @pytest.mark.asyncio
    async def test_other_provider_unaffected(self):
        cb = InMemoryCircuitBreaker()

        await cb.record_failure(PROVIDER)

        assert await cb.is_available("openai/gpt-4") is True


class TestCooldownExpiry:
    @pytest.mark.asyncio
    async def test_available_after_cooldown(self):
        cb = InMemoryCircuitBreaker(cooldown_seconds=0.05)

        await cb.record_failure(PROVIDER)
        assert await cb.is_available(PROVIDER) is False

        # Simulate time passing beyond cooldown
        cb._failures[PROVIDER] = time.monotonic() - 1.0

        assert await cb.is_available(PROVIDER) is True

    @pytest.mark.asyncio
    async def test_cooldown_clears_failure_entry(self):
        cb = InMemoryCircuitBreaker(cooldown_seconds=0.05)

        await cb.record_failure(PROVIDER)
        cb._failures[PROVIDER] = time.monotonic() - 1.0

        await cb.is_available(PROVIDER)

        assert PROVIDER not in cb._failures


class TestRecordSuccess:
    @pytest.mark.asyncio
    async def test_success_clears_failure(self):
        cb = InMemoryCircuitBreaker()

        await cb.record_failure(PROVIDER)
        assert await cb.is_available(PROVIDER) is False

        await cb.record_success(PROVIDER)
        assert await cb.is_available(PROVIDER) is True

    @pytest.mark.asyncio
    async def test_success_noop_when_not_tripped(self):
        cb = InMemoryCircuitBreaker()

        await cb.record_success(PROVIDER)

        assert await cb.is_available(PROVIDER) is True
        assert PROVIDER not in cb._failures


class TestMultipleProviders:
    @pytest.mark.asyncio
    async def test_independent_cooldowns(self):
        cb = InMemoryCircuitBreaker()
        provider_a = "provider-a"
        provider_b = "provider-b"

        await cb.record_failure(provider_a)
        await cb.record_failure(provider_b)

        await cb.record_success(provider_a)

        assert await cb.is_available(provider_a) is True
        assert await cb.is_available(provider_b) is False

    @pytest.mark.asyncio
    async def test_tripped_providers_only_shows_active(self):
        cb = InMemoryCircuitBreaker(cooldown_seconds=60)

        await cb.record_failure("a")
        await cb.record_failure("b")
        await cb.record_success("a")

        tripped = cb.tripped_providers
        assert "a" not in tripped
        assert "b" in tripped


class TestCustomCooldown:
    @pytest.mark.asyncio
    async def test_respects_custom_cooldown(self):
        cb = InMemoryCircuitBreaker(cooldown_seconds=300)

        await cb.record_failure(PROVIDER)
        # Set failure to 100s ago — still within 300s cooldown
        cb._failures[PROVIDER] = time.monotonic() - 100

        assert await cb.is_available(PROVIDER) is False

    @pytest.mark.asyncio
    async def test_default_cooldown_is_60(self):
        cb = InMemoryCircuitBreaker()
        assert cb._cooldown == 60.0
