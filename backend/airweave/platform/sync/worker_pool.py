"""Worker pool implementation for controlling async concurrency."""

import asyncio
from typing import Any, Callable

from airweave.core.logging import logger


class AsyncWorkerPool:
    """Manages a pool of workers with controlled concurrency.

    This class limits how many async tasks can run at once using a semaphore,
    preventing system overload when processing many items in parallel.
    """

    def __init__(self, max_workers: int = 20):
        """Initialize worker pool with concurrency control.

        Args:
            max_workers: Maximum number of tasks allowed to run concurrently
        """
        self.semaphore = asyncio.Semaphore(max_workers)
        self.pending_tasks = set()
        self.max_workers = max_workers

    async def submit(self, coro: Callable, *args, **kwargs) -> asyncio.Task:
        """Submit a coroutine to be executed by the worker pool.

        Creates a task, adds it to our tracking set, and returns it.
        Tasks run with controlled concurrency through the semaphore.
        """
        task = asyncio.create_task(self._run_with_semaphore(coro, *args, **kwargs))
        self.pending_tasks.add(task)
        task.add_done_callback(self._handle_task_completion)
        return task

    async def _run_with_semaphore(self, coro: Callable, *args, **kwargs) -> Any:
        """Run a coroutine with semaphore control.

        Acquires a semaphore before running the coroutine, limiting concurrency.
        Semaphore is automatically released when coroutine completes.
        """
        async with self.semaphore:
            return await coro(*args, **kwargs)

    def _handle_task_completion(self, task: asyncio.Task) -> None:
        """Handle task completion and clean up."""
        self.pending_tasks.discard(task)
        if not task.cancelled() and task._exception:
            logger.error(f"Task failed: {task._exception}")

    async def wait_for_batch(self, timeout: float = 0.5) -> None:
        """Wait for some tasks to complete."""
        if not self.pending_tasks:
            return

        done, _ = await asyncio.wait(
            self.pending_tasks, return_when=asyncio.FIRST_COMPLETED, timeout=timeout
        )

        for task in done:
            try:
                await task
            except Exception as e:
                logger.error(f"Error in worker task: {e}")

    async def wait_for_completion(self) -> None:
        """Wait for all tasks to complete."""
        while self.pending_tasks:
            current_batch = list(self.pending_tasks)[: self.max_workers * 2]
            if not current_batch:
                break

            done, _ = await asyncio.wait(
                current_batch, return_when=asyncio.ALL_COMPLETED, timeout=10
            )

            for task in done:
                try:
                    await task
                except Exception as e:
                    logger.error(f"Task error during completion: {e}")
