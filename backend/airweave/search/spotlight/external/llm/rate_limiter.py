"""Rate limiter for LLM API calls.

Provides sliding window rate limiting based on RPM (requests per minute)
and TPM (tokens per minute) limits from model specifications.
"""

import asyncio
import time

from airweave.core.logging import ContextualLogger


class LLMRateLimiter:
    """Rate limiter for LLM APIs based on RPM and TPM limits.

    Uses sliding window algorithm to enforce both limits.
    Not a singleton - each LLM instance gets its own limiter.

    Attributes:
        rpm_limit: Maximum requests per minute.
        tpm_limit: Maximum tokens per minute.
    """

    # Configuration
    WINDOW_SECONDS = 60.0  # 1 minute sliding window
    MAX_WAIT_SECONDS = 120.0  # Max time to wait for a slot
    POLL_INTERVAL_SECONDS = 0.5  # Poll every 500ms

    def __init__(
        self,
        rpm_limit: int,
        tpm_limit: int,
        logger: ContextualLogger,
    ) -> None:
        """Initialize rate limiter.

        Args:
            rpm_limit: Requests per minute limit.
            tpm_limit: Tokens per minute limit.
            logger: Logger for debug output.
        """
        self._rpm_limit = rpm_limit
        self._tpm_limit = tpm_limit
        self._logger = logger

        # Sliding window tracking
        self._request_times: list[float] = []
        self._token_usage: list[tuple[float, int]] = []  # (timestamp, tokens)
        self._lock = asyncio.Lock()

        self._logger.debug(f"[LLMRateLimiter] Initialized: RPM={rpm_limit}, TPM={tpm_limit}")

    @property
    def rpm_limit(self) -> int:
        """Get the RPM limit."""
        return self._rpm_limit

    @property
    def tpm_limit(self) -> int:
        """Get the TPM limit."""
        return self._tpm_limit

    async def acquire(self, input_tokens: int = 0) -> None:
        """Acquire a rate limit slot.

        Blocks until both RPM and TPM limits allow the request.

        Args:
            input_tokens: Token count for this request (for TPM tracking).
                Use tokenizer.count_tokens() for accurate counting.

        Raises:
            TimeoutError: If can't acquire slot within MAX_WAIT_SECONDS.
        """
        start_time = time.monotonic()

        while True:
            now = time.monotonic()
            elapsed = now - start_time

            if elapsed > self.MAX_WAIT_SECONDS:
                raise TimeoutError(
                    f"Failed to acquire rate limit slot within {self.MAX_WAIT_SECONDS}s "
                    f"(RPM={self._rpm_limit}, TPM={self._tpm_limit})"
                )

            async with self._lock:
                # Remove entries outside sliding window
                cutoff = now - self.WINDOW_SECONDS
                self._request_times = [t for t in self._request_times if t > cutoff]
                self._token_usage = [(t, tokens) for t, tokens in self._token_usage if t > cutoff]

                # Check RPM limit
                current_rpm = len(self._request_times)
                if current_rpm >= self._rpm_limit:
                    # RPM limit reached, need to wait
                    if elapsed > 5.0:  # Only log after waiting a while
                        self._logger.debug(
                            f"[LLMRateLimiter] RPM limit reached "
                            f"({current_rpm}/{self._rpm_limit}), waiting..."
                        )
                else:
                    # Check TPM limit
                    current_tpm = sum(tokens for _, tokens in self._token_usage)
                    if current_tpm + input_tokens <= self._tpm_limit:
                        # Both limits OK - acquire slot
                        self._request_times.append(now)
                        if input_tokens > 0:
                            self._token_usage.append((now, input_tokens))
                        return
                    elif elapsed > 5.0:  # Only log after waiting a while
                        self._logger.debug(
                            f"[LLMRateLimiter] TPM limit reached "
                            f"({current_tpm}/{self._tpm_limit}), waiting..."
                        )

            # At limit - wait and retry
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

    def record_tokens(self, actual_tokens: int) -> None:
        """Record actual token usage after API call completes.

        Call this after getting the response to update token tracking
        with actual usage (which may differ from the input token count).

        Args:
            actual_tokens: Actual tokens used (from response.usage.total_tokens).
        """
        now = time.monotonic()
        # Add the actual usage (the input tokens were already recorded in acquire)
        # This is a simplified approach - for perfect accuracy we'd need to
        # correlate and replace the input count, but this is sufficient for
        # rate limiting purposes.
        self._token_usage.append((now, actual_tokens))
