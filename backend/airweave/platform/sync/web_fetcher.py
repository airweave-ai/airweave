"""Web fetcher transformer using Firecrawl."""

import asyncio
import hashlib
import os
import random
from typing import List
from uuid import uuid4

import aiofiles
from firecrawl import AsyncFirecrawlApp

from airweave.core.config import settings
from airweave.core.logging import ContextualLogger
from airweave.platform.entities._base import WebEntity
from airweave.platform.entities.web import WebFileEntity
from airweave.platform.sync.async_helpers import run_in_thread_pool

# Improved connection management
_shared_firecrawl_client = None
_client_semaphore = None
_client_lock = asyncio.Lock()
_httpx_client = None
_temp_dir_created = False

# Tavily client state
_shared_tavily_client = None
_tavily_semaphore = None
_tavily_client_lock = asyncio.Lock()

# Add a separate semaphore for CTTI to limit their concurrent requests
_ctti_semaphore = None
_ctti_semaphore_lock = asyncio.Lock()


async def get_httpx_client(logger: ContextualLogger):
    """Get or create shared httpx client with proper connection pooling."""
    global _httpx_client

    if _httpx_client is None:
        import httpx

        # Optimized connection limits for high concurrency
        max_connections = getattr(settings, "WEB_FETCHER_MAX_CONNECTIONS", 200)
        keepalive_connections = getattr(settings, "WEB_FETCHER_KEEPALIVE_CONNECTIONS", 100)

        limits = httpx.Limits(
            max_connections=max_connections,
            max_keepalive_connections=keepalive_connections,
            keepalive_expiry=60.0,  # Longer keepalive for connection reuse
        )

        # Create client with optimized timeout settings
        _httpx_client = httpx.AsyncClient(
            limits=limits,
            timeout=httpx.Timeout(
                connect=30.0,  # Increased from 10.0 to handle slower connections
                read=240.0,  # Increased from 120.0 to handle slow CTTI pages (4 minutes)
                write=30.0,
                pool=240.0,  # Increased from 120.0 to match read timeout
            ),
            # Performance optimizations
            verify=True,
            http2=False,  # Disabled - can cause SSL shutdown errors with some servers
            follow_redirects=True,  # Handle redirects automatically
        )

        logger.debug(
            f"🌐 HTTPX_CLIENT_INIT Created shared httpx client "
            f"(max_connections={max_connections}, keepalive={keepalive_connections})"
        )

    return _httpx_client


async def cleanup_httpx_client(logger: ContextualLogger):
    """Clean up the httpx client when done."""
    global _httpx_client
    if _httpx_client:
        # Clean client shutdown without SSL errors
        try:
            # First cancel any pending requests
            _httpx_client._transport.close()
            # Then close the client
            await _httpx_client.aclose()
        except Exception as e:
            # Ignore SSL shutdown errors during cleanup
            if "ssl" not in str(e).lower():
                logger.error(f"Error closing httpx client: {e}")
        finally:
            _httpx_client = None
        logger.debug("🌐 HTTPX_CLIENT_CLEANUP Closed httpx client")


async def ensure_temp_dir(logger: ContextualLogger):
    """Ensure the temp directory exists (create once)."""
    global _temp_dir_created
    if not _temp_dir_created:
        base_temp_dir = "/tmp/airweave"
        await run_in_thread_pool(os.makedirs, base_temp_dir, exist_ok=True)
        _temp_dir_created = True
        logger.debug(f"📁 WEB_TEMP_DIR Created temp directory: {base_temp_dir}")
    return "/tmp/airweave"


