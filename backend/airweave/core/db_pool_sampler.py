"""Background sampler that pushes DB connection pool stats into gauges.

A lightweight ``asyncio.Task`` polls ``pool.checkedout()`` /
``checkedin()`` / ``overflow()`` / ``size()`` every *interval* seconds
and forwards the values to a ``DbPoolMetrics`` implementation.

The loop tolerates transient pool errors (e.g. during shutdown) by
logging a warning and continuing rather than killing the task.
"""

import asyncio
import logging

from airweave.core.protocols.metrics import DbPool, DbPoolMetrics

logger = logging.getLogger(__name__)


class DbPoolSampler:
    """Periodically sample a SQLAlchemy pool and push to metrics.

    Args:
        pool: A SQLAlchemy pool exposing ``size()``, ``checkedout()``,
            ``checkedin()``, and ``overflow()`` methods.
        metrics: Any object satisfying the ``DbPoolMetrics`` protocol.
        interval: Seconds between samples (default 5.0).
    """

    def __init__(
        self,
        pool: DbPool,
        metrics: DbPoolMetrics,
        interval: float = 5.0,
    ) -> None:
        self._pool = pool
        self._metrics = metrics
        self._interval = interval
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Create the background sampling task."""
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        """Cancel the background task and wait for it to finish."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        """Sample pool stats and push to metrics on each tick."""
        while True:
            try:
                self._metrics.update(
                    pool_size=self._pool.size(),
                    checked_out=self._pool.checkedout(),
                    checked_in=self._pool.checkedin(),
                    overflow=self._pool.overflow(),
                )
            except Exception:
                logger.warning("Failed to sample DB pool metrics", exc_info=True)
            await asyncio.sleep(self._interval)
