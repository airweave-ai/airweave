"""Tests for FallbackOcrProvider with circuit breaker integration.

Uses table-driven tests: each case is a dataclass row describing
fakes configuration, input, and expected output. The test runner
is generic boilerplate written once.
"""

from dataclasses import dataclass, field
from typing import Optional

import pytest

from airweave.adapters.circuit_breaker.fake import FakeCircuitBreaker
from airweave.adapters.ocr.fake import FakeOcrProvider
from airweave.adapters.ocr.fallback import FallbackOcrProvider
from airweave.core.protocols.ocr import OcrProvider

FILES = ["/tmp/doc.pdf", "/tmp/img.png"]


# ---------------------------------------------------------------------------
# Protocol conformance (not table-driven — one-off check)
# ---------------------------------------------------------------------------


class TestProtocolConformance:
    def test_fallback_is_ocr_provider(self):
        fb = FallbackOcrProvider(
            providers=[("fake", FakeOcrProvider())],
            circuit_breaker=FakeCircuitBreaker(),
        )
        assert isinstance(fb, OcrProvider)


# ---------------------------------------------------------------------------
# Table-driven tests
# ---------------------------------------------------------------------------


@dataclass
class Case:
    """One row in the test table."""

    desc: str

    # Fakes — configure provider behavior
    providers: list[tuple[str, FakeOcrProvider]]
    tripped: list[str] = field(default_factory=list)

    # Input
    files: list[str] = field(default_factory=lambda: FILES.copy())

    # Expected output
    expect_markdown: Optional[dict[str, Optional[str]]] = None
    expect_all_none: bool = False

    # Expected circuit breaker side effects
    expect_successes: list[str] = field(default_factory=list)
    expect_failures: list[str] = field(default_factory=list)
    expect_tripped: list[str] = field(default_factory=list)

    # Expected call counts (provider_key → expected count)
    expect_call_counts: dict[str, int] = field(default_factory=dict)


CASES = [
    # ---- Happy path ----
    Case(
        desc="uses first available provider",
        providers=[
            ("primary", FakeOcrProvider(default_markdown="# Primary")),
            ("secondary", FakeOcrProvider(default_markdown="# Secondary")),
        ],
        expect_markdown={"/tmp/doc.pdf": "# Primary"},
        expect_successes=["primary"],
        expect_call_counts={"primary": 1, "secondary": 0},
    ),
    Case(
        desc="records success on single provider",
        providers=[
            ("primary", FakeOcrProvider(default_markdown="# OK")),
        ],
        expect_successes=["primary"],
    ),
    # ---- Failover ----
    Case(
        desc="falls back when primary fails",
        providers=[
            ("primary", FakeOcrProvider(should_raise=RuntimeError("down"))),
            ("secondary", FakeOcrProvider(default_markdown="# Secondary")),
        ],
        expect_markdown={"/tmp/doc.pdf": "# Secondary"},
        expect_failures=["primary"],
        expect_successes=["secondary"],
        expect_tripped=["primary"],
    ),
    Case(
        desc="failing provider is still called before fallback",
        providers=[
            ("failing", FakeOcrProvider(should_raise=RuntimeError("down"))),
            ("secondary", FakeOcrProvider(default_markdown="# Secondary")),
        ],
        expect_call_counts={"failing": 1, "secondary": 1},
    ),
    # ---- Circuit breaker skipping ----
    Case(
        desc="skips circuit-broken provider",
        providers=[
            ("primary", FakeOcrProvider(default_markdown="# Primary")),
            ("secondary", FakeOcrProvider(default_markdown="# Secondary")),
        ],
        tripped=["primary"],
        expect_markdown={"/tmp/doc.pdf": "# Secondary"},
        expect_call_counts={"primary": 0, "secondary": 1},
        expect_successes=["secondary"],
    ),
    Case(
        desc="skips multiple circuit-broken providers",
        providers=[
            ("first", FakeOcrProvider(should_raise=RuntimeError("down"))),
            ("second", FakeOcrProvider(should_raise=RuntimeError("down"))),
            ("third", FakeOcrProvider(default_markdown="# Third")),
        ],
        tripped=["first", "second"],
        expect_markdown={"/tmp/doc.pdf": "# Third"},
    ),
    # ---- All providers exhausted ----
    Case(
        desc="returns None when all providers fail",
        providers=[
            ("a", FakeOcrProvider(should_raise=RuntimeError("down"))),
            ("b", FakeOcrProvider(should_raise=RuntimeError("down"))),
        ],
        expect_all_none=True,
        expect_failures=["a", "b"],
    ),
    Case(
        desc="returns None when all circuit-broken",
        providers=[
            ("primary", FakeOcrProvider(default_markdown="# Primary")),
        ],
        tripped=["primary"],
        expect_all_none=True,
        expect_call_counts={"primary": 0},
    ),
    # ---- Edge cases ----
    Case(
        desc="empty file list",
        providers=[
            ("primary", FakeOcrProvider(default_markdown="# Primary")),
        ],
        files=[],
        expect_markdown={},
        expect_call_counts={"primary": 1},
    ),
]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.desc)
@pytest.mark.asyncio
async def test_fallback_ocr(case: Case):
    # Setup
    cb = FakeCircuitBreaker()
    for key in case.tripped:
        await cb.record_failure(key)
    cb.failures.clear()  # pre-trip is setup, not an observed failure

    fb = FallbackOcrProvider(providers=case.providers, circuit_breaker=cb)

    # Act
    result = await fb.convert_batch(case.files)

    # Assert — expected results
    if case.expect_markdown is not None:
        for path, expected in case.expect_markdown.items():
            assert result.get(path) == expected, f"mismatch for {path}"

    if case.expect_all_none:
        assert all(v is None for v in result.values()), f"expected all None, got {result}"

    # Assert — circuit breaker side effects
    if case.expect_successes:
        assert cb.successes == case.expect_successes

    if case.expect_failures:
        assert cb.failures == case.expect_failures

    for key in case.expect_tripped:
        assert cb.is_tripped(key), f"expected '{key}' to be tripped"

    # Assert — call counts
    providers_by_key = {key: prov for key, prov in case.providers}
    for key, expected_count in case.expect_call_counts.items():
        actual = providers_by_key[key].call_count
        assert actual == expected_count, (
            f"provider '{key}': expected {expected_count} calls, got {actual}"
        )


# ---------------------------------------------------------------------------
# Construction validation (not table-driven — uses pytest.raises)
# ---------------------------------------------------------------------------


def test_rejects_empty_providers():
    with pytest.raises(ValueError, match="At least one"):
        FallbackOcrProvider(providers=[], circuit_breaker=FakeCircuitBreaker())
