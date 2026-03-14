"""Web converter for fetching URLs and converting to markdown using Firecrawl."""

import asyncio
from typing import Any, Dict, List, Optional

from httpx import HTTPStatusError, ReadTimeout, TimeoutException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.domains.converters._base import BaseTextConverter
from airweave.domains.sync_pipeline.exceptions import SyncFailureError
from airweave.platform.rate_limiters import FirecrawlRateLimiter

MAX_RETRIES = 3
RETRY_MIN_WAIT = 10
RETRY_MAX_WAIT = 120
RETRY_MULTIPLIER = 2

POLL_INTERVAL_SECONDS = 2
POLL_TIMEOUT_SECONDS = 600


class WebConverter(BaseTextConverter):
    """Converter that fetches URLs and converts HTML to markdown.

    Uses Firecrawl batch scrape API to efficiently process multiple URLs.
    """

    BATCH_SIZE = FirecrawlRateLimiter.FIRECRAWL_CONCURRENT_BROWSERS

    def __init__(self):
        """Initialize the web converter with lazy Firecrawl client."""
        self.rate_limiter = FirecrawlRateLimiter()
        self._firecrawl_client: Optional[Any] = None
        self._initialized = False

    def _ensure_client(self):
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
        """Fetch URLs and convert to markdown using Firecrawl batch scrape."""
        if not urls:
            return {}

        self._ensure_client()

        results: Dict[str, str] = {url: None for url in urls}

        try:
            await self.rate_limiter.acquire()
            batch_result = await self._batch_scrape_with_retry(urls)
            self._extract_results(urls, batch_result, results)
            return results

        except SyncFailureError:
            raise
        except Exception as e:
            error_msg = str(e).lower()

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

            logger.warning(f"Firecrawl batch scrape error (entities will be skipped): {e}")
            return results

    async def _batch_scrape_with_retry(self, urls: List[str]):
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
            return await self._firecrawl_client.batch_scrape(
                urls,
                formats=["markdown"],
                poll_interval=POLL_INTERVAL_SECONDS,
                wait_timeout=POLL_TIMEOUT_SECONDS,
            )

        return await _call()

    def _extract_results(self, urls: List[str], batch_result, results: Dict[str, str]) -> None:
        if not hasattr(batch_result, "data") or not batch_result.data:
            logger.warning("Firecrawl batch returned no data")
            return

        for doc in batch_result.data:
            source_url = self._get_source_url(doc)
            if not source_url:
                logger.warning("Firecrawl doc missing sourceURL in metadata")
                continue

            markdown = getattr(doc, "markdown", None)

            if not markdown:
                logger.warning(f"Firecrawl returned no markdown for {source_url}")
                continue

            matched_url = self._match_url(source_url, urls)
            if matched_url:
                results[matched_url] = markdown
            elif source_url in results:
                results[source_url] = markdown
            else:
                logger.warning(f"Could not match Firecrawl result URL: {source_url}")

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
        if not hasattr(doc, "metadata") or not doc.metadata:
            return None

        source_url = getattr(doc.metadata, "source_url", None)
        if source_url:
            return source_url

        source_url = getattr(doc.metadata, "sourceURL", None)
        if source_url:
            return source_url

        if isinstance(doc.metadata, dict):
            return doc.metadata.get("source_url") or doc.metadata.get("sourceURL")

        return None

    def _match_url(self, source_url: str, original_urls: List[str]) -> Optional[str]:
        if source_url in original_urls:
            return source_url

        normalized_source = source_url.rstrip("/")
        for url in original_urls:
            if url.rstrip("/") == normalized_source:
                return url

        return None
