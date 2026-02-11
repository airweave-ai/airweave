"""Tests for FallbackOcrProvider with circuit breaker integration."""

import pytest

from airweave.adapters.circuit_breaker.fake import FakeCircuitBreaker
from airweave.adapters.ocr.fake import FakeOcrProvider
from airweave.adapters.ocr.fallback import FallbackOcrProvider
from airweave.core.protocols.ocr import OcrProvider

FILES = ["/tmp/doc.pdf", "/tmp/img.png"]

class TestProtocolConformance:
    def test_fallback_is_ocr_provider(self):
        fb = FallbackOcrProvider(
            providers=[("fake", FakeOcrProvider())],
            circuit_breaker=FakeCircuitBreaker(),
        )
        assert isinstance(fb, OcrProvider)


class TestFallbackOcrProvider:
    @pytest.fixture
    def cb(self):
        return FakeCircuitBreaker()

    @pytest.fixture
    def primary(self):
        return FakeOcrProvider(default_markdown="# Primary")

    @pytest.fixture
    def secondary(self):
        return FakeOcrProvider(default_markdown="# Secondary")

    @pytest.fixture
    def failing(self):
        return FakeOcrProvider(should_raise=RuntimeError("provider down"))

    # ---- Happy path ----

    @pytest.mark.asyncio
    async def test_uses_first_available_provider(self, cb, primary, secondary):
        fb = FallbackOcrProvider(
            providers=[("primary", primary), ("secondary", secondary)],
            circuit_breaker=cb,
        )
        results = await fb.convert_batch(FILES)

        assert results[FILES[0]] == "# Primary"
        assert primary.call_count == 1
        assert secondary.call_count == 0

    @pytest.mark.asyncio
    async def test_records_success_on_primary(self, cb, primary):
        fb = FallbackOcrProvider(
            providers=[("primary", primary)],
            circuit_breaker=cb,
        )
        await fb.convert_batch(FILES)

        assert cb.successes == ["primary"]

    # ---- Failover ----

    @pytest.mark.asyncio
    async def test_falls_back_on_failure(self, cb, failing, secondary):
        fb = FallbackOcrProvider(
            providers=[("failing", failing), ("secondary", secondary)],
            circuit_breaker=cb,
        )
        results = await fb.convert_batch(FILES)

        assert results[FILES[0]] == "# Secondary"
        assert cb.is_tripped("failing")
        assert cb.successes == ["secondary"]

    @pytest.mark.asyncio
    async def test_records_failure_then_success(self, cb, failing, secondary):
        fb = FallbackOcrProvider(
            providers=[("failing", failing), ("secondary", secondary)],
            circuit_breaker=cb,
        )
        await fb.convert_batch(FILES)

        assert cb.failures == ["failing"]
        assert cb.successes == ["secondary"]

    @pytest.mark.asyncio
    async def test_failing_provider_still_called(self, cb, failing, secondary):
        """Failing provider is attempted (call recorded) before fallback."""
        fb = FallbackOcrProvider(
            providers=[("failing", failing), ("secondary", secondary)],
            circuit_breaker=cb,
        )
        await fb.convert_batch(FILES)

        assert failing.call_count == 1
        assert secondary.call_count == 1

    # ---- Circuit breaker skipping ----

    @pytest.mark.asyncio
    async def test_skips_circuit_broken_provider(self, cb, primary, secondary):
        await cb.record_failure("primary")

        fb = FallbackOcrProvider(
            providers=[("primary", primary), ("secondary", secondary)],
            circuit_breaker=cb,
        )
        results = await fb.convert_batch(FILES)

        assert results[FILES[0]] == "# Secondary"
        assert primary.call_count == 0
        assert secondary.call_count == 1

    @pytest.mark.asyncio
    async def test_skips_multiple_circuit_broken_providers(self, cb, secondary):
        await cb.record_failure("first")
        await cb.record_failure("second")

        fb = FallbackOcrProvider(
            providers=[
                ("first", FakeOcrProvider(should_raise=RuntimeError("down"))),
                ("second", FakeOcrProvider(should_raise=RuntimeError("down"))),
                ("secondary", secondary),
            ],
            circuit_breaker=cb,
        )
        results = await fb.convert_batch(FILES)

        assert results[FILES[0]] == "# Secondary"

    # ---- All providers exhausted ----

    @pytest.mark.asyncio
    async def test_returns_none_when_all_fail(self, cb):
        fb = FallbackOcrProvider(
            providers=[
                ("a", FakeOcrProvider(should_raise=RuntimeError("down"))),
                ("b", FakeOcrProvider(should_raise=RuntimeError("down"))),
            ],
            circuit_breaker=cb,
        )
        results = await fb.convert_batch(FILES)

        assert all(v is None for v in results.values())
        assert cb.failure_count == 2

    @pytest.mark.asyncio
    async def test_returns_none_when_all_circuit_broken(self, cb, primary):
        await cb.record_failure("primary")

        fb = FallbackOcrProvider(
            providers=[("primary", primary)],
            circuit_breaker=cb,
        )
        results = await fb.convert_batch(FILES)

        assert all(v is None for v in results.values())
        assert primary.call_count == 0

    # ---- Edge cases ----

    def test_rejects_empty_providers(self, cb):
        with pytest.raises(ValueError, match="At least one"):
            FallbackOcrProvider(providers=[], circuit_breaker=cb)

    @pytest.mark.asyncio
    async def test_empty_file_list(self, cb, primary):
        fb = FallbackOcrProvider(
            providers=[("primary", primary)],
            circuit_breaker=cb,
        )
        results = await fb.convert_batch([])

        assert results == {}
        assert primary.call_count == 1
