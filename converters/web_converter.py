"""Web converter for fetching URLs and converting to markdown using Firecrawl."""

import asyncio
from typing import Any, Dict, List, Optional

from httpx import HTTPStatusError, ReadTimeout, TimeoutException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.converters._base import BaseTextConverter
from airweave.platform.rate_limiters import FirecrawlRateLimiter
from airweave.platform.sync.exceptions import SyncFailureError

# ==================== CONFIGURATION ====================

# Retry configuration
MAX_RETRIES = 3
RETRY_MIN_WAIT = 10  # seconds
RETRY_MAX_WAIT = 120  # seconds (longer for rate limits)
RETRY_MULTIPLIER = 2

# Batch job polling
POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 600  # 10 minutes max for a batch


class WebConverter(BaseTextConverter):
    """Converter that fetches URLs and converts HTML to markdown.

    Uses Firecrawl batch scrape API to efficiently process multiple URLs.
    Returns markdown content for each URL.

    Error handling:
    - Per-URL failures: Returns None for that URL (entity will be skipped)
    - Batch failures: Returns all None (all entities in batch will be skipped)
    - Infrastructure failures (API key, auth, quota): Raises SyncFailureError (fails entire sync)
    """

    # Batch size from Firecrawl Growth plan (100 concurrent browsers)
    BATCH_SIZE = FirecrawlRateLimiter.FIRECRAWL_CONCURRENT_BROWSERS

    def __init__(self):
        """Initialize the web converter with lazy Firecrawl client."""
        self.rate_limiter = FirecrawlRateLimiter()  # Singleton - shared across pod
        self._firecrawl_client: Optional[Any] = None
        self._initialized = False

    def _ensure_client(self):
        """Ensure Firecrawl client is initialized (lazy initialization).

        Raises:
            SyncFailureError: If API key not configured or package not installed
        """
        if self._initialized:
            return

        api_key = getattr(settings, "FIRECRAWL_API_KEY", None)
        if not api_key:
            raise SyncFailureError("FIRECRAWL_API_KEY required for web conversion")

        try:
            from firecrawl import AsyncFirecrawl

            self._firecrawl_client = AsyncFirecrawl(api_key=api_key)
            self._initialized = True
            logger.debug("Firecrawl client initialized for web conversion")
        except ImportError:
            raise SyncFailureError("firecrawl-py package required but not installed")

    async def convert_batch(self, urls: List[str]) -> Dict[str, str]:
        """Fetch URLs and convert to markdown using Firecrawl batch scrape.

        Args:
            urls: List of URLs to fetch and convert

        Returns:
            Dict mapping URL -> markdown content (None if that URL failed).
            Even if the entire batch fails, returns all None values so entities
            can be skipped individually rather than failing the entire sync.

        Raises:
            SyncFailureError: Only for true infrastructure failures (API key missing,
                              unauthorized, forbidden, payment required, quota exceeded)
        """
        if not urls:
            return {}

        # Ensure client is initialized (raises SyncFailureError if not possible)
        self._ensure_client()

        # Initialize all URLs as None (failed) - will be updated with successful results
        results: Dict[str, str] = {url: None for url in urls}

        try:
            # Rate limit before API call (batch counts as 1 request)
            await self.rate_limiter.acquire()

            # Start batch scrape and wait for completion
            batch_result = await self._batch_scrape_with_retry(urls)

            # Extract results - updates dict with successful conversions
            self._extract_results(urls, batch_result, results)

            return results

        except SyncFailureError:
            # Infrastructure failure - propagate to fail sync
            raise
        except Exception as e:
            error_msg = str(e).lower()

            # Check for infrastructure failures that should fail the sync
            is_infrastructure = any(
                kw in error_msg
                for kw in [
                    "api key",
                    "unauthorized",
                    "forbidden",
                    "payment required",
                    "rate limit",
                    "quota exceeded",
                ]
            )

            if is_infrastructure:
                logger.error(f"Firecrawl infrastructure failure: {e}")
                raise SyncFailureError(f"Firecrawl infrastructure failure: {e}")

            # Other errors (timeout, network issues) - log but return partial results
            # Individual URL failures are already handled by returning None
            # Even if entire batch fails, return all None - entities will be skipped individually
            logger.warning(f"Firecrawl batch scrape error (entities will be skipped): {e}")

            # Return partial results - URLs with None will be skipped by entity pipeline
            return results

    async def _batch_scrape_with_retry(self, urls: List[str]):
        """Execute batch scrape with retry logic.

        Args:
            urls: List of URLs to scrape

        Returns:
            Firecrawl batch scrape result object

        Raises:
            Exception: If all retries fail
        """

        @retry(
            retry=retry_if_exception_type(
                (TimeoutException, ReadTimeout, HTTPStatusError, asyncio.TimeoutError)
            ),
            stop=stop_after_attempt(MAX_RETRIES),
            wait=wait_exponential(
                multiplier=RETRY_MULTIPLIER, min=RETRY_MIN_WAIT, max=RETRY_MAX_WAIT
            ),
            reraise=True,
        )
        async def _call():
            # batch_scrape polls internally until complete
            return await self._firecrawl_client.batch_scrape(
                urls,
                formats=["markdown"],
                poll_interval=POLL_INTERVAL_SECONDS,
                wait_timeout=POLL_TIMEOUT_SECONDS,
            )

        return await _call()

    def _extract_results(self, urls: List[str], batch_result, results: Dict[str, str]) -> None:
        """Extract markdown content from batch scrape result.

        Updates results dict in-place with successful conversions.
        URLs that fail remain as None in the dict.

        Args:
            urls: Original list of URLs
            batch_result: Firecrawl batch scrape result object
            results: Dict to update (already initialized with all URLs -> None)
        """
        # Check if we got any data
        if not hasattr(batch_result, "data") or not batch_result.data:
            logger.warning("Firecrawl batch returned no data")
            return

        # Process each document in the result
        for doc in batch_result.data:
            # Extract source URL from metadata
            source_url = self._get_source_url(doc)
            if not source_url:
                logger.warning("Firecrawl doc missing sourceURL in metadata")
                continue

            # Extract markdown content
            markdown = getattr(doc, "markdown", None)

            if not markdown:
                logger.warning(f"Firecrawl returned no markdown for {source_url}")
                # Leave as None in results
                continue

            # Match back to original URL (handle trailing slashes etc)
            matched_url = self._match_url(source_url, urls)
            if matched_url:
                results[matched_url] = markdown
            elif source_url in results:
                # Fallback: use source_url directly if it was in input
                results[source_url] = markdown
            else:
                logger.warning(f"Could not match Firecrawl result URL: {source_url}")

        # Log summary
        successful = sum(1 for v in results.values() if v is not None)
        failed = len(results) - successful

        if failed > 0:
            failed_urls = [url for url, content in results.items() if content is None]
            logger.warning(
                f"Firecrawl: {successful}/{len(results)} URLs succeeded, "
                f"{failed} failed: {failed_urls[:3]}{'...' if len(failed_urls) > 3 else ''}"
            )
        else:
            logger.debug(f"Firecrawl: all {successful} URLs converted successfully")

    def _get_source_url(self, doc) -> Optional[str]:
        """Extract source URL from Firecrawl document metadata.

        Args:
            doc: Firecrawl document object

        Returns:
            Source URL string or None
        """
        if not hasattr(doc, "metadata") or not doc.metadata:
            return None

        # Firecrawl v4 uses snake_case: source_url
        # Try attribute access first (for typed objects)
        source_url = getattr(doc.metadata, "source_url", None)
        if source_url:
            return source_url

        # Fallback: try camelCase for older SDK versions
        source_url = getattr(doc.metadata, "sourceURL", None)
        if source_url:
            return source_url

        # Try dict access (for untyped dicts)
        if isinstance(doc.metadata, dict):
            return doc.metadata.get("source_url") or doc.metadata.get("sourceURL")

        return None

    def _match_url(self, source_url: str, original_urls: List[str]) -> Optional[str]:
        """Match a source URL back to the original URL list.

        Handles minor differences like trailing slashes.

        Args:
            source_url: URL from Firecrawl response
            original_urls: List of original input URLs

        Returns:
            Matched original URL or None
        """
        # Exact match
        if source_url in original_urls:
            return source_url

        # Try normalized comparison (trailing slashes)
        normalized_source = source_url.rstrip("/")
        for url in original_urls:
            if url.rstrip("/") == normalized_source:
                return url

        return None