async def get_firecrawl_client(logger: ContextualLogger):
    """Get or create the shared Firecrawl client instance with connection pooling."""
    global _shared_firecrawl_client, _client_semaphore

    async with _client_lock:
        if _shared_firecrawl_client is None:
            firecrawl_api_key = getattr(settings, "FIRECRAWL_API_KEY", None)
            if not firecrawl_api_key:
                raise ValueError("FIRECRAWL_API_KEY must be configured to use web fetcher")

            # Configurable semaphore limit - increase for better throughput
            # Reduced to prevent overwhelming target websites and connection pool exhaustion
            max_concurrent_requests = getattr(settings, "WEB_FETCHER_MAX_CONCURRENT", 10)  # Was 30
            _client_semaphore = asyncio.Semaphore(max_concurrent_requests)
            # Store initial value for logging purposes
            _client_semaphore._initial_value = max_concurrent_requests

            # Get the shared httpx client
            httpx_client = await get_httpx_client(logger)

            # Initialize client with our custom httpx client if supported
            try:
                # Try to pass our httpx client to Firecrawl
                _shared_firecrawl_client = AsyncFirecrawlApp(
                    api_key=firecrawl_api_key,
                    client=httpx_client,  # This may not be supported
                )
            except Exception:
                # Fallback to default client
                _shared_firecrawl_client = AsyncFirecrawlApp(
                    api_key=firecrawl_api_key,
                )

            logger.debug(
                f"🔗 WEB_CLIENT_INIT Initialized Firecrawl client "
                f"(max_concurrent={max_concurrent_requests})"
            )

    return _shared_firecrawl_client, _client_semaphore


async def get_ctti_semaphore(logger: ContextualLogger):
    """Get or create a special semaphore for CTTI entities with lower concurrency."""
    global _ctti_semaphore

    async with _ctti_semaphore_lock:
        if _ctti_semaphore is None:
            # Much lower concurrency for CTTI to avoid overwhelming their servers
            max_ctti_concurrent = getattr(settings, "CTTI_MAX_CONCURRENT", 3)  # Default to 3
            _ctti_semaphore = asyncio.Semaphore(max_ctti_concurrent)
            _ctti_semaphore._initial_value = max_ctti_concurrent
            logger.debug(
                f"🏥 CTTI_SEMAPHORE_INIT Created CTTI-specific semaphore "
                f"(max_concurrent={max_ctti_concurrent})"
            )

    return _ctti_semaphore


async def get_tavily_client(logger: ContextualLogger):
    """Get or create the shared Tavily client instance."""
    global _shared_tavily_client, _tavily_semaphore

    async with _tavily_client_lock:
        if _shared_tavily_client is None:
            tavily_api_key = getattr(settings, "TAVILY_API_KEY", None)
            if not tavily_api_key:
                raise ValueError("TAVILY_API_KEY must be configured to use Tavily web fetcher")

            from tavily import AsyncTavilyClient

            _shared_tavily_client = AsyncTavilyClient(api_key=tavily_api_key)

            max_concurrent_requests = getattr(settings, "WEB_FETCHER_MAX_CONCURRENT", 10)
            _tavily_semaphore = asyncio.Semaphore(max_concurrent_requests)
            _tavily_semaphore._initial_value = max_concurrent_requests

            logger.debug(
                f"🔗 WEB_CLIENT_INIT Initialized Tavily client "
                f"(max_concurrent={max_concurrent_requests})"
            )

    return _shared_tavily_client, _tavily_semaphore


