"""Async helper utilities for improved performance."""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, TypeVar

from airweave.core.config import settings

# Shared thread pool for CPU-bound operations
_cpu_executor = None
_cpu_executor_lock = asyncio.Lock()

T = TypeVar("T")


async def get_cpu_executor() -> ThreadPoolExecutor:
    """Get or create the shared CPU executor for thread pool operations."""
    global _cpu_executor

    async with _cpu_executor_lock:
        if _cpu_executor is None:
            # Scale with worker count
            max_workers = getattr(settings, "SYNC_THREAD_POOL_SIZE", min(100, os.cpu_count() * 4))

            # Create a thread pool with configurable limits
            _cpu_executor = ThreadPoolExecutor(
                max_workers=max_workers, thread_name_prefix="airweave-cpu"
            )

    return _cpu_executor


async def run_in_thread_pool(func: Callable[..., T], *args, **kwargs) -> T:
    """Run a synchronous function in the shared thread pool.

    This avoids creating excessive threads by using a controlled thread pool.
    """
    loop = asyncio.get_running_loop()
    executor = await get_cpu_executor()

    # If there are keyword arguments, wrap the function with partial
    if kwargs:
        from functools import partial

        func = partial(func, **kwargs)
        return await loop.run_in_executor(executor, func, *args)
    else:
        return await loop.run_in_executor(executor, func, *args)
