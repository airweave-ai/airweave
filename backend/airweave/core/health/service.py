"""HealthService — readiness-check facade.

Absorbs the orchestrator logic that previously lived in ``core.health``
(``check_readiness``, ``_run_probe``, ``_sanitize_error``) and owns the
``shutting_down`` flag that was previously stored on ``app.state``.
"""

import asyncio
import errno
from collections.abc import Sequence

from airweave.core.health.protocols import HealthProbe, HealthServiceProtocol
from airweave.schemas.health import CheckStatus, DependencyCheck, ReadinessResponse


class HealthService(HealthServiceProtocol):
    """Concrete ``HealthServiceProtocol`` implementation.

    Constructed by the container factory with critical and informational
    probe sequences.
    """

    def __init__(
        self,
        *,
        critical: Sequence[HealthProbe],
        informational: Sequence[HealthProbe],
        timeout: float = 5.0,
    ) -> None:
        """Initialise with critical and informational probe sequences."""
        self._critical = critical
        self._informational = informational
        self._timeout = timeout
        self._shutting_down = False

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
        """Evaluate readiness by probing dependencies concurrently.

        *critical* probes gate the HTTP status — any failure flips the
        response to ``not_ready``.  *informational* probes are surfaced
        in the response body but do not affect the status code.
        """
        all_probes = [*self._critical, *self._informational]
        critical_names = {p.name for p in self._critical}

        skipped = DependencyCheck(status=CheckStatus.skipped)

        if self._shutting_down:
            return ReadinessResponse(
                status="not_ready",
                checks={p.name: skipped for p in all_probes},
            )

        results = await asyncio.gather(
            *(self._run_probe(p) for p in all_probes),
            return_exceptions=True,
        )

        checks: dict[str, DependencyCheck] = {}
        ready = True

        for entry in results:
            if isinstance(entry, BaseException):
                continue

            name, outcome = entry

            if isinstance(outcome, BaseException):
                checks[name] = DependencyCheck(
                    status=CheckStatus.down,
                    error=self._sanitize_error(outcome, debug=debug),
                )
                if name in critical_names:
                    ready = False
            else:
                checks[name] = outcome

        return ReadinessResponse(
            status="ready" if ready else "not_ready",
            checks=checks,
        )

    # -- helpers -------------------------------------------------------------

    async def _run_probe(self, probe: HealthProbe) -> tuple[str, DependencyCheck | Exception]:
        """Execute a single probe with a timeout."""
        try:
            result = await asyncio.wait_for(probe.check(), timeout=self._timeout)
        except Exception as exc:
            return probe.name, exc
        return probe.name, result

    @staticmethod
    def _sanitize_error(exc: Exception, *, debug: bool) -> str:
        """Return an error string safe for external consumption.

        In debug mode the full exception text is returned.  In production
        the message is reduced to a generic category so that internal
        hostnames, ports, or stack traces are never leaked.
        """
        if debug:
            return str(exc)

        if isinstance(exc, asyncio.TimeoutError):
            return "timeout"

        os_err = getattr(exc, "errno", None) or (
            getattr(exc.__cause__, "errno", None) if exc.__cause__ else None
        )
        if os_err == errno.ECONNREFUSED:
            return "connection_refused"

        return "unavailable"
