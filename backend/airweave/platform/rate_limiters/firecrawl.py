"""Firecrawl API rate limiter."""

from typing import Optional

from airweave.core.logging import logger

from ._base import BaseRateLimiter


class FirecrawlRateLimiter(BaseRateLimiter):
    """Per-pod rate limiter for Firecrawl API.

    Singleton per pod (Python process) that limits Firecrawl API requests.
    Growth plan: 2500 req/min for batch endpoints = ~42 RPS total.
    With 6 pods, each gets ~7 RPS.

    Note: This limits API calls, not URLs. A single batch_scrape call
    with 100 URLs counts as 1 request towards the rate limit.
    """

    # ==================== CONFIGURATION (Class Attributes) ====================

    # Firecrawl workspace limits (Growth plan)
    FIRECRAWL_WORKSPACE_RPM = 2500  # Requests per minute for batch endpoints
    FIRECRAWL_WORKSPACE_RPS = 42  # ~2500/60
    FIRECRAWL_CONCURRENT_BROWSERS = 100  # Growth plan concurrent browser limit

    # Deployment configuration
    NUM_SYNC_WORKER_PODS = 6  # Number of K8s sync worker pods

    # Per-pod rate limit (conservative)
    RATE_LIMIT_PER_POD_RPS = 7.0  # RPS per pod (42/6 ≈ 7)

    # Sliding window configuration
    RATE_LIMIT_WINDOW_SECONDS = 1.0  # 1 second sliding window

    # Acquisition timeout (very long - rate limiter paces but never fails sync)
    MAX_WAIT_FOR_SLOT_SECONDS = 3600.0  # 1 hour - only paces, never stops sync
    POLL_INTERVAL_SECONDS = 0.1  # Check availability every 100ms

    # ==========================================================================

    _instance: Optional["FirecrawlRateLimiter"] = None

    def _log_initialization(self):
        """Log Firecrawl-specific initialization message."""
        logger.debug(
            f"Firecrawl rate limiter initialized: {self.RATE_LIMIT_PER_POD_RPS} RPS per pod "
            f"({self.NUM_SYNC_WORKER_PODS} pods × {self.RATE_LIMIT_PER_POD_RPS} RPS = "
            f"{self.NUM_SYNC_WORKER_PODS * self.RATE_LIMIT_PER_POD_RPS:.0f} RPS total, "
            f"timeout: {self.MAX_WAIT_FOR_SLOT_SECONDS / 60:.0f} min)"
        )
