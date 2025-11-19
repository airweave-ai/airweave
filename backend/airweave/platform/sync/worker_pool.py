"""Worker pool implementation for controlling async concurrency."""

import asyncio
import threading
from typing import Any, Callable

from airweave.core.logging import ContextualLogger


class AsyncWorkerPool:
    """Manages a pool of workers with controlled concurrency.

    This class limits how many async tasks can run at once using a semaphore,
    preventing system overload when processing many items in parallel.
    """

    def __init__(self, logger: ContextualLogger, max_workers: int = 100):
        """Initialize worker pool with concurrency control.

        Args:
            max_workers: Maximum number of tasks allowed to run concurrently
            logger: Optional logger instance for contextual logging
        """
        self.semaphore = asyncio.Semaphore(max_workers)
        self.pending_tasks = set()
        self.max_workers = max_workers
        self.logger = logger

        # Simple flag to prevent submissions after cancellation
        self._cancelled = False

    async def submit(self, coro: Callable, *args, **kwargs) -> asyncio.Task:
        """Submit a coroutine to be executed by the worker pool.

        Creates a task, adds it to our tracking set, and returns it.
        Tasks run with controlled concurrency through the semaphore.
        """
        if self._cancelled:
            raise RuntimeError("Cannot submit tasks after worker pool has been cancelled")

        task_id = f"task_{len(self.pending_tasks) + 1}"

        self.logger.debug(
            f"🔄 WORKER_SUBMIT [{task_id}] Submitting task to worker pool "
            f"(pending: {len(self.pending_tasks)}/{self.max_workers})"
        )

        task = asyncio.create_task(
            self._run_with_semaphore(coro, task_id, *args, **kwargs), name=task_id
        )
        task.task_id = task_id  # Store task ID for logging
        self.pending_tasks.add(task)
        task.add_done_callback(self._handle_task_completion)
        return task

    async def _run_with_semaphore(self, coro: Callable, task_id: str, *args, **kwargs) -> Any:
        """Run a coroutine with semaphore control.

        Acquires a semaphore before running the coroutine, limiting concurrency.
        Semaphore is automatically released when coroutine completes.
        """
        thread_id = threading.get_ident()

        self.logger.debug(
            f"⏳ WORKER_WAIT [{task_id}] Waiting for semaphore "
            f"(thread: {thread_id}, available: {self.semaphore._value})"
        )

        async with self.semaphore:
            self.logger.debug(
                f"🚀 WORKER_START [{task_id}] Acquired semaphore, starting execution "
                f"(thread: {thread_id})"
            )

            start_time = asyncio.get_running_loop().time()
            try:
                result = await coro(*args, **kwargs)
                elapsed = asyncio.get_running_loop().time() - start_time

                self.logger.debug(
                    f"✅ WORKER_COMPLETE [{task_id}] Task completed successfully "
                    f"in {elapsed:.2f}s (thread: {thread_id})"
                )
                return result

            except asyncio.CancelledError:
                elapsed = asyncio.get_running_loop().time() - start_time
                self.logger.warning(
                    f"🚫 WORKER_CANCELLED [{task_id}] "
                    f"Cancelled after {elapsed:.2f}s (thread: {thread_id})"
                )
                raise
            except Exception as e:
                elapsed = asyncio.get_running_loop().time() - start_time
                self.logger.warning(
                    f"❌ WORKER_ERROR [{task_id}] Task failed after {elapsed:.2f}s "
                    f"(thread: {thread_id}): {type(e).__name__}: {str(e)}"
                )
                raise

    def _handle_task_completion(self, task: asyncio.Task) -> None:
        """Handle task completion and clean up."""
        task_id = getattr(task, "task_id", "unknown")
        self.pending_tasks.discard(task)

        if task.cancelled():
            self.logger.warning(f"🚫 WORKER_CANCELLED [{task_id}] Task was cancelled")
        elif task.exception() is not None:
            self.logger.warning(
                f"💥 WORKER_EXCEPTION [{task_id}] Task completed with exception: {task.exception()}"
            )
        else:
            self.logger.debug(f"🏁 WORKER_CLEANUP [{task_id}] Task cleaned up successfully")

    async def cancel_all(self) -> None:
        """Cancel all pending tasks immediately."""
        # Set flag to prevent new submissions
        self._cancelled = True

        if self.pending_tasks:
            self.logger.info(f"Cancelling {len(self.pending_tasks)} pending tasks...")
            for task in list(self.pending_tasks):
                if not task.done():
                    task.cancel()

            # Wait for cancellations to complete
            await asyncio.gather(*self.pending_tasks, return_exceptions=True)
            self.logger.info("All tasks cancelled")
