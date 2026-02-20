"""Postgres health probe adapter."""

import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from airweave.core.health.protocols import HealthProbe
from airweave.schemas.health import CheckStatus, DependencyCheck


class PostgresHealthProbe(HealthProbe):
    """Probes Postgres by executing ``SELECT 1`` on a dedicated engine."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @property
    def name(self) -> str:
        return "postgres"

    async def check(self) -> DependencyCheck:
        start = time.perf_counter()
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        latency = (time.perf_counter() - start) * 1000
        return DependencyCheck(status=CheckStatus.up, latency_ms=round(latency, 2))
