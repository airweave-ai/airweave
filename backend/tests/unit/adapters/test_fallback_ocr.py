"""Tests for FallbackOcrProvider with circuit breaker integration."""

from dataclasses import dataclass, field
from typing import Optional

import pytest

from airweave.adapters.circuit_breaker.fake import FakeCircuitBreaker
from airweave.adapters.ocr.fake import FakeOcrProvider
from airweave.adapters.ocr.fallback import FallbackOcrProvider
from airweave.core.protocols.ocr import OcrProvider


class TestProtocolConformance:
    def test_fallback_is_ocr_provider(self):
        fallback = FallbackOcrProvider(
            providers=[("fake", FakeOcrProvider())],
            circuit_breaker=FakeCircuitBreaker(),
        )
        assert isinstance(fallback, OcrProvider)


@dataclass
class Case:
    desc: str

    providers: list[tuple[str, FakeOcrProvider]]
    tripped_providers: list[str] = field(default_factory=list)

    expect_result: Optional[str] = "# Primary"
    expect_circuit_breaker_successes: list[str] = field(default_factory=list)
    expect_circuit_breaker_failures: list[str] = field(default_factory=list)


CASES = [
    Case(
        desc="uses first available provider",
        providers=[
            ("primary", FakeOcrProvider(default_markdown="# Primary")),
            ("secondary", FakeOcrProvider(default_markdown="# Secondary")),
        ],
        expect_result="# Primary",
        expect_circuit_breaker_successes=["primary"],
    ),
    Case(
        desc="falls back when primary fails",
        providers=[
            ("primary", FakeOcrProvider(should_raise=RuntimeError("down"))),
            ("secondary", FakeOcrProvider(default_markdown="# Secondary")),
        ],
        expect_result="# Secondary",
        expect_circuit_breaker_failures=["primary"],
        expect_circuit_breaker_successes=["secondary"],
    ),
    Case(
        desc="skips circuit-broken provider",
        providers=[
            ("primary", FakeOcrProvider(default_markdown="# Primary")),
            ("secondary", FakeOcrProvider(default_markdown="# Secondary")),
        ],
        tripped_providers=["primary"],
        expect_result="# Secondary",
        expect_circuit_breaker_successes=["secondary"],
    ),
    Case(
        desc="skips multiple circuit-broken providers",
        providers=[
            ("first", FakeOcrProvider(should_raise=RuntimeError("down"))),
            ("second", FakeOcrProvider(should_raise=RuntimeError("down"))),
            ("third", FakeOcrProvider(default_markdown="# Third")),
        ],
        tripped_providers=["first", "second"],
        expect_result="# Third",
        expect_circuit_breaker_successes=["third"],
    ),
    Case(
        desc="returns None when all providers fail",
        providers=[
            ("a", FakeOcrProvider(should_raise=RuntimeError("down"))),
            ("b", FakeOcrProvider(should_raise=RuntimeError("down"))),
        ],
        expect_result=None,
        expect_circuit_breaker_failures=["a", "b"],
    ),
    Case(
        desc="returns None when all providers circuit-broken",
        providers=[
            ("primary", FakeOcrProvider(default_markdown="# Primary")),
        ],
        tripped_providers=["primary"],
        expect_result=None,
    ),
    Case(
        desc="single provider success records circuit breaker success",
        providers=[
            ("only", FakeOcrProvider(default_markdown="# Only")),
        ],
        expect_result="# Only",
        expect_circuit_breaker_successes=["only"],
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_fallback_ocr(case: Case):
    circuit_breaker = FakeCircuitBreaker()
    for key in case.tripped_providers:
        await circuit_breaker.record_failure(key)
    circuit_breaker.failures.clear()

    fallback = FallbackOcrProvider(providers=case.providers, circuit_breaker=circuit_breaker)
    result = await fallback.convert_batch(["/tmp/doc.pdf"])

    assert result.get("/tmp/doc.pdf") == case.expect_result
    assert circuit_breaker.successes == case.expect_circuit_breaker_successes
    assert circuit_breaker.failures == case.expect_circuit_breaker_failures


def test_rejects_empty_providers():
    with pytest.raises(ValueError, match="At least one"):
        FallbackOcrProvider(providers=[], circuit_breaker=FakeCircuitBreaker())
