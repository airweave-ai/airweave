"""Health protocols for dependency injection.

Defines ``HealthProbe`` (individual infrastructure check) and
``HealthServiceProtocol`` (readiness-check facade).
"""

from typing import Protocol, runtime_checkable

from airweave.schemas.health import DependencyCheck, ReadinessResponse


@runtime_checkable
class HealthProbe(Protocol):
    """Protocol for a single infrastructure health check.

    Implementations return a ``DependencyCheck`` on success and **raise**
    on failure.  The orchestrator handles timeouts and error sanitization,
    so probes can stay simple.

    The critical-vs-informational distinction is a deployment concern and
    lives in the wiring layer, not in the probe itself.
    """

    @property
    def name(self) -> str:
        """Human-readable identifier surfaced in the readiness response."""
        ...

    async def check(self) -> DependencyCheck:
        """Probe the dependency and return its status.

        Returns:
            A ``DependencyCheck`` with ``status=up`` and measured latency.

        Raises:
            Any exception on failure — the orchestrator will catch it.
        """
        ...


@runtime_checkable
class HealthServiceProtocol(Protocol):
    """Facade that orchestrates health probes and owns shutdown state."""

    @property
    def shutting_down(self) -> bool:
        """Whether the application is shutting down."""
        ...

    @shutting_down.setter
    def shutting_down(self, value: bool) -> None: ...

    async def check_readiness(self, *, debug: bool) -> ReadinessResponse:
        """Evaluate readiness by probing dependencies concurrently."""
        ...
