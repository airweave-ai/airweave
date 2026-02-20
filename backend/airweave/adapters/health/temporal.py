"""Temporal health probe adapter."""

from __future__ import annotations

import time
from collections.abc import Callable

from temporalio.client import Client as TemporalClientType

from airweave.core.health.protocols import HealthProbe
from airweave.schemas.health import CheckStatus, DependencyCheck


class TemporalHealthProbe(HealthProbe):
    """Probes Temporal via the gRPC health check on its service client."""

    def __init__(self, get_client: Callable[[], TemporalClientType | None]) -> None:
        self._get_client = get_client

    @property
    def name(self) -> str:
        return "temporal"

    async def check(self) -> DependencyCheck:
        client = self._get_client()
        if client is None:
            return DependencyCheck(status=CheckStatus.skipped)
        start = time.perf_counter()
        await client.service_client.check_health()
        latency = (time.perf_counter() - start) * 1000
        return DependencyCheck(status=CheckStatus.up, latency_ms=round(latency, 2))