async def _retry_with_backoff(
    func, *args, max_retries=3, entity_context="", logger: ContextualLogger, **kwargs
):
    """Retry a function with exponential backoff and improved error handling."""
    last_exception = None
    context_prefix = f"{entity_context} " if entity_context else ""

    for attempt in range(max_retries + 1):
        try:
            start_time = asyncio.get_event_loop().time()
            result = await func(*args, **kwargs)
            elapsed = asyncio.get_event_loop().time() - start_time

            if attempt > 0:  # Only log success after retry
                logger.debug(
                    f"✅ WEB_SUCCESS [{context_prefix}] "
                    f"Completed in {elapsed:.2f}s on attempt {attempt + 1}"
                )

            return result

        except Exception as e:
            elapsed = asyncio.get_event_loop().time() - start_time
            last_exception = e
            error_type = type(e).__name__
            error_msg = str(e)

            # Check for permanent errors
            permanent_errors = [
                "invalid api key",
                "unauthorized",
                "forbidden",
                "not found",
                "bad request",
                "invalid url",
                "404",
            ]

            # Check for rate limiting errors
            rate_limit_errors = ["rate limit", "too many requests", "quota exceeded", "429"]

            # Check for connection errors
            connection_errors = ["connecttimeout", "connection", "timeout", "ssl"]

            is_permanent = any(pe in error_msg.lower() for pe in permanent_errors)
            is_rate_limited = any(rl in error_msg.lower() for rl in rate_limit_errors)
            is_connection_error = any(
                ce in error_msg.lower() for ce in connection_errors
            ) or error_type in ["ConnectTimeout", "ConnectionError", "TimeoutError"]

            if is_permanent:
                logger.error(
                    f"🚫 WEB_PERMANENT_ERROR [{context_prefix}] Non-retryable error: "
                    f"{error_type}: {error_msg}"
                )
                raise e

            if attempt < max_retries:
                if is_connection_error:
                    # Longer delays for connection issues
                    base_delay = 5 * (attempt + 1)  # 5, 10, 15 seconds
                    jitter = random.uniform(1.0, 2.0)
                    delay = base_delay + jitter

                    logger.warning(
                        f"🔌 WEB_CONNECTION_ERROR [{context_prefix}] "
                        f"Connection error on attempt {attempt + 1}, retrying in {delay:.2f}s..."
                    )
                elif is_rate_limited:
                    # Medium delay for rate limiting
                    base_delay = 3 ** (attempt + 1)  # 3, 9, 27 seconds
                    jitter = random.uniform(0.5, 1.0)
                    delay = base_delay + jitter

                    logger.warning(
                        f"🚦 WEB_RATE_LIMIT [{context_prefix}] "
                        f"Rate limited, retrying in {delay:.2f}s..."
                    )
                else:
                    # Standard exponential backoff
                    base_delay = 2 * (attempt + 1)  # 2, 4, 6 seconds
                    jitter = random.uniform(0.1, 0.5)
                    delay = base_delay + jitter

                    logger.warning(
                        f"⚠️  WEB_RETRY [{context_prefix}] Attempt {attempt + 1} failed, "
                        f"retrying in {delay:.2f}s..."
                    )

                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"💥 WEB_FINAL_FAILURE [{context_prefix}] "
                    f"All attempts failed: {error_type}: {error_msg}"
                )

    raise last_exception


# NOTE: This function was previously a @transformer but transformers have been removed
# in the new sync architecture. This function is kept for potential future use or
# manual invocation, but is not automatically integrated into the sync pipeline.
async def web_fetcher(web_entity: WebEntity, logger: ContextualLogger) -> List[WebFileEntity]:
    """Fetch web content using Firecrawl and convert to FileEntity.

    This function (formerly a transformer):
    1. Takes a WebEntity with a URL
    2. Uses Firecrawl to crawl the URL and convert to markdown
       (or retrieves from storage for CTTI entities)
    3. Saves the markdown content to a local temporary file
    4. Returns a list containing a single FileEntity with local_path set,
       ready for file chunker

    NOTE: We always process entities even if content exists in storage,
    because each collection needs its own copy in the vector database.

    Args:
        web_entity: The WebEntity containing the URL to fetch
        logger: The contextual logger for logging

    Returns:
        List[WebFileEntity]: A list containing the single FileEntity with the web
        content as markdown and local_path set
    """
    entity_context = f"Entity({web_entity.entity_id})"

    logger.debug(f"🌐 WEB_START [{entity_context}] Starting web fetch for URL: {web_entity.url}")

    # Import storage manager here to avoid circular imports
    from airweave.platform.storage import sync_file_manager

    # Check if this is a CTTI entity for special handling
    is_ctti = sync_file_manager._is_ctti_entity(web_entity)

    if is_ctti:
        logger.debug(
            f"🏥 WEB_CTTI [{entity_context}] Detected CTTI entity, using global deduplication"
        )

    try:
        # Use retry logic with connection limiting
        scrape_result = await _scrape_web_content(web_entity, entity_context, logger)

        # Create and store file entity
        file_entity = await _create_and_store_file_entity(
            web_entity, scrape_result, is_ctti, entity_context, logger
        )

        return [file_entity]

    except Exception as e:
        logger.error(
            f"💥 WEB_ERROR [{entity_context}] Failed to fetch web content: "
            f"{type(e).__name__}: {str(e)}"
        )
        raise e


async def _is_entity_already_processed(
    web_entity: WebEntity, is_ctti: bool, entity_context: str
) -> bool:
    """DEPRECATED: We no longer skip entities that are already processed.

    Each collection needs its own copy in the vector database, so we always
    process entities even if they've been processed before.
    """
    # This method is kept for backwards compatibility but always returns False
    return False


