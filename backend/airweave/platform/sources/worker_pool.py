"""Bounded async worker pool with optional token-bucket rate limiting.

Provides two APIs:
  - ``pool.map(items, worker)``  — high-level: process an iterable through
    a fixed-size pool of workers, yielding results with backpressure.
  - ``async with pool.acquire()`` — low-level: acquire a concurrency slot
    and (optionally) a rate-limit token before executing a single call.

Designed to replace the ad-hoc concurrency patterns scattered across source
connectors (raw semaphores, inline producer/consumer pools, fully sequential
loops) with one reusable, injectable primitive.
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterable,
    Callable,
    Dict,
    Iterable,
    Optional,
    Union,
)

from airweave.core.logging import logger as _default_logger
from airweave.platform.entities._base import BaseEntity


class _TokenBucket:
    """Async token-bucket rate limiter.

    Refills at ``rate`` tokens/sec up to ``burst`` capacity.
    Callers that exceed the bucket "borrow" tokens (go negative)
    and sleep proportionally, ensuring correct spacing without
    serialising all acquisitions behind the lock.
    """

    __slots__ = ("_rate", "_burst", "_tokens", "_last_refill", "_lock")

    def __init__(self, rate: float, burst: int) -> None:
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Block until a token is available (or borrow + sleep)."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_refill = now

            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return

            wait_time = (1.0 - self._tokens) / self._rate
            self._tokens -= 1.0  # borrow — may go further negative

        await asyncio.sleep(wait_time)


class WorkerPool:
    """Bounded async worker pool with optional token-bucket rate limiting.

    Combines:
      - **Concurrency cap** (``max_workers``): limits in-flight tasks via a
        fixed pool (``map``) or semaphore (``acquire``).
      - **Rate cap** (``max_rps``): token-bucket that spaces requests to stay
        under the target requests-per-second.
      - **Backpressure** (``max_queue_size``): bounded result queue prevents
        unbounded memory growth when workers outpace consumers.

    Examples::

        # High-level: concurrent entity generation
        pool = WorkerPool(max_workers=15, max_rps=30.0, logger=self.logger)
        async for entity in pool.map(file_listing, self._process_file):
            yield entity

        # Low-level: throttled individual API calls
        pool = WorkerPool(max_workers=5, max_rps=10.0)
        async with pool.acquire():
            resp = await client.get(url, headers=headers)
    """

    def __init__(
        self,
        max_workers: int = 10,
        max_rps: Optional[float] = None,
        burst: Optional[int] = None,
        max_queue_size: int = 100,
        logger: Any = None,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")

        self._max_workers = max_workers
        self._max_queue_size = max_queue_size
        self._semaphore = asyncio.Semaphore(max_workers)
        self._logger = logger or _default_logger

        self._bucket: Optional[_TokenBucket] = None
        if max_rps is not None and max_rps > 0:
            effective_burst = burst if burst is not None else max(1, int(max_rps))
            self._bucket = _TokenBucket(rate=max_rps, burst=effective_burst)

    @property
    def max_workers(self) -> int:
        return self._max_workers

    @property
    def max_rps(self) -> Optional[float]:
        return self._bucket._rate if self._bucket else None

    # ------------------------------------------------------------------
    # Low-level API
    # ------------------------------------------------------------------

    @asynccontextmanager
    async def acquire(self):
        """Acquire a worker slot and (optionally) a rate-limit token.

        Blocks until both a concurrency slot and a rate token are
        available, then yields control to the caller.

        Usage::

            async with pool.acquire():
                resp = await client.get(url)
        """
        async with self._semaphore:
            if self._bucket:
                await self._bucket.acquire()
            yield

    # ------------------------------------------------------------------
    # High-level API
    # ------------------------------------------------------------------

    async def map(
        self,
        items: Union[Iterable[Any], AsyncIterable[Any]],
        worker: Callable[[Any], AsyncIterable[BaseEntity]],
        *,
        preserve_order: bool = False,
        stop_on_error: bool = False,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process *items* through a bounded worker pool, yielding entities.

        Spawns ``max_workers`` pool tasks fed by a producer via a bounded
        queue. Each worker acquires a rate-limit token (if configured)
        before invoking the caller-supplied ``worker(item)`` async
        generator.

        Args:
            items: Sync or async iterable of work units.
            worker: ``async def worker(item) -> AsyncGenerator[BaseEntity, None]``
            preserve_order: If True, buffer and yield in input order.
            stop_on_error: If True, cancel remaining work on first error.
        """
        results_q: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue_size)
        items_q: asyncio.Queue = asyncio.Queue(maxsize=self._max_workers)
        sentinel = object()
        items_done = object()
        producer_finished = asyncio.Event()
        total_items: list[int] = [0]

        async def _producer() -> None:
            try:
                idx = 0
                if hasattr(items, "__aiter__"):
                    async for item in items:
                        await items_q.put((idx, item))
                        idx += 1
                        total_items[0] = idx
                else:
                    for item in items:
                        await items_q.put((idx, item))
                        idx += 1
                        total_items[0] = idx
            finally:
                await items_q.put(items_done)
                producer_finished.set()
                await results_q.put(None)

        async def _pool_worker() -> None:
            while True:
                msg = await items_q.get()
                if msg is items_done:
                    await items_q.put(items_done)
                    return
                idx, item = msg
                try:
                    if self._bucket:
                        await self._bucket.acquire()

                    agen = worker(item)
                    if not hasattr(agen, "__aiter__"):
                        raise TypeError(
                            "worker(item) must return an async iterator (async generator)."
                        )
                    async for entity in agen:
                        await results_q.put((idx, entity, None))
                except BaseException as exc:
                    await results_q.put((idx, None, exc))
                finally:
                    await results_q.put((idx, sentinel, None))

        producer_task = asyncio.create_task(_producer())
        worker_tasks = [asyncio.create_task(_pool_worker()) for _ in range(self._max_workers)]
        all_tasks = [producer_task, *worker_tasks]

        try:
            drain = self._drain_ordered if preserve_order else self._drain_unordered
            async for entity in drain(
                results_q,
                all_tasks,
                producer_finished,
                lambda: total_items[0],
                stop_on_error,
                sentinel,
            ):
                yield entity
        finally:
            for t in all_tasks:
                t.cancel()
            await asyncio.gather(*all_tasks, return_exceptions=True)

    # ------------------------------------------------------------------
    # Drain helpers
    # ------------------------------------------------------------------

    async def _drain_unordered(
        self,
        results_q: asyncio.Queue,
        tasks: list,
        producer_finished: asyncio.Event,
        get_total: Callable[[], int],
        stop_on_error: bool,
        sentinel: object,
    ) -> AsyncGenerator[BaseEntity, None]:
        done_items = 0
        while True:
            if producer_finished.is_set() and done_items >= get_total():
                break
            msg = await results_q.get()
            if msg is None:
                continue
            idx, payload, err = msg
            if payload is sentinel:
                done_items += 1
                continue
            if err is not None:
                self._logger.error(f"Worker error (item {idx}): {err}", exc_info=True)
                if stop_on_error:
                    for t in tasks:
                        t.cancel()
                    raise err
                continue
            yield payload

    async def _drain_ordered(
        self,
        results_q: asyncio.Queue,
        tasks: list,
        producer_finished: asyncio.Event,
        get_total: Callable[[], int],
        stop_on_error: bool,
        sentinel: object,
    ) -> AsyncGenerator[BaseEntity, None]:
        buffers: Dict[int, list[BaseEntity]] = {}
        finished: set[int] = set()
        next_idx = 0
        done_items = 0

        while True:
            if producer_finished.is_set() and done_items >= get_total():
                break
            msg = await results_q.get()
            if msg is None:
                continue
            idx, payload, err = msg
            if payload is sentinel:
                finished.add(idx)
                done_items += 1
            elif err is not None:
                self._logger.error(f"Worker error (item {idx}): {err}", exc_info=True)
                if stop_on_error:
                    for t in tasks:
                        t.cancel()
                    raise err
            else:
                buffers.setdefault(idx, []).append(payload)

            while next_idx in finished:
                for ent in buffers.pop(next_idx, []):
                    yield ent
                next_idx += 1
