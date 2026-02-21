"""Fakes for health probes and service — used in unit tests."""

import asyncio

from airweave.core.health.protocols import HealthProbe, HealthServiceProtocol
from airweave.schemas.health import CheckStatus, DependencyCheck, ReadinessResponse


class FakeHealthService(HealthServiceProtocol):
    """In-memory fake satisfying the ``HealthService`` protocol.

    Records calls and supports canned responses via ``set_response()``.
    """

    def __init__(self) -> None:
        """Initialise with a default ``ready`` canned response."""
        self._shutting_down = False
        self._response = ReadinessResponse(
            status="ready",
            checks={"fake": DependencyCheck(status=CheckStatus.up)},
        )
        self.check_readiness_calls: list[dict[str, bool]] = []

    # -- shutdown flag -------------------------------------------------------

    @property
    def shutting_down(self) -> bool:
        """Whether the application is shutting down."""
        return self._shutting_down

    @shutting_down.setter
    def shutting_down(self, value: bool) -> None:
        self._shutting_down = value

    # -- readiness check -----------------------------------------------------

    async def check_readiness(self, *, debug: bool) -> ReadinessResponse:
        """Return the canned response and record the call."""
        self.check_readiness_calls.append({"debug": debug})
        return self._response

    # -- test helpers --------------------------------------------------------

    def set_response(self, response: ReadinessResponse) -> None:
        """Set the canned response returned by ``check_readiness``."""
        self._response = response


# ---------------------------------------------------------------------------
# Fake probes — satisfy ``HealthProbe`` for orchestrator-level tests
# ---------------------------------------------------------------------------


class FakeProbe(HealthProbe):
    """Configurable probe that succeeds with a given latency."""

    def __init__(self, name: str, *, latency_ms: float = 1.0) -> None:
        """Create a probe that reports ``up`` with *latency_ms*."""
        self._name = name
        self._latency_ms = latency_ms

    @property
    def name(self) -> str:
        """Human-readable probe identifier."""
        return self._name

    async def check(self) -> DependencyCheck:
        """Return an ``up`` check with the configured latency."""
        return DependencyCheck(status=CheckStatus.up, latency_ms=self._latency_ms)


class FakeFailingProbe(HealthProbe):
    """Probe that always raises the given exception."""

    def __init__(self, name: str, exc: Exception) -> None:
        """Create a probe that raises *exc* on every check."""
        self._name = name
        self._exc = exc

    @property
    def name(self) -> str:
        """Human-readable probe identifier."""
        return self._name

    async def check(self) -> DependencyCheck:
        """Raise the stored exception."""
        raise self._exc


class FakeSlowProbe(HealthProbe):
    """Probe that blocks longer than the orchestrator timeout."""

    def __init__(self, name: str, delay: float = 10.0) -> None:
        """Create a probe that sleeps for *delay* seconds."""
        self._name = name
        self._delay = delay

    @property
    def name(self) -> str:
        """Human-readable probe identifier."""
        return self._name

    async def check(self) -> DependencyCheck:
        """Sleep for the configured delay, then return ``up``."""
        await asyncio.sleep(self._delay)
        return DependencyCheck(status=CheckStatus.up)


class FakeSkippedProbe(HealthProbe):
    """Probe that returns ``CheckStatus.skipped``."""

    def __init__(self, name: str) -> None:
        """Create a probe that always reports ``skipped``."""
        self._name = name

    @property
    def name(self) -> str:
        """Human-readable probe identifier."""
        return self._name

    async def check(self) -> DependencyCheck:
        """Return a ``skipped`` check."""
        return DependencyCheck(status=CheckStatus.skipped)