async def _get_ctti_cached_content(
    web_entity: WebEntity, entity_context: str, logger: ContextualLogger
):
    """Check for and retrieve CTTI content from global storage."""
    from airweave.platform.storage import sync_file_manager

    existing_content = await sync_file_manager.get_ctti_file_content(logger, web_entity.entity_id)

    if existing_content:
        logger.debug(
            f"📥 WEB_CTTI_CACHED [{entity_context}] Retrieved CTTI content from global storage "
            f"({len(existing_content)} characters)"
        )
        return _create_mock_scrape_result(existing_content, web_entity)

    logger.debug(
        f"🌐 WEB_CTTI_NOT_CACHED [{entity_context}] CTTI content not found in storage, "
        f"will scrape from web"
    )
    return None


def _create_mock_scrape_result(markdown_content: str, web_entity: WebEntity):
    """Create a mock scrape result object that mimics Firecrawl's response."""

    class MockScrapeResult:
        def __init__(self, markdown_content: str):
            self.markdown = markdown_content

            # Try to extract title from markdown content
            title = None
            lines = markdown_content.split("\n")
            for line in lines[:10]:  # Check first 10 lines
                if line.strip().startswith("# "):
                    title = line.strip()[2:].strip()
                    break

            self.metadata = {
                "source": "azure_storage",
                "retrieved_from_cache": True,
                "title": title or f"Clinical Trial {web_entity.entity_id.split(':')[-1]}",
            }

    return MockScrapeResult(markdown_content)


def _create_tavily_scrape_result(markdown_content: str, web_entity: WebEntity):
    """Create a scrape result object from Tavily extract response."""

    class TavilyScrapeResult:
        def __init__(self, markdown_content: str):
            self.markdown = markdown_content

            # Try to extract title from markdown content
            title = None
            lines = markdown_content.split("\n")
            for line in lines[:10]:  # Check first 10 lines
                if line.strip().startswith("# "):
                    title = line.strip()[2:].strip()
                    break

            self.metadata = {
                "source": "tavily",
                "title": title or "Web Page",
            }

    return TavilyScrapeResult(markdown_content)


async def _scrape_with_firecrawl_internal(
    web_entity: WebEntity, entity_context: str, logger: ContextualLogger
):
    """Internal function to handle the actual scraping with connection limiting."""
    app, semaphore = await get_firecrawl_client(logger)

    # Check if this is a CTTI entity and use special semaphore
    from airweave.platform.storage import sync_file_manager

    is_ctti = sync_file_manager._is_ctti_entity(web_entity)

    if is_ctti:
        # Use CTTI-specific semaphore with lower concurrency
        ctti_semaphore = await get_ctti_semaphore(logger)

        # Check if we need to wait for a CTTI slot
        if ctti_semaphore._value == 0:
            logger.debug(
                f"⏳ WEB_CTTI_QUEUE [{entity_context}] Waiting for CTTI connection slot "
                f"(all {getattr(ctti_semaphore, '_initial_value', 3)} slots in use)"
            )

        # Use CTTI semaphore to limit concurrent connections to ClinicalTrials.gov
        async with ctti_semaphore:
            logger.debug(
                f"🏥 WEB_CTTI_SLOT [{entity_context}] Acquired CTTI connection slot "
                f"(active: {ctti_semaphore._initial_value - ctti_semaphore._value}"
                f"/{ctti_semaphore._initial_value})"
            )
            return await _perform_firecrawl_scrape(web_entity, entity_context, logger)
    else:
        # Use regular semaphore for non-CTTI entities
        # Check if we need to wait for a slot
        if semaphore._value == 0:
            logger.debug(
                f"⏳ WEB_QUEUE [{entity_context}] Waiting for connection slot "
                f"(all {getattr(semaphore, '_initial_value', 10)} slots in use)"
            )

        # Use semaphore to limit concurrent connections
        async with semaphore:
            return await _perform_firecrawl_scrape(web_entity, entity_context, logger)


