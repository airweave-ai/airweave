"""Base rate limiter for API clients."""

import asyncio
import time
from abc import ABC
from typing import Optional

from airweave.core.logging import logger


class BaseRateLimiter(ABC):
    """Base class for per-pod singleton rate limiters.

    Implements sliding window rate limiting with async-safe locks.
    Shared across all converter instances in the pod.
    """

    # Subclasses must define these class attributes
    RATE_LIMIT_PER_POD_RPS: float = NotImplemented  # Requests per second per pod
    RATE_LIMIT_WINDOW_SECONDS: float = 1.0  # Sliding window size
    MAX_WAIT_FOR_SLOT_SECONDS: float = 30.0  # Max wait time
    POLL_INTERVAL_SECONDS: float = 0.1  # Poll interval

    _instance: Optional["BaseRateLimiter"] = None

    def __new__(cls):
        """Singleton pattern - one instance per pod per limiter type."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize rate limiter (only once per pod)."""
        if self._initialized:
            return

        # Sliding window tracking
        self._request_times: list[float] = []
        self._lock = asyncio.Lock()
        self._initialized = True

        # Log initialization (subclass should provide details)
        self._log_initialization()

    def _log_initialization(self):
        """Log rate limiter initialization. Override in subclasses for custom messages."""
        logger.debug(
            f"{self.__class__.__name__} initialized: {self.RATE_LIMIT_PER_POD_RPS:.1f} RPS per pod"
        )

    async def acquire(self):
        """Acquire a rate limit slot (blocks until available).

        Uses sliding window algorithm to enforce rate limit.
        All instances in this pod share this limiter.

        Raises:
            TimeoutError: If can't acquire slot within MAX_WAIT_FOR_SLOT_SECONDS
        """
        start_time = time.time()

        while True:
            now = time.time()

            # Timeout check
            if now - start_time > self.MAX_WAIT_FOR_SLOT_SECONDS:
                raise TimeoutError(
                    f"Failed to acquire {self.__class__.__name__} rate limit slot within "
                    f"{self.MAX_WAIT_FOR_SLOT_SECONDS}s"
                )

            async with self._lock:
                # Remove requests outside sliding window
                cutoff = now - self.RATE_LIMIT_WINDOW_SECONDS
                self._request_times = [t for t in self._request_times if t > cutoff]

                # Check if slot available
                if len(self._request_times) < self.RATE_LIMIT_PER_POD_RPS:
                    # Slot available - claim it
                    self._request_times.append(now)
                    return

            # At limit - wait and retry
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)
