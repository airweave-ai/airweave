"""Web converter for fetching URLs and converting to markdown using Tavily Extract."""

from typing import Any, Dict, List, Optional

from airweave.core.config import settings
from airweave.core.logging import logger
from airweave.platform.converters._base import BaseTextConverter
from airweave.platform.sync.exceptions import SyncFailureError

# Tavily Extract API limit
TAVILY_MAX_URLS_PER_REQUEST = 20


class TavilyWebConverter(BaseTextConverter):
    """Converter that fetches URLs and converts HTML to markdown using Tavily Extract.

    Uses Tavily's extract() API to process URLs and return markdown content.
    Returns markdown content for each URL.

    Error handling:
    - Per-URL failures: Returns None for that URL (entity will be skipped)
    - Batch failures: Returns all None (all entities in batch will be skipped)
    - Infrastructure failures (API key, auth): Raises SyncFailureError (fails entire sync)
    """

    BATCH_SIZE = TAVILY_MAX_URLS_PER_REQUEST

    def __init__(self):
        """Initialize the Tavily web converter with lazy client."""
        self._tavily_client: Optional[Any] = None
        self._initialized = False

    def _ensure_client(self):
        """Ensure Tavily client is initialized (lazy initialization).

        Raises:
            SyncFailureError: If API key not configured or package not installed
        """
        if self._initialized:
            return

        api_key = getattr(settings, "TAVILY_API_KEY", None)
        if not api_key:
            raise SyncFailureError("TAVILY_API_KEY required for Tavily web conversion")

        try:
            from tavily import AsyncTavilyClient

            self._tavily_client = AsyncTavilyClient(api_key=api_key)
            self._initialized = True
            logger.debug("Tavily client initialized for web conversion")
        except ImportError:
            raise SyncFailureError("tavily-python package required but not installed")

    async def convert_batch(self, urls: List[str]) -> Dict[str, str]:
        """Fetch URLs and convert to markdown using Tavily Extract.

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
            # Process URLs in chunks of TAVILY_MAX_URLS_PER_REQUEST
            for i in range(0, len(urls), TAVILY_MAX_URLS_PER_REQUEST):
                chunk = urls[i : i + TAVILY_MAX_URLS_PER_REQUEST]
                response = await self._tavily_client.extract(
                    urls=chunk,
                    extract_depth="advanced",
                )

                # Map successful results
                for item in response.get("results", []):
                    url = item.get("url")
                    raw_content = item.get("raw_content")
                    if url and raw_content:
                        matched_url = self._match_url(url, urls)
                        if matched_url:
                            results[matched_url] = raw_content
                        elif url in results:
                            results[url] = raw_content
                        else:
                            logger.warning(f"Could not match Tavily result URL: {url}")
                    elif url:
                        logger.warning(f"Tavily returned no content for {url}")

                # Log any failed URLs
                for failed in response.get("failed_results", []):
                    failed_url = failed.get("url", "unknown")
                    error = failed.get("error", "unknown error")
                    logger.warning(f"Tavily extraction failed for {failed_url}: {error}")

            # Log summary
            successful = sum(1 for v in results.values() if v is not None)
            failed = len(results) - successful

            if failed > 0:
                failed_urls = [url for url, content in results.items() if content is None]
                logger.warning(
                    f"Tavily: {successful}/{len(results)} URLs succeeded, "
                    f"{failed} failed: {failed_urls[:3]}"
                    f"{'...' if len(failed_urls) > 3 else ''}"
                )
            else:
                logger.debug(f"Tavily: all {successful} URLs converted successfully")

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
                logger.error(f"Tavily infrastructure failure: {e}")
                raise SyncFailureError(f"Tavily infrastructure failure: {e}")

            # Other errors - log but return partial results
            logger.warning(f"Tavily batch extract error (entities will be skipped): {e}")
            return results

    def _match_url(self, source_url: str, original_urls: List[str]) -> Optional[str]:
        """Match a source URL back to the original URL list.

        Handles minor differences like trailing slashes.

        Args:
            source_url: URL from Tavily response
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