async def _perform_firecrawl_scrape(
    web_entity: WebEntity, entity_context: str, logger: ContextualLogger
):
    """Perform the actual Firecrawl scrape with timeout handling."""
    app, _ = await get_firecrawl_client(logger)

    # Log the current semaphore state
    _, semaphore = await get_firecrawl_client(logger)
    available_slots = semaphore._value
    total_slots = getattr(semaphore, "_initial_value", 10)
    queue_size = total_slots - available_slots

    logger.debug(
        f"🔗 WEB_CONNECT [{entity_context}] Acquired connection slot "
        f"(active: {queue_size}/{total_slots}, available: {available_slots})"
    )

    logger.debug(f"📥 WEB_SCRAPE [{entity_context}] Scraping URL: {web_entity.url}")
    scrape_start = asyncio.get_event_loop().time()

    # Start with shorter timeout, retry with longer if needed
    # Increased timeouts for slow CTTI pages that can take 40-80 seconds
    timeouts = [60.0, 90.0, 120.0]  # Was [10.0, 20.0, 30.0]

    scrape_result = await _try_scrape_with_timeouts(
        app, web_entity, timeouts, entity_context, logger
    )

    scrape_elapsed = asyncio.get_event_loop().time() - scrape_start

    if not scrape_result or not hasattr(scrape_result, "markdown") or not scrape_result.markdown:
        logger.warning(f"📭 WEB_EMPTY [{entity_context}] No markdown content returned")
        raise ValueError(f"No content extracted from URL: {web_entity.url}")

    content_length = len(scrape_result.markdown)
    logger.debug(
        f"📄 WEB_CONTENT [{entity_context}] Received {content_length} characters "
        f"in {scrape_elapsed:.2f}s"
    )

    return scrape_result


