"""OpenAI API rate limiter."""

from typing import Optional

from airweave.core.logging import logger

from ._base import BaseRateLimiter


class OpenAIRateLimiter(BaseRateLimiter):
    """Per-pod rate limiter for OpenAI API.

    Singleton shared across all CodeConverter instances in pod.
    Based on gpt-5-nano limits: 10,000 RPM.
    """

    # ==================== CONFIGURATION (Class Attributes) ====================

    # OpenAI rate limits (gpt-5-nano)
    OPENAI_RPM_LIMIT = 10_000  # Requests per minute

    # Deployment configuration
    NUM_SYNC_WORKER_PODS = 6  # Number of K8s sync worker pods

    # Per-pod rate limit (conservative)
    RATE_LIMIT_PER_POD_RPM = 1500  # RPM per pod (10k / 6 ≈ 1666, use 1500)
    RATE_LIMIT_PER_POD_RPS = RATE_LIMIT_PER_POD_RPM / 60  # = 25 RPS

    # Sliding window configuration
    RATE_LIMIT_WINDOW_SECONDS = 1.0  # 1 second window
    MAX_WAIT_FOR_SLOT_SECONDS = 30.0  # Max wait time
    POLL_INTERVAL_SECONDS = 0.1  # Poll every 100ms

    # ==========================================================================

    _instance: Optional["OpenAIRateLimiter"] = None

    def _log_initialization(self):
        """Log OpenAI-specific initialization message."""
        logger.debug(
            f"OpenAI rate limiter initialized: {self.RATE_LIMIT_PER_POD_RPS:.1f} RPS per pod "
            f"({self.NUM_SYNC_WORKER_PODS} pods × {self.RATE_LIMIT_PER_POD_RPS:.1f} = "
            f"{self.NUM_SYNC_WORKER_PODS * self.RATE_LIMIT_PER_POD_RPS:.1f} RPS total)"
        )
