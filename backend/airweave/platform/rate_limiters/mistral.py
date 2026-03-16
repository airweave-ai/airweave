"""Mistral API rate limiter."""

from typing import Optional

from airweave.core.logging import logger

from ._base import BaseRateLimiter


class MistralRateLimiter(BaseRateLimiter):
    """Per-pod rate limiter for Mistral API.

    Singleton per pod (Python process) that limits Mistral API requests.
    Assumes 6 sync worker pods, each gets ~3 RPS (24 / 6 = 4, conservative: 3).

    Features:
    - Sliding window rate limiting
    - Async-safe with locks
    - Shared across all syncs in the pod
    """

    # ==================== CONFIGURATION (Class Attributes) ====================

    # Mistral workspace limits
    MISTRAL_WORKSPACE_RPS = 36  # Mistral API workspace limit (updated from 24)

    # Deployment configuration
    NUM_SYNC_WORKER_PODS = 6  # Number of K8s sync worker pods

    # Per-pod rate limit (use full capacity)
    RATE_LIMIT_PER_POD_RPS = 10.0  # RPS per pod (36 / 6 = 6)

    # Sliding window configuration
    RATE_LIMIT_WINDOW_SECONDS = 1.0  # 1 second sliding window

    # Acquisition timeout (very long - rate limiter paces but never fails sync)
    MAX_WAIT_FOR_SLOT_SECONDS = 3600.0  # 1 hour - only paces, never stops sync
    POLL_INTERVAL_SECONDS = 0.1  # Check availability every 100ms

    # ==========================================================================

    _instance: Optional["MistralRateLimiter"] = None

    def _log_initialization(self) -> None:
        """Log Mistral-specific initialization message."""
        logger.debug(
            f"Mistral rate limiter initialized: {self.RATE_LIMIT_PER_POD_RPS} RPS per pod "
            f"({self.NUM_SYNC_WORKER_PODS} pods × {self.RATE_LIMIT_PER_POD_RPS} RPS = "
            f"{self.NUM_SYNC_WORKER_PODS * self.RATE_LIMIT_PER_POD_RPS:.0f} RPS total, "
            f"timeout: {self.MAX_WAIT_FOR_SLOT_SECONDS / 60:.0f} min)"
        )