async def _try_scrape_with_timeouts(
    app, web_entity: WebEntity, timeouts: list, entity_context: str, logger: ContextualLogger
):
    """Try scraping with progressively longer timeouts."""
    # Check if this is a CTTI entity for special timeout handling
    from airweave.platform.storage import sync_file_manager

    is_ctti = sync_file_manager._is_ctti_entity(web_entity)

    # Use longer timeouts for CTTI entities
    if is_ctti:
        # Much longer timeouts for slow CTTI pages
        timeouts = [120.0, 180.0, 240.0]  # 2, 3, 4 minutes
        logger.debug(
            f"🏥 WEB_CTTI_TIMEOUTS [{entity_context}] Using extended timeouts for CTTI: {timeouts}"
        )

    for timeout in timeouts:
        try:
            return await asyncio.wait_for(
                app.scrape_url(
                    web_entity.url,
                    formats=["markdown"],
                    include_tags=["ctg-study-details-top-info", "ctg-study-info"],
                    only_main_content=True,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            if timeout == timeouts[-1]:
                raise
            logger.warning(
                f"⏱️  WEB_TIMEOUT [{entity_context}] Timed out after {timeout}s, "
                f"retrying with {timeouts[timeouts.index(timeout) + 1]}s timeout"
            )


async def _scrape_with_tavily_internal(
    web_entity: WebEntity, entity_context: str, logger: ContextualLogger
):
    """Internal function to handle scraping with Tavily Extract."""
    _, semaphore = await get_tavily_client(logger)

    if semaphore._value == 0:
        logger.debug(
            f"⏳ WEB_QUEUE [{entity_context}] Waiting for Tavily connection slot "
            f"(all {getattr(semaphore, '_initial_value', 10)} slots in use)"
        )

    async with semaphore:
        return await _perform_tavily_scrape(web_entity, entity_context, logger)


async def _perform_tavily_scrape(
    web_entity: WebEntity, entity_context: str, logger: ContextualLogger
):
    """Perform the actual Tavily extract with timeout handling."""
    client, _ = await get_tavily_client(logger)

    logger.debug(f"📥 WEB_SCRAPE [{entity_context}] Extracting URL via Tavily: {web_entity.url}")
    scrape_start = asyncio.get_event_loop().time()

    response = await asyncio.wait_for(
        client.extract(
            urls=[web_entity.url],
            extract_depth="advanced",
        ),
        timeout=120.0,
    )

    scrape_elapsed = asyncio.get_event_loop().time() - scrape_start

    # Extract content from response
    results = response.get("results", [])
    failed = response.get("failed_results", [])

    if not results:
        if failed:
            error = failed[0].get("error", "unknown error")
            logger.warning(f"📭 WEB_EMPTY [{entity_context}] Tavily extraction failed: {error}")
        else:
            logger.warning(f"📭 WEB_EMPTY [{entity_context}] No content returned from Tavily")
        raise ValueError(f"No content extracted from URL: {web_entity.url}")

    raw_content = results[0].get("raw_content", "")
    if not raw_content:
        logger.warning(f"📭 WEB_EMPTY [{entity_context}] Tavily returned empty content")
        raise ValueError(f"No content extracted from URL: {web_entity.url}")

    logger.debug(
        f"📄 WEB_CONTENT [{entity_context}] Received {len(raw_content)} characters "
        f"via Tavily in {scrape_elapsed:.2f}s"
    )

    return _create_tavily_scrape_result(raw_content, web_entity)


async def _scrape_web_content(web_entity: WebEntity, entity_context: str, logger: ContextualLogger):
    """Scrape web content using Firecrawl/Tavily or retrieve from storage for CTTI entities."""
    # Import storage manager here to avoid circular imports
    from airweave.platform.storage import sync_file_manager

    # Check if this is a CTTI entity that already exists in global storage
    is_ctti = sync_file_manager._is_ctti_entity(web_entity)

    if is_ctti:
        cached_result = await _get_ctti_cached_content(web_entity, entity_context, logger)
        if cached_result:
            return cached_result

    # Select scraping backend based on WEB_EXTRACTOR_BACKEND setting
    web_backend = getattr(settings, "WEB_EXTRACTOR_BACKEND", "firecrawl")
    if web_backend == "tavily":
        return await _retry_with_backoff(
            _scrape_with_tavily_internal,
            web_entity,
            entity_context,
            entity_context=entity_context,
            logger=logger,
        )

    return await _retry_with_backoff(
        _scrape_with_firecrawl_internal,
        web_entity,
        entity_context,
        entity_context=entity_context,
        logger=logger,
    )


async def _create_and_store_file_entity(
    web_entity: WebEntity,
    scrape_result,
    is_ctti: bool,
    entity_context: str,
    logger: ContextualLogger,
) -> WebFileEntity:
    """Create file entity from scraped content and store it."""
    # Streamlined file processing
    logger.debug(f"💾 WEB_FILE_START [{entity_context}] Creating temporary file")

    # Get markdown content and metadata
    markdown_content = scrape_result.markdown
    metadata = scrape_result.metadata if hasattr(scrape_result, "metadata") else {}

    # Extract title
    if isinstance(metadata, dict):
        title = web_entity.title or metadata.get("title", "Web Page")
    else:
        title = web_entity.title or getattr(metadata, "title", "Web Page")

    # Generate file metadata
    file_uuid = uuid4()
    safe_title = title.replace("/", "_").replace("\\", "_")[:100]  # Limit title length
    safe_filename = f"{file_uuid}-{safe_title}.md"

    # Use storage manager's temp directory
    base_temp_dir = "/tmp/airweave/processing"
    os.makedirs(base_temp_dir, exist_ok=True)
    temp_file_path = os.path.join(base_temp_dir, safe_filename)

    # Write file asynchronously
    async with aiofiles.open(temp_file_path, "w", encoding="utf-8") as f:
        await f.write(markdown_content)

    # Calculate file size and checksum in parallel with file write
    def _calculate_file_metrics(content: str):
        encoded_content = content.encode("utf-8")
        file_size = len(encoded_content)
        checksum = hashlib.sha256(encoded_content).hexdigest()
        return file_size, checksum

    file_size, checksum = await run_in_thread_pool(_calculate_file_metrics, markdown_content)

    # Create enhanced metadata
    enhanced_metadata = _create_enhanced_metadata(web_entity, title, markdown_content, is_ctti)

    # Create WebFileEntity
    file_entity = _create_web_file_entity(
        web_entity,
        title,
        file_size,
        temp_file_path,
        file_uuid,
        checksum,
        metadata,
        enhanced_metadata,
    )

    # Populate FileSystemMetadata fields after construction to satisfy model typing
    # WebFileEntity.airweave_system_metadata is FileSystemMetadata (auto-created)
    try:
        fsm = file_entity.airweave_system_metadata
        if fsm is not None:
            fsm.file_uuid = file_uuid
            fsm.local_path = temp_file_path
            fsm.checksum = checksum
            fsm.total_size = file_size
            # carry over source context if present on the web entity
            if (
                hasattr(web_entity, "airweave_system_metadata")
                and web_entity.airweave_system_metadata is not None
            ):
                fsm.source_name = web_entity.airweave_system_metadata.source_name
                fsm.entity_type = web_entity.airweave_system_metadata.entity_type
                fsm.sync_id = web_entity.airweave_system_metadata.sync_id
                fsm.sync_job_id = web_entity.airweave_system_metadata.sync_job_id
    except Exception:
        # Do not fail transformation if metadata population fails
        pass

    # Store in persistent storage
    await _store_file_entity(file_entity, temp_file_path, is_ctti, entity_context, logger)

    logger.debug(
        f"✅ WEB_COMPLETE [{entity_context}] Successfully created FileEntity ({file_size} bytes)"
    )

    return file_entity


def _create_enhanced_metadata(
    web_entity: WebEntity, title: str, markdown_content: str, is_ctti: bool
) -> dict:
    """Create enhanced metadata for the file entity."""
    enhanced_metadata = {
        "url": web_entity.url,
        "title": title,
        "content_length": len(markdown_content),
        **(web_entity.metadata or {}),
    }

    # Add CTTI source marker if this is a CTTI entity
    if is_ctti:
        enhanced_metadata["source"] = "CTTI"

    return enhanced_metadata


def _create_web_file_entity(
    web_entity: WebEntity,
    title: str,
    file_size: int,
    temp_file_path: str,
    file_uuid,
    checksum: str,
    metadata,
    enhanced_metadata: dict,
) -> WebFileEntity:
    """Create WebFileEntity with optimized field copying."""
    return WebFileEntity(
        entity_id=web_entity.entity_id,
        file_id=f"web_{web_entity.entity_id}",
        name=f"{title}.md",
        mime_type="text/markdown",
        size=file_size,
        download_url=web_entity.url,
        url=web_entity.url,
        # Copy BaseEntity fields
        breadcrumbs=web_entity.breadcrumbs,
        parent_entity_id=web_entity.parent_entity_id,
        # WebFileEntity specific
        original_url=web_entity.url,
        crawl_metadata=metadata,
        web_title=title,
        web_description=metadata.get("description", "") if isinstance(metadata, dict) else "",
        # Enhanced metadata
        metadata=enhanced_metadata,
    )


async def _store_file_entity(
    file_entity: WebFileEntity,
    temp_file_path: str,
    is_ctti: bool,
    entity_context: str,
    logger: ContextualLogger,
) -> None:
    """Store file entity in persistent storage."""
    from airweave.platform.storage import sync_file_manager

    if is_ctti:
        # Check if CTTI file already exists in global storage
        if await sync_file_manager.check_ctti_file_exists(logger, file_entity.entity_id):
            logger.debug(
                f"💾 WEB_CTTI_EXISTS [{entity_context}] "
                f"CTTI file already exists in global storage, skipping upload"
            )
            # Still set the storage metadata on the entity
            safe_filename = file_entity.entity_id.replace(":", "_").replace("/", "_") + ".md"
            if file_entity.airweave_system_metadata is not None:
                file_entity.airweave_system_metadata.storage_blob_name = safe_filename
            if not hasattr(file_entity, "metadata") or file_entity.metadata is None:
                file_entity.metadata = {}
            file_entity.metadata["ctti_container"] = "aactmarkdowns"
            file_entity.metadata["ctti_blob_name"] = safe_filename
            file_entity.metadata["ctti_global_storage"] = True
        else:
            # Use CTTI-specific storage (global deduplication)
            with open(temp_file_path, "rb") as f:
                file_entity = await sync_file_manager.store_ctti_file(logger, file_entity, f)

            logger.debug(
                f"💾 WEB_CTTI_STORED [{entity_context}] "
                f"Stored CTTI file globally: {file_entity.storage_blob_name}"
            )
    else:
        # Non-CTTI: Use standard sync-based storage
        # (file will be uploaded by FileDownloadService when needed)
        logger.debug(
            f"💾 WEB_FILE_CREATED [{entity_context}] Created local file at {temp_file_path}"
        )
