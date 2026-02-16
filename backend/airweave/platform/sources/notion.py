"""Notion connector for syncing content from Notion workspaces to Airweave.

This module provides a comprehensive source implementation for extracting databases and pages
with full aggregated content from Notion, handling API rate limits, and converting API
responses to entity objects.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import httpx
from httpx import HTTPStatusError, ReadTimeout, TimeoutException
from tenacity import retry, retry_if_exception_type, stop_after_attempt

from airweave.core.logging import logger
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.config import NotionConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.notion import (
    NotionDatabaseEntity,
    NotionFileEntity,
    NotionPageEntity,
    NotionPropertyEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import wait_rate_limit_with_backoff
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Notion",
    short_name="notion",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=None,
    config_class=NotionConfig,
    labels=["Knowledge Base", "Productivity"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.CONNECTION,
)
class NotionSource(BaseSource):
    """Notion source connector integrates with the Notion API to extract and synchronize content.

    Connects to your Notion workspace.

    It provides comprehensive access to databases, pages, and content with advanced content
    aggregation, lazy loading, and file processing capabilities for optimal performance.
    """

    # Rate limiting constants
    TIMEOUT_SECONDS = 60.0  # Increased from 30.0
    RATE_LIMIT_REQUESTS = 2  # Reduced from 3 to be more conservative
    RATE_LIMIT_PERIOD = 1.0  # Time period in seconds
    MAX_RETRIES = 5  # Increased from 3

    class NotionAccessError(Exception):
        """Non-retryable access/shape error from Notion.

        Raised for permission or structural cases that won't succeed on retry
        (e.g., 403/404, or specific 400 validation for linked views).
        """

        def __init__(self, status: int, message: str, url: str):
            """Initialize a non-retryable Notion access/shape error.

            Args:
                status: HTTP status code returned by Notion.
                message: Short explanation extracted from Notion's response.
                url: The Notion API URL that was called.
            """
            super().__init__(f"HTTP {status} - {message} ({url})")
            self.status = status
            self.message = message
            self.url = url

    @classmethod
    async def create(cls, access_token, config: Optional[Dict[str, Any]] = None) -> "NotionSource":
        """Create a new Notion source."""
        logger.debug("Creating new Notion source")
        instance = cls()
        instance.access_token = access_token

        # ---- per-instance materialization controls (match Drive-style knobs) ----
        config = config or {}
        try:
            instance.batch_generation = bool(
                config.get("batch_generation", instance.batch_generation)
            )
        except Exception:
            pass
        try:
            instance.batch_size = int(config.get("batch_size", 30))
        except Exception:
            pass
        # Rebuild the gate in case batch_size changed
        instance._materialize_semaphore = asyncio.Semaphore(instance.batch_size)

        return instance

    async def validate(self) -> bool:
        """Validate the Notion source."""
        return await self._validate_oauth2(
            ping_url="https://api.notion.com/v1/users/me",
            headers={"Notion-Version": "2022-06-28"},
        )

    def __init__(self):
        """Initialize rate limiting state and tracking."""
        super().__init__()
        self._request_times = []
        self._lock = asyncio.Lock()
        self._processed_pages: Set[str] = set()
        self._processed_databases: Set[str] = set()
        self._child_databases_to_process: Set[str] = set()
        self._child_database_breadcrumbs: Dict[str, List[Breadcrumb]] = {}
        self._stats = {
            "api_calls": 0,
            "rate_limit_waits": 0,
            "databases_found": 0,
            "child_databases_found": 0,
            "pages_found": 0,
            "total_blocks_processed": 0,
            "total_files_found": 0,
            "max_page_depth": 0,
        }
        logger.debug("Initialized comprehensive Notion source with content aggregation")

    async def _wait_for_rate_limit(self):
        """Implement rate limiting for Notion API requests."""
        async with self._lock:
            current_time = asyncio.get_event_loop().time()

            # Remove old request times
            self._request_times = [
                t for t in self._request_times if current_time - t < self.RATE_LIMIT_PERIOD
            ]

            if len(self._request_times) >= self.RATE_LIMIT_REQUESTS:
                # Wait until enough time has passed
                sleep_time = self._request_times[0] + self.RATE_LIMIT_PERIOD - current_time
                if sleep_time > 0:
                    self.logger.debug(
                        f"Rate limit reached. Waiting {sleep_time:.2f}s before next request"
                    )
                    self._stats["rate_limit_waits"] += 1
                    await asyncio.sleep(sleep_time)

                # Clean up old requests again after waiting
                current_time = asyncio.get_event_loop().time()
                self._request_times = [
                    t for t in self._request_times if current_time - t < self.RATE_LIMIT_PERIOD
                ]

            self._request_times.append(current_time)

    def _should_retry_request(self, exception: Exception) -> bool:
        """Determine if a request should be retried based on the exception."""
        if isinstance(exception, (TimeoutException, ReadTimeout)):
            return True
        if isinstance(exception, HTTPStatusError):
            # Retry on 429 (rate limit) and 502/503/504 (server errors)
            return exception.response.status_code in {429, 502, 503, 504}
        return False

    @retry(
        retry=retry_if_exception_type((TimeoutException, ReadTimeout, HTTPStatusError)),
        stop=stop_after_attempt(5),
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> dict:
        """Make an authenticated GET request to the Notion API."""
        await self._wait_for_rate_limit()
        self.logger.debug(f"GET request to {url}")
        self._stats["api_calls"] += 1

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Notion-Version": "2022-06-28",
        }

        try:
            response = await client.get(url, headers=headers, timeout=self.TIMEOUT_SECONDS)
            status = response.status_code
            self.logger.debug(f"GET response from {url}: status={status}")

            if status != 200:
                body_text = response.text[:200] if getattr(response, "text", None) else ""
                self.logger.warning(f"Non-200 response from Notion API: {status} for {url}")
                self.logger.debug(f"Response body: {body_text}...")

                # Determine path
                is_pages = "/v1/pages/" in url
                is_databases = "/v1/databases/" in url

                # Parse message if available
                msg = body_text
                try:
                    body_json = response.json()
                    if isinstance(body_json, dict):
                        msg = str(body_json.get("message", msg))
                except Exception:
                    pass

                # Non-retryable: inaccessible parents (404/403) or child DB validation 400
                if is_pages and status in (403, 404):
                    raise NotionSource.NotionAccessError(status, msg or "access denied", url)
                if is_databases and (
                    status in (403, 404)
                    or (
                        status == 400 and "does not contain any data sources" in (msg or "").lower()
                    )
                ):
                    raise NotionSource.NotionAccessError(status, msg or "validation_error", url)

            # Fallback to standard behavior (lets tenacity retry on HTTPStatusError)
            response.raise_for_status()
            return response.json()
        except NotionSource.NotionAccessError as e:
            # Known inaccessibility: log as warning (no retry by design)
            self.logger.warning(f"Error during GET request to {url}: {str(e)}")
            raise
        except Exception as e:
            self.logger.warning(f"Error during GET request to {url}: {str(e)}")
            raise

    @retry(
        retry=retry_if_exception_type((TimeoutException, ReadTimeout, HTTPStatusError)),
        stop=stop_after_attempt(5),
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post_with_auth(self, client: httpx.AsyncClient, url: str, json_data: dict) -> dict:
        """Make an authenticated POST request to the Notion API."""
        await self._wait_for_rate_limit()
        self.logger.debug(f"POST request to {url}")
        self._stats["api_calls"] += 1

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Notion-Version": "2022-06-28",
        }

        try:
            response = await client.post(
                url, headers=headers, json=json_data, timeout=self.TIMEOUT_SECONDS
            )
            self.logger.debug(f"POST response from {url}: status={response.status_code}")

            if response.status_code != 200:
                self.logger.warning(
                    f"Non-200 response from Notion API: {response.status_code} for {url}"
                )
                self.logger.debug(f"Response body: {response.text[:200]}...")

            response.raise_for_status()
            return response.json()
        except NotionSource.NotionAccessError as e:
            # Not used in POST flow currently, keep symmetry if added later
            self.logger.warning(f"Error during POST request to {url}: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Error during POST request to {url}: {str(e)}")
            raise

    async def _search_objects(  # noqa: C901
        self, client: httpx.AsyncClient, object_type: str
    ) -> AsyncGenerator[dict, None]:
        """Search for objects of a specific type, excluding archived objects."""
        url = "https://api.notion.com/v1/search"
        has_more = True
        start_cursor = None

        total_found = 0
        total_filtered = 0

        while has_more:
            json_data = {
                "filter": {"property": "object", "value": object_type},
                "page_size": 100,
            }

            if start_cursor:
                json_data["start_cursor"] = start_cursor

            try:
                response = await self._post_with_auth(client, url, json_data)
                results = response.get("results", [])
                total_found += len(results)

                self.logger.debug(
                    f"🔍 Search returned {len(results)} {object_type}(s) in this batch"
                )

                # Filter out archived and trashed objects
                # Notion search API returns archived and trashed objects by default
                filtered_count = 0
                yielded_count_batch = 0
                for obj in results:
                    obj_id = obj.get("id", "unknown")
                    is_archived = obj.get("archived", False)
                    is_trashed = obj.get("in_trash", False)

                    # Extract title for better logging
                    obj_title = "Unknown"
                    if object_type == "page":
                        title_prop = obj.get("properties", {}).get("title", {})
                        title_content = title_prop.get("title", [])
                        if title_content and len(title_content) > 0:
                            obj_title = title_content[0].get("text", {}).get("content", "Unknown")
                    elif object_type == "database":
                        title_list = obj.get("title", [])
                        if title_list and len(title_list) > 0:
                            obj_title = title_list[0].get("text", {}).get("content", "Unknown")

                    if is_archived or is_trashed:
                        filtered_count += 1
                        total_filtered += 1
                        status = []
                        if is_archived:
                            status.append("archived")
                        if is_trashed:
                            status.append("trashed")
                        self.logger.warning(
                            f"🗑️  FILTERED OUT {object_type}: '{obj_title}' [{obj_id}] "
                            f"- Status: {', '.join(status)}"
                        )
                    else:
                        yielded_count_batch += 1
                        self.logger.debug(
                            f"✅ YIELDING {object_type}: '{obj_title}' [{obj_id}] "
                            f"(archived={is_archived}, in_trash={is_trashed})"
                        )
                        yield obj

                self.logger.debug(
                    f"📊 Batch complete: yielded {yielded_count_batch}, "
                    f"filtered {filtered_count} {object_type}(s)"
                )

                if filtered_count > 0:
                    self.logger.warning(
                        f"⚠️  Filtered {filtered_count} {object_type}(s) in this batch "
                        f"(archived or trashed)"
                    )

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            except NotionSource.NotionAccessError as e:
                self.logger.warning(f"Search access issue for {object_type}: {str(e)}")
                raise
            except Exception as e:
                self.logger.error(f"Error searching for {object_type}: {str(e)}")
                raise

        # Log summary after all pages processed
        yielded_count = total_found - total_filtered
        self.logger.debug(
            f"📊 Search complete for {object_type}: "
            f"found={total_found}, filtered={total_filtered}, yielded={yielded_count}"
        )

    async def _query_database_pages(  # noqa: C901
        self, client: httpx.AsyncClient, database_id: str
    ) -> AsyncGenerator[dict, None]:
        """Query all pages in a database, excluding archived pages.

        Note: The 'archived' attribute is a page-level property, not a database property,
        so it cannot be filtered via the database query filter. We filter client-side instead.
        """
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        has_more = True
        start_cursor = None

        total_found = 0
        total_filtered = 0

        while has_more:
            json_data = {"page_size": 100}
            if start_cursor:
                json_data["start_cursor"] = start_cursor

            try:
                response = await self._post_with_auth(client, url, json_data)
                results = response.get("results", [])
                total_found += len(results)

                self.logger.debug(
                    f"🔍 Database query returned {len(results)} page(s) for database {database_id}"
                )

                # Client-side filter: exclude archived and trashed pages
                # Notion API returns archived and trashed pages by default, but we skip them
                filtered_count = 0
                yielded_count_batch = 0
                for page in results:
                    page_id = page.get("id", "unknown")
                    is_archived = page.get("archived", False)
                    is_trashed = page.get("in_trash", False)

                    # Extract title for better logging
                    page_title = "Unknown"
                    title_prop = page.get("properties", {}).get("title", {})
                    title_content = title_prop.get("title", [])
                    if title_content and len(title_content) > 0:
                        page_title = title_content[0].get("text", {}).get("content", "Unknown")

                    if is_archived or is_trashed:
                        filtered_count += 1
                        total_filtered += 1
                        status = []
                        if is_archived:
                            status.append("archived")
                        if is_trashed:
                            status.append("trashed")
                        self.logger.warning(
                            f"🗑️  FILTERED OUT page: '{page_title}' [{page_id}] "
                            f"from database {database_id} - Status: {', '.join(status)}"
                        )
                    else:
                        yielded_count_batch += 1
                        self.logger.debug(
                            f"✅ YIELDING page: '{page_title}' [{page_id}] "
                            f"from database (archived={is_archived}, in_trash={is_trashed})"
                        )
                        yield page

                self.logger.debug(
                    f"📊 Database batch complete: yielded {yielded_count_batch}, "
                    f"filtered {filtered_count} page(s)"
                )

                if filtered_count > 0:
                    self.logger.warning(
                        f"⚠️  Filtered {filtered_count} page(s) in this batch (archived or trashed)"
                    )

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            except NotionSource.NotionAccessError as e:
                self.logger.warning(f"Database query access issue for {database_id}: {str(e)}")
                raise
            except Exception as e:
                self.logger.error(f"Error querying database {database_id}: {str(e)}")
                raise

        # Log summary after all pages processed
        yielded_count = total_found - total_filtered
        self.logger.debug(
            f"📊 Database query complete for {database_id}: "
            f"found={total_found}, filtered={total_filtered}, yielded={yielded_count}"
        )

    # Child Database Processing
    async def _process_child_databases(  # noqa: C901 - complex loop over child DB traversal
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process child databases discovered during page content extraction."""
        self.logger.debug("Processing child databases")

        # Process child databases until no new ones are discovered
        while self._child_databases_to_process:
            # Get databases that haven't been processed yet
            unprocessed_databases = [
                db_id
                for db_id in self._child_databases_to_process
                if db_id not in self._processed_databases
            ]

            if not unprocessed_databases:
                break

            self.logger.debug(f"Processing {len(unprocessed_databases)} child databases")

            for database_id in unprocessed_databases:
                try:
                    self.logger.debug(f"Processing child database: {database_id}")

                    # Get database schema
                    schema = await self._get_with_auth(
                        client, f"https://api.notion.com/v1/databases/{database_id}"
                    )

                    # Get breadcrumbs for this child database
                    breadcrumbs = self._child_database_breadcrumbs.get(database_id, [])

                    # Create database entity with proper breadcrumbs
                    database_entity = self._create_database_entity(schema)
                    database_entity.breadcrumbs = breadcrumbs
                    yield database_entity
                    self._processed_databases.add(database_id)

                    # Process all pages in this child database
                    async for page in self._query_database_pages(client, database_id):
                        page_id = page["id"]
                        if page_id in self._processed_pages:
                            continue

                        try:
                            # Create breadcrumbs for child database pages
                            db_breadcrumb = Breadcrumb(
                                entity_id=database_id,
                                name=database_entity.title,
                                entity_type=NotionDatabaseEntity.__name__,
                            )
                            page_breadcrumbs = breadcrumbs + [db_breadcrumb]

                            # Eagerly build page and files for child database page
                            page_entity, files = await self._create_comprehensive_page_entity(
                                client, page, page_breadcrumbs, database_id, schema
                            )
                            yield page_entity

                            for file_entity in files:
                                processed = await self._process_and_yield_file(file_entity)
                                if processed:
                                    yield processed

                            self._processed_pages.add(page_id)

                        except NotionSource.NotionAccessError as e:
                            self.logger.warning(
                                f"Access issue processing child database page {page_id}: {str(e)}"
                            )
                            continue
                        except Exception as e:
                            self.logger.error(
                                f"Error processing child database page {page_id}: {str(e)}"
                            )
                            continue

                except NotionSource.NotionAccessError as e:
                    status = e.status
                    self.logger.warning(
                        f"Child database {database_id} not accessible ({status}). Skipping."
                    )
                    self._processed_databases.add(database_id)
                    continue
                except httpx.HTTPStatusError as e:
                    status = e.response.status_code
                    msg = ""
                    try:
                        body = e.response.json()
                        msg = body.get("message", "") or ""
                    except Exception:
                        pass

                    inaccessible = status in (404, 403) or (
                        status == 400 and "does not contain any data sources" in msg.lower()
                    )

                    if inaccessible:
                        self.logger.warning(
                            f"Child database {database_id} not accessible ({status}). Skipping."
                        )
                        # Mark as processed to avoid retrying forever
                        self._processed_databases.add(database_id)
                        continue

                    self.logger.error(
                        f"HTTP error processing child database {database_id}: {str(e)}"
                    )
                    # Also mark as processed to avoid tight retry loops on persistent errors
                    self._processed_databases.add(database_id)
                    continue
                except Exception as e:
                    self.logger.error(f"Error processing child database {database_id}: {str(e)}")
                    continue

    async def _build_page_breadcrumbs(
        self, client: httpx.AsyncClient, page: dict
    ) -> List[Breadcrumb]:
        """Build breadcrumbs for a page by traversing up the parent hierarchy."""
        breadcrumbs = []
        current_page = page

        while True:
            parent = current_page.get("parent", {})
            parent_type = parent.get("type", "")

            if parent_type == "page_id":
                parent_id = parent.get("page_id")
                try:
                    parent_page = await self._get_with_auth(
                        client, f"https://api.notion.com/v1/pages/{parent_id}"
                    )
                    parent_title = self._extract_page_title(parent_page) or "Untitled Page"
                    breadcrumbs.insert(
                        0,
                        Breadcrumb(
                            entity_id=parent_id,
                            name=parent_title,
                            entity_type=NotionPageEntity.__name__,
                        ),
                    )
                    current_page = parent_page
                except Exception as e:
                    self.logger.warning(f"Could not fetch parent page {parent_id}: {str(e)}")
                    break
            elif parent_type == "database_id":
                # This shouldn't happen for standalone pages, but handle it
                break
            else:
                # Reached workspace level
                break

        return breadcrumbs

    # Comprehensive Page Entity Creation with Content Aggregation
    async def _create_comprehensive_page_entity(
        self,
        client: httpx.AsyncClient,
        page: dict,
        breadcrumbs: List[Breadcrumb],
        database_id: Optional[str] = None,
        database_schema: Optional[dict] = None,
    ) -> Tuple[NotionPageEntity, List[NotionFileEntity]]:
        """Create a comprehensive page entity with full aggregated content."""
        page_id = page["id"]
        title = self._extract_page_title(page)
        is_archived = page.get("archived", False)
        is_trashed = page.get("in_trash", False)

        # Log page state for debugging
        status_flags = []
        if is_archived:
            status_flags.append("ARCHIVED")
        if is_trashed:
            status_flags.append("TRASHED")
        status_str = f" [{', '.join(status_flags)}]" if status_flags else ""

        self.logger.debug(f"📝 Processing page: {title} ({page_id}){status_str}")

        # Warn if processing a trashed/archived page (should not happen)
        if is_archived or is_trashed:
            self.logger.error(
                f"❌ UNEXPECTED: Processing {status_str.strip('[]')} page {page_id}! "
                f"This should have been filtered earlier."
            )

        # Reset child database tracking for this page
        self._child_databases_to_process.clear()

        # Aggregate all content from blocks
        content_result = await self._aggregate_page_content(client, page_id, breadcrumbs)

        # Extract properties if this is a database page
        property_entities = []
        formatted_properties = {}  # New: formatted properties dict
        if database_id and database_schema:
            property_entities = await self._extract_page_properties(
                page, database_id, database_schema
            )
            # Create formatted properties dict for better searchability
            formatted_properties = self._create_formatted_properties_dict(
                page.get("properties", {}), database_schema.get("properties", {})
            )

        # Create the comprehensive page entity
        parent = page.get("parent", {})

        # Generate human-readable properties text
        properties_text = self._generate_properties_text_for_page(formatted_properties, title)
        created_time = self._parse_datetime(page.get("created_time"))
        updated_time = self._parse_datetime(page.get("last_edited_time"))
        page_url = page.get("url", "")

        page_entity = NotionPageEntity(
            # Base fields
            entity_id=page_id,
            breadcrumbs=breadcrumbs,
            name=title,
            created_at=created_time,
            updated_at=updated_time,
            # API fields
            page_id=page_id,
            parent_id=parent.get("page_id") or parent.get("database_id") or "",
            parent_type=parent.get("type", "workspace"),
            title=title,
            created_time=created_time,
            updated_time=updated_time,
            content=content_result["content"],
            properties=formatted_properties,  # Use formatted properties instead of raw
            properties_text=properties_text,  # Add formatted text for embedding
            property_entities=property_entities,
            files=[],  # Don't include files in page entity - they'll be yielded separately
            icon=page.get("icon"),
            cover=page.get("cover"),
            archived=page.get("archived", False),
            in_trash=page.get("in_trash", False),
            url=page_url,
            content_blocks_count=content_result["blocks_count"],
            max_depth=content_result["max_depth"],
        )

        # Set breadcrumbs on file entities
        files_with_breadcrumbs = []
        for file_entity in content_result["files"]:
            file_entity.breadcrumbs = breadcrumbs.copy()
            files_with_breadcrumbs.append(file_entity)

        self.logger.debug(
            f"Page entity created: {len(content_result['content'])} chars, "
            f"{content_result['blocks_count']} blocks, "
            f"{len(files_with_breadcrumbs)} files, "
            f"max depth {content_result['max_depth']}"
        )

        return page_entity, files_with_breadcrumbs

    async def _aggregate_page_content(
        self, client: httpx.AsyncClient, page_id: str, page_breadcrumbs: List[Breadcrumb]
    ) -> Dict[str, Any]:
        """Aggregate all content from a page into a single markdown string."""
        content_parts = []
        files = []
        blocks_count = 0
        max_depth = 0

        async for block_content in self._extract_blocks_recursive(
            client, page_id, 0, page_breadcrumbs
        ):
            content_parts.append(block_content["content"])
            files.extend(block_content["files"])
            blocks_count += 1
            max_depth = max(max_depth, block_content["depth"])
            self._stats["total_blocks_processed"] += 1

        # Update global stats
        if max_depth > self._stats["max_page_depth"]:
            self._stats["max_page_depth"] = max_depth

        self._stats["total_files_found"] += len(files)

        # Join all content with appropriate spacing
        full_content = "\n\n".join(filter(None, content_parts))

        # Clean up content for embedding (remove huge URLs, etc.)
        cleaned_content = self.clean_content_for_embedding(full_content)

        return {
            "content": cleaned_content,
            "files": files,
            "blocks_count": blocks_count,
            "max_depth": max_depth,
        }

    async def _extract_blocks_recursive(
        self,
        client: httpx.AsyncClient,
        block_id: str,
        depth: int,
        page_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Recursively extract and format blocks into markdown content."""
        url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        has_more = True
        start_cursor = None

        while has_more:
            url_with_params = url if not start_cursor else f"{url}?start_cursor={start_cursor}"

            try:
                response = await self._get_with_auth(client, url_with_params)
                if not self._is_valid_response(response, block_id):
                    break

                blocks = response.get("results", [])
                async for result in self._process_blocks(
                    client, blocks, block_id, depth, page_breadcrumbs
                ):
                    yield result

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            except NotionSource.NotionAccessError as e:
                self.logger.warning(f"Access issue extracting blocks from {block_id}: {str(e)}")
                break
            except Exception as e:
                self.logger.error(
                    f"Error extracting blocks from {block_id}: {type(e).__name__}: {str(e)}"
                )
                break

    def _is_valid_response(self, response: Any, block_id: str) -> bool:
        """Validate API response format."""
        if not response or not isinstance(response, dict):
            self.logger.warning(
                f"Invalid response format for blocks from {block_id}: {type(response)}"
            )
            return False
        return True

    async def _process_blocks(
        self,
        client: httpx.AsyncClient,
        blocks: List[dict],
        block_id: str,
        depth: int,
        page_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process a list of blocks and their children."""
        for block in blocks:
            if not block or not isinstance(block, dict):
                self.logger.warning(f"Skipping invalid block in {block_id}: {type(block)}")
                continue

            block_result = await self._format_block_content(block, depth, page_breadcrumbs)
            if block_result and block_result.get("content"):
                yield block_result

            if block.get("has_children", False) and block.get("id"):
                async for child_result in self._extract_blocks_recursive(
                    client, block["id"], depth + 1, page_breadcrumbs
                ):
                    yield child_result

    async def _format_block_content(
        self, block: dict, depth: int, page_breadcrumbs: List[Breadcrumb]
    ) -> Dict[str, Any]:
        """Format a single block into markdown content."""
        if not self._validate_block(block):
            return {"content": "", "files": [], "depth": depth}

        block_type = block.get("type", "")
        if not block_type:
            self.logger.warning(f"Block missing type field: {block.get('id', 'unknown')}")
            return {"content": "", "files": [], "depth": depth}

        block_content = block.get(block_type, {}) or {}
        content, files = self._dispatch_block_formatter(
            block_type, block_content, block, depth, page_breadcrumbs
        )

        return {"content": content, "files": files, "depth": depth}

    def _validate_block(self, block: dict) -> bool:
        """Validate block structure."""
        if not block or not isinstance(block, dict):
            self.logger.warning(f"Invalid block format: {type(block)}")
            return False
        return True

    def _dispatch_block_formatter(
        self,
        block_type: str,
        block_content: dict,
        block: dict,
        depth: int,
        page_breadcrumbs: List[Breadcrumb],
    ) -> Tuple[str, List[NotionFileEntity]]:
        """Dispatch to appropriate block formatter based on type."""
        if block_type == "paragraph":
            return self._extract_rich_text_markdown(block_content.get("rich_text", [])), []
        if block_type in ["heading_1", "heading_2", "heading_3"]:
            return self._format_heading_block(block_content, block_type), []
        if block_type in ["bulleted_list_item", "numbered_list_item", "to_do"]:
            return self._format_list_blocks(block_content, block_type, depth), []
        if block_type in ["quote", "callout", "code"]:
            return self._format_text_blocks(block_content, block_type), []
        if block_type in ["image", "video", "file", "pdf"]:
            return self._format_file_block(block_content, block, block_type)
        if block_type in ["embed", "bookmark", "equation", "divider"]:
            return self._format_simple_blocks(block_content, block_type), []
        if block_type in ["child_page", "child_database"]:
            return (
                self._format_child_blocks(block_content, block, block_type, page_breadcrumbs),
                [],
            )
        return self._format_other_blocks(block_content, block_type), []

    def _format_heading_block(self, block_content: dict, block_type: str) -> str:
        """Format heading blocks."""
        level = int(block_type.split("_")[1])
        text = self._extract_rich_text_markdown(block_content.get("rich_text", []))
        prefix = "▸ " if block_content.get("is_toggleable", False) else ""
        return f"{'#' * level} {prefix}{text}"

    def _format_list_blocks(self, block_content: dict, block_type: str, depth: int) -> str:
        """Format list and todo blocks."""
        text = self._extract_rich_text_markdown(block_content.get("rich_text", []))
        indent = "  " * depth

        if block_type == "bulleted_list_item":
            return f"{indent}- {text}"
        elif block_type == "numbered_list_item":
            return f"{indent}1. {text}"
        else:  # to_do
            checkbox = "- [x]" if block_content.get("checked", False) else "- [ ]"
            return f"{indent}{checkbox} {text}"

    def _format_text_blocks(self, block_content: dict, block_type: str) -> str:
        """Format quote, callout, and code blocks."""
        if block_type == "quote":
            text = self._extract_rich_text_markdown(block_content.get("rich_text", []))
            return f"> {text}"
        elif block_type == "callout":
            return self._format_callout_block(block_content)
        else:  # code
            return self._format_code_block(block_content)

    def _format_simple_blocks(self, block_content: dict, block_type: str) -> str:
        """Format simple blocks like embed, bookmark, equation, divider."""
        if block_type in ["embed", "bookmark"]:
            url = block_content.get("url", "")
            caption = self._extract_rich_text_plain(block_content.get("caption", []))
            # For embeddable text, don't include the full URL if it's very long
            # Just indicate it's an embed/bookmark
            if len(url) > 200 or "?" in url and len(url.split("?", 1)[1]) > 100:
                content = f"[{block_type.title()}]"
            else:
                content = f"[{block_type.title()}]({url})"
            if caption:
                content += f" - {caption}"
            return content
        elif block_type == "equation":
            expression = block_content.get("expression", "")
            return f"$$\n{expression}\n$$"
        elif block_type == "divider":
            return "---"
        else:
            return "**Table of Contents**"  # table_of_contents

    def _format_child_blocks(
        self, block_content: dict, block: dict, block_type: str, page_breadcrumbs: List[Breadcrumb]
    ) -> str:
        """Format child page and database blocks."""
        if block_type == "child_page":
            title = block_content.get("title", "Untitled Page")
            return f"📄 **[{title}]** (Child Page)"
        else:  # child_database
            return self._format_child_database_block(block_content, block, page_breadcrumbs)

    def _format_other_blocks(self, block_content: dict, block_type: str) -> str:
        """Format other block types including table, column, etc."""
        if block_type in ["table", "column_list"]:
            return f"**[{block_type.replace('_', ' ').title()}]**"
        elif block_type in ["table_row", "column"]:
            return ""  # These are handled by their parents
        elif block_type == "unsupported":
            return "*[Unsupported block type]*"
        else:
            return self._format_unknown_block(block_content, block_type)

    def _format_callout_block(self, block_content: dict) -> str:
        """Format callout blocks."""
        icon = block_content.get("icon", {})
        icon_text = icon.get("emoji", "💡") if icon.get("type") == "emoji" else "💡"
        text = self._extract_rich_text_markdown(block_content.get("rich_text", []))
        return f"**{icon_text} {text}**"

    def _format_code_block(self, block_content: dict) -> str:
        """Format code blocks."""
        language = block_content.get("language", "")
        code_text = self._extract_rich_text_plain(block_content.get("rich_text", []))
        caption = self._extract_rich_text_plain(block_content.get("caption", []))
        content = f"```{language}\n{code_text}\n```"
        if caption:
            content += f"\n*{caption}*"
        return content

    def _format_file_block(
        self, block_content: dict, block: dict, block_type: str
    ) -> Tuple[str, List[NotionFileEntity]]:
        """Format file blocks and return content and file entities."""
        file_entity = self._create_file_entity_from_block(block_content, block["id"])
        files = [file_entity]
        caption = self._extract_rich_text_plain(block_content.get("caption", []))

        # For embedding text, use simplified representation without full URLs
        # The actual URL is preserved in the file entity
        if block_type == "image":
            # Just use the filename or a generic placeholder for images
            display_name = file_entity.name if file_entity.name != "Untitled File" else "Image"
            content = f"[Image: {display_name}]"
        else:
            # For other files, just show the filename
            content = f"[File: {file_entity.name}]"

        if caption:
            content += f" - {caption}"

        return content, files

    def _format_child_database_block(
        self, block_content: dict, block: dict, page_breadcrumbs: List[Breadcrumb]
    ) -> str:
        """Format child database blocks."""
        title = block_content.get("title", "Untitled Database")
        database_id = block["id"]

        # Queue this child database for processing with proper breadcrumbs
        self._child_databases_to_process.add(database_id)

        # Create breadcrumbs for the child database (parent page + current page)
        child_db_breadcrumbs = page_breadcrumbs.copy()
        self._child_database_breadcrumbs[database_id] = child_db_breadcrumbs

        self._stats["child_databases_found"] += 1
        breadcrumb_names = [b.name for b in child_db_breadcrumbs]
        self.logger.debug(
            f"Found child database: {title} ({database_id}) in page breadcrumbs: {breadcrumb_names}"
        )

        # Include a reference in the page content
        return f"🗃️ **[{title}]** (Child Database)"

    def _format_unknown_block(self, block_content: dict, block_type: str) -> str:
        """Format unknown block types."""
        if "rich_text" in block_content:
            return self._extract_rich_text_markdown(block_content.get("rich_text", []))
        else:
            return f"*[{block_type.replace('_', ' ').title()}]*"

    def _extract_rich_text_markdown(self, rich_text: List[dict]) -> str:
        """Extract rich text and convert to markdown formatting."""
        if not rich_text or not isinstance(rich_text, list):
            return ""

        result_parts = []
        for text_obj in rich_text:
            if not text_obj or not isinstance(text_obj, dict):
                continue

            text = text_obj.get("plain_text", "")
            if not text:
                continue

            annotations = text_obj.get("annotations") or {}
            href = text_obj.get("href")
            formatted_text = self._apply_markdown_annotations(text, annotations, href)
            result_parts.append(formatted_text)

        return "".join(result_parts)

    def _apply_markdown_annotations(self, text: str, annotations: dict, href: str = None) -> str:
        """Apply markdown formatting based on annotations."""
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        if annotations.get("strikethrough"):
            text = f"~~{text}~~"
        if annotations.get("underline"):
            text = f"<u>{text}</u>"
        if annotations.get("code"):
            text = f"`{text}`"
        if href:
            text = f"[{text}]({href})"
        return text

    def _extract_rich_text_plain(self, rich_text: List[dict]) -> str:
        """Extract plain text from rich text objects."""
        if not rich_text or not isinstance(rich_text, list):
            return ""

        text_parts = []
        for text_obj in rich_text:
            # Defensive check: ensure text_obj is valid
            if not text_obj or not isinstance(text_obj, dict):
                continue

            plain_text = text_obj.get("plain_text", "")
            if plain_text:
                text_parts.append(plain_text)

        return " ".join(text_parts)

    async def _extract_page_properties(
        self, page: dict, database_id: str, database_schema: dict
    ) -> List[NotionPropertyEntity]:
        """Extract database page properties as structured entities."""
        page_id = page["id"]
        page_properties = page.get("properties", {})
        schema_properties = database_schema.get("properties", {})

        property_entities = []

        for prop_name, prop_value in page_properties.items():
            if prop_name in schema_properties:
                schema_prop = schema_properties[prop_name]

                try:
                    property_entity = self._create_property_entity(
                        prop_name, prop_value, schema_prop, page_id, database_id
                    )
                    property_entities.append(property_entity)

                except Exception as e:
                    self.logger.warning(
                        f"Error processing property {prop_name} for page {page_id}: {str(e)}"
                    )
                    continue

        return property_entities

    # Entity Creation Methods
    def _create_database_entity(self, database: dict) -> NotionDatabaseEntity:
        """Create a database entity from API response."""
        database_id = database["id"]
        title = self._extract_rich_text_plain(database.get("title", []))
        description = self._extract_rich_text_plain(database.get("description", []))
        created_time = self._parse_datetime(database.get("created_time"))
        updated_time = self._parse_datetime(database.get("last_edited_time"))
        database_url = database.get("url", "")

        parent = database.get("parent", {})

        # Format database schema properties for better searchability
        formatted_schema = self._format_database_schema(database.get("properties", {}))

        # Generate human-readable schema text
        properties_text = self._generate_schema_text_for_database(formatted_schema)

        return NotionDatabaseEntity(
            # Base fields
            entity_id=database_id,
            breadcrumbs=[],
            name=title or "Untitled Database",
            created_at=created_time,
            updated_at=updated_time,
            # API fields
            database_id=database_id,
            title=title or "Untitled Database",
            created_time=created_time,
            updated_time=updated_time,
            description=description,
            properties=formatted_schema,  # Use formatted schema
            properties_text=properties_text,  # Add formatted text for embedding
            parent_id=parent.get("page_id", ""),
            parent_type=parent.get("type", "workspace"),
            icon=database.get("icon"),
            cover=database.get("cover"),
            archived=database.get("archived", False),
            is_inline=database.get("is_inline", False),
            url=database_url,
        )

    def _format_database_schema(self, properties: dict) -> Dict[str, Any]:
        """Format database schema properties for better searchability.

        Creates a simplified schema dict with property names and types,
        plus key metadata like select options.
        """
        formatted = {}

        for prop_name, prop_config in properties.items():
            prop_type = prop_config.get("type", "")

            # Store basic info
            prop_info = {"type": prop_type, "name": prop_config.get("name", prop_name)}

            # Add options for select/status/multi_select
            if prop_type in ["select", "status"]:
                options = prop_config.get(prop_type, {}).get("options", [])
                prop_info["options"] = [opt.get("name", "") for opt in options if opt.get("name")]
            elif prop_type == "multi_select":
                options = prop_config.get("multi_select", {}).get("options", [])
                prop_info["options"] = [opt.get("name", "") for opt in options if opt.get("name")]
            elif prop_type == "number":
                format_type = prop_config.get("number", {}).get("format", "number")
                prop_info["format"] = format_type  # e.g., "percent", "dollar", etc.

            formatted[prop_name] = prop_info

        return formatted

    def _generate_schema_text_for_database(self, schema: Dict[str, Any]) -> str:
        """Generate human-readable text from database schema for embedding.

        Creates a clean representation of the database structure.
        """
        if not schema:
            return ""

        text_parts = []

        for prop_name, prop_info in schema.items():
            if isinstance(prop_info, dict):
                prop_type = prop_info.get("type", "unknown")

                # Build property description
                desc_parts = [f"{prop_name} ({prop_type})"]

                # Add options if available
                if "options" in prop_info and prop_info["options"]:
                    options_str = ", ".join(prop_info["options"][:5])  # Limit to first 5
                    if len(prop_info["options"]) > 5:
                        options_str += f" +{len(prop_info['options']) - 5} more"
                    desc_parts.append(f"options: {options_str}")

                # Add format for numbers
                if "format" in prop_info:
                    desc_parts.append(f"format: {prop_info['format']}")

                text_parts.append(" ".join(desc_parts))

        return " | ".join(text_parts) if text_parts else ""

    def _create_property_entity(
        self, prop_name: str, prop_value: dict, schema_prop: dict, page_id: str, database_id: str
    ) -> NotionPropertyEntity:
        """Create a property entity from page property data."""
        prop_type = prop_value.get("type", "")
        formatted_value = self._format_property_value(prop_value, prop_type)
        schema_prop_id = schema_prop.get("id", prop_name)
        property_key = f"{page_id}_{schema_prop_id}"

        return NotionPropertyEntity(
            # Base fields
            entity_id=property_key,
            breadcrumbs=[],
            name=prop_name,
            created_at=None,  # Properties don't have timestamps
            updated_at=None,  # Properties don't have timestamps
            # API fields
            property_key=property_key,
            property_id=schema_prop_id,
            property_name=prop_name,
            property_type=prop_type,
            page_id=page_id,
            database_id=database_id,
            value=prop_value.get(prop_type),
            formatted_value=formatted_value,
        )

    def _create_file_entity_from_block(
        self, block_content: dict, parent_id: str
    ) -> NotionFileEntity:
        """Create a file entity from block content."""
        file_type_notion = block_content.get("type", "external")

        # Handle different file types according to Notion API
        if file_type_notion == "file":
            # Notion-hosted file (uploaded via UI)
            file_data = block_content.get("file", {})
            url = file_data.get("url", "")
            expiry_time = self._parse_datetime(file_data.get("expiry_time"))
            file_id = url  # Use URL as file_id for Notion-hosted files
            download_url = url
        elif file_type_notion == "file_upload":
            # File uploaded via API
            file_data = block_content.get("file_upload", {})
            file_id = file_data.get("id", "")
            # For file_upload, we need to construct the download URL
            download_url = f"https://api.notion.com/v1/files/{file_id}"
            url = download_url
            expiry_time = None
        else:  # external
            # External file with public URL
            file_data = block_content.get("external", {})
            url = file_data.get("url", "")
            file_id = url  # Use URL as file_id for external files
            download_url = url
            expiry_time = None

        # Extract filename and caption
        name = block_content.get("name", "")
        if not name and url:
            parsed_url = urlparse(url)
            name = parsed_url.path.split("/")[-1] if parsed_url.path else "Untitled File"

        caption = self._extract_rich_text_plain(block_content.get("caption", []))
        display_name = name or "Untitled File"

        # Determine MIME type based on file extension or block type
        mime_type = None
        if name:
            ext = name.lower().split(".")[-1] if "." in name else ""
            mime_type_map = {
                "pdf": "application/pdf",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "gif": "image/gif",
                "webp": "image/webp",
                "svg": "image/svg+xml",
                "tiff": "image/tiff",
                "tif": "image/tiff",
                "ico": "image/vnd.microsoft.icon",
                "heic": "image/heic",
                "mp4": "video/mp4",
                "mov": "video/quicktime",
                "avi": "video/x-msvideo",
                "mkv": "video/x-matroska",
                "wmv": "video/x-ms-wmv",
                "flv": "video/x-flv",
                "webm": "video/webm",
                "mpeg": "video/mpeg",
                "mp3": "audio/mpeg",
                "wav": "audio/wav",
                "aac": "audio/aac",
                "ogg": "audio/ogg",
                "wma": "audio/x-ms-wma",
                "m4a": "audio/mp4",
                "m4b": "audio/mp4",
                "mid": "audio/midi",
                "midi": "audio/midi",
                "txt": "text/plain",
                "json": "application/json",
            }
            mime_type = mime_type_map.get(ext)

        # Determine general file type from mime_type for FileEntity base class
        if mime_type:
            general_file_type = mime_type.split("/")[0]  # e.g., "image", "video", "audio"
        else:
            general_file_type = "file"

        return NotionFileEntity(
            # Base fields
            entity_id=f"file_{parent_id}_{hash(file_id)}",
            breadcrumbs=[],
            name=display_name,
            created_at=None,  # Notion files don't have timestamps in block content
            updated_at=None,  # Notion files don't have timestamps in block content
            # File fields
            url=download_url,
            size=0,  # Notion API doesn't provide size in block content
            file_type=general_file_type,
            mime_type=mime_type or "application/octet-stream",
            local_path=None,
            # API fields (Notion-specific)
            file_id=file_id,
            file_name=display_name,
            expiry_time=expiry_time,
            caption=caption,
            web_url_value=url,
        )

    # Utility Methods
    def _extract_page_title(self, page: dict) -> str:
        """Extract title from page object."""
        properties = page.get("properties", {})

        # Look for title property
        for _prop_name, prop_value in properties.items():
            if prop_value.get("type") == "title":
                title_content = prop_value.get("title", [])
                return self._extract_rich_text_plain(title_content)

        return "Untitled"

    def _format_property_value(self, prop_value: dict, prop_type: str) -> str:
        """Format property value for human readability."""
        if not prop_value or prop_type not in prop_value:
            return ""

        value = prop_value[prop_type]

        # Use a mapping approach to reduce complexity
        formatters = {
            "title": lambda v: self._extract_rich_text_plain(v),
            "rich_text": lambda v: self._extract_rich_text_plain(v),
            "number": lambda v: str(v) if v is not None else "",
            "url": lambda v: str(v) if v is not None else "",
            "email": lambda v: str(v) if v is not None else "",
            "phone_number": lambda v: str(v) if v is not None else "",
            "checkbox": lambda v: "Yes" if v else "No",
            "select": lambda v: self._format_select_properties(v),
            "status": lambda v: self._format_select_properties(v),
            "multi_select": lambda v: ", ".join([opt.get("name", "") for opt in v]) if v else "",
            "date": lambda v: self._format_date_property(v),
            "people": lambda v: self._format_people_property(v),
            "files": lambda v: f"{len(v)} file(s)" if v else "0 files",
            "created_time": lambda v: v or "",
            "last_edited_time": lambda v: v or "",
            "created_by": lambda v: v.get("name", "Unknown User") if v else "",
            "last_edited_by": lambda v: v.get("name", "Unknown User") if v else "",
        }

        # Check if we have a direct formatter
        if prop_type in formatters:
            return formatters[prop_type](value)

        # Handle complex properties that need special logic
        return self._format_complex_property_types(prop_type, value)

    def _format_complex_property_types(self, prop_type: str, value: Any) -> str:
        """Format complex property types that need special handling."""
        if prop_type == "relation":
            return f"{len(value)} relation(s)" if value else "0 relations"
        elif prop_type == "rollup":
            return self._format_rollup_property(value)
        elif prop_type == "formula":
            return self._format_formula_property(value)
        elif prop_type == "unique_id":
            return self._format_unique_id_property(value)
        elif prop_type == "verification":
            return self._format_verification_property(value)
        else:
            return str(value) if value else ""

    def _format_unique_id_property(self, value: dict) -> str:
        """Format unique_id property values."""
        prefix = value.get("prefix", "")
        number = value.get("number", "")
        return f"{prefix}{number}" if prefix else str(number)

    def _format_verification_property(self, value: dict) -> str:
        """Format verification property values."""
        state = value.get("state", "")
        return state.title() if state else ""

    def _format_select_properties(self, value: dict) -> str:
        """Format select and status properties."""
        return value.get("name", "") if value else ""

    def _format_date_property(self, value: dict) -> str:
        """Format date property values."""
        if value and value.get("start"):
            start = value["start"]
            end = value.get("end")
            return f"{start} - {end}" if end else start
        return ""

    def _format_people_property(self, value: List[dict]) -> str:
        """Format people property values."""
        names = []
        for person in value:
            if person.get("type") == "person":
                names.append(person.get("name", "Unknown"))
            elif person.get("type") == "bot":
                names.append(person.get("name", "Bot"))
        return ", ".join(names)

    def _format_formula_property(self, value: dict) -> str:
        """Format formula property values."""
        formula_type = value.get("type", "")
        if formula_type in ["string", "number", "boolean", "date"]:
            return str(value.get(formula_type, ""))
        return ""

    def _format_rollup_property(self, value: dict) -> str:
        """Format rollup property values."""
        rollup_type = value.get("type", "")
        if rollup_type in ["string", "number", "boolean", "date"]:
            return str(value.get(rollup_type, ""))
        elif rollup_type == "array":
            return f"{len(value.get('array', []))} item(s)"
        return ""

    def _create_formatted_properties_dict(
        self, page_properties: dict, database_schema: dict
    ) -> Dict[str, Any]:
        """Create a clean, formatted properties dictionary for better searchability.

        Instead of storing raw Notion API responses, create a simplified dict with:
        - Property names as keys
        - Formatted human-readable values
        - Essential metadata only (type, options for selects)
        """
        formatted = {}

        for prop_name, prop_value in page_properties.items():
            if not prop_value:
                continue

            prop_type = prop_value.get("type", "")

            # Get the formatted value using existing formatting methods
            formatted_value = self._format_property_value(prop_value, prop_type)

            # Skip empty values
            if not formatted_value:
                continue

            # Store clean formatted value
            formatted[prop_name] = formatted_value

            # For select/status properties, also store the options from schema for searchability
            if prop_type in ["select", "status", "multi_select"] and prop_name in database_schema:
                schema_prop = database_schema[prop_name]
                if prop_type == "multi_select":
                    options = schema_prop.get("multi_select", {}).get("options", [])
                else:
                    options = schema_prop.get(prop_type, {}).get("options", [])

                if options:
                    # Store available options as metadata
                    formatted[f"{prop_name}_options"] = [
                        opt.get("name", "") for opt in options if opt.get("name")
                    ]

        return formatted

    def _generate_properties_text_for_page(
        self, properties: Dict[str, Any], page_title: str
    ) -> str:
        """Generate human-readable text from properties for embedding.

        Creates a clean, searchable representation of property values.
        """
        if not properties:
            return ""

        text_parts = []

        # Process properties in a logical order
        priority_keys = [
            "Product Name",
            "Name",
            "Title",
            "Status",
            "Priority",
            "Launch Status",
            "Owner",
            "Team",
            "Description",
        ]

        # First add priority properties
        for key in priority_keys:
            if key in properties:
                value = properties[key]
                if value and str(value).strip():
                    # Skip if it's the same as the page title
                    if key in ["Product Name", "Name", "Title"] and value == page_title:
                        continue
                    text_parts.append(f"{key}: {value}")

        # Then add remaining properties
        for key, value in properties.items():
            if key not in priority_keys and not key.endswith("_options"):
                if value and str(value).strip():
                    # Format the key nicely
                    formatted_key = key.replace("_", " ").title()
                    text_parts.append(f"{formatted_key}: {value}")

        return " | ".join(text_parts) if text_parts else ""

    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object.

        Returns a timezone-naive datetime in UTC for consistency with the rest of the system.
        """
        if not datetime_str:
            return None

        try:
            # Handle ISO format with timezone
            if datetime_str.endswith("Z"):
                datetime_str = datetime_str[:-1] + "+00:00"

            # Parse the datetime (will be timezone-aware)
            dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))

            # Convert to UTC if it has timezone info, then make it naive
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)

            return dt
        except (ValueError, AttributeError):
            self.logger.warning(f"Could not parse datetime: {datetime_str}")
            return None

    # Main Entry Point
    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Notion using streaming discovery."""
        self.logger.debug("=" * 80)
        self.logger.debug("🚀 Starting Notion entity generation with content aggregation")
        self.logger.debug("=" * 80)

        self._stats = {
            "api_calls": 0,
            "rate_limit_waits": 0,
            "databases_found": 0,
            "child_databases_found": 0,
            "pages_found": 0,
            "total_blocks_processed": 0,
            "total_files_found": 0,
            "max_page_depth": 0,
        }

        try:
            async with self.http_client() as client:
                # Phase 1 & 2: Discover and yield databases with their schemas
                self.logger.debug("=" * 80)
                self.logger.debug(
                    "📊 PHASE 1 & 2: Streaming database discovery and schema analysis"
                )
                self.logger.debug("=" * 80)
                async for entity in self._stream_database_discovery(client):
                    yield entity
                self.logger.debug(
                    f"✅ Phase 1 & 2 complete: {self._stats['databases_found']} databases found"
                )

                # Phase 3: Discover and yield standalone pages
                self.logger.debug("=" * 80)
                self.logger.debug("📄 PHASE 3: Streaming standalone page discovery")
                self.logger.debug("=" * 80)
                async for entity in self._stream_page_discovery(client):
                    yield entity
                self.logger.debug(
                    f"✅ Phase 3 complete: {self._stats['pages_found']} standalone pages found"
                )

                # Phase 4: Process any remaining child databases found during page processing
                self.logger.debug("=" * 80)
                self.logger.debug("🗃️  PHASE 4: Processing child databases")
                self.logger.debug("=" * 80)
                async for entity in self._process_child_databases(client):
                    yield entity
                self.logger.debug(
                    f"✅ Phase 4 complete: "
                    f"{self._stats['child_databases_found']} child databases found"
                )

            self.logger.debug("=" * 80)
            self.logger.debug("✅ Notion sync complete. Final stats:")
            for key, value in self._stats.items():
                self.logger.debug(f"   {key}: {value}")
            self.logger.debug("=" * 80)

        except Exception as e:
            self.logger.error(
                f"Error during streaming Notion entity generation: {str(e)}", exc_info=True
            )
            raise

    async def _stream_database_discovery(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Discover databases and delegate per-database processing to a helper.

        Keeping this wrapper minimal satisfies complexity limits while preserving logic.
        """
        self.logger.debug("Streaming database discovery...")

        async for database in self._search_objects(client, "database"):
            database_id = database["id"]
            if database_id in self._processed_databases:
                continue
            self._stats["databases_found"] += 1
            async for entity in self._process_single_database(client, database_id):
                yield entity

    async def _process_single_database(
        self, client: httpx.AsyncClient, database_id: str
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process one database: fetch schema, emit DB entity, pages, files, child DBs."""
        try:
            self.logger.debug(f"Fetching schema for database: {database_id}")
            schema = await self._get_with_auth(
                client, f"https://api.notion.com/v1/databases/{database_id}"
            )
            self._processed_databases.add(database_id)

            database_entity = self._create_database_entity(schema)
            yield database_entity

            database_title = self._extract_rich_text_plain(schema.get("title", []))
            self.logger.debug(f"Processing pages in database: {database_title}")

            async for page in self._query_database_pages(client, database_id):
                page_id = page["id"]
                if page_id in self._processed_pages:
                    continue
                try:
                    breadcrumbs = [
                        Breadcrumb(
                            entity_id=database_id,
                            name=database_title or "Untitled Database",
                            entity_type=NotionDatabaseEntity.__name__,
                        )
                    ]
                    page_entity, files = await self._create_comprehensive_page_entity(
                        client, page, breadcrumbs, database_id, schema
                    )
                    yield page_entity
                    for file_entity in files:
                        processed = await self._process_and_yield_file(file_entity)
                        if processed:
                            yield processed
                    self._processed_pages.add(page_id)
                    async for child_entity in self._process_child_databases(client):
                        yield child_entity
                except NotionSource.NotionAccessError as e:
                    self.logger.warning(
                        f"Access issue processing database page {page_id}: {str(e)}"
                    )
                    continue
                except Exception as e:
                    self.logger.error(f"Error processing database page {page_id}: {str(e)}")
                    continue
        except NotionSource.NotionAccessError as e:
            self.logger.warning(f"Access issue processing database {database_id}: {str(e)}")
            return
        except Exception as e:
            self.logger.error(f"Error processing database {database_id}: {str(e)}")
            return

    async def _stream_page_discovery(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[BaseEntity, None]:
        """Stream page discovery and immediately yield page entities."""
        self.logger.debug("Streaming page discovery...")

        # Search for pages and process them one by one
        async for page in self._search_objects(client, "page"):
            page_id = page["id"]
            if page_id in self._processed_pages:
                continue

            parent = page.get("parent", {})
            parent_type = parent.get("type", "")

            # Skip database pages (already processed during database discovery)
            if parent_type == "database_id":
                continue

            self._stats["pages_found"] += 1

            try:
                # Get full page details
                full_page = await self._get_with_auth(
                    client, f"https://api.notion.com/v1/pages/{page_id}"
                )

                # Build breadcrumbs for standalone pages
                breadcrumbs = await self._build_page_breadcrumbs(client, full_page)

                # Eagerly build full page entity and files
                page_entity, files = await self._create_comprehensive_page_entity(
                    client, full_page, breadcrumbs
                )
                yield page_entity

                for file_entity in files:
                    processed = await self._process_and_yield_file(file_entity)
                    if processed:
                        yield processed

                self._processed_pages.add(page_id)

                # Process any child databases discovered within this page immediately
                async for child_entity in self._process_child_databases(client):
                    yield child_entity

            except NotionSource.NotionAccessError as e:
                self.logger.warning(f"Access issue processing standalone page {page_id}: {str(e)}")
                continue
            except Exception as e:
                self.logger.error(f"Error processing standalone page {page_id}: {str(e)}")
                continue

    async def _process_and_yield_file(
        self, file_entity: NotionFileEntity
    ) -> Optional[NotionFileEntity]:
        """Process a file entity by downloading it and setting local_path."""
        try:
            # Skip files that need refresh (expired URLs)
            if file_entity.needs_refresh():
                self.logger.warning(f"Skipping file {file_entity.name} - URL expired")
                return None

            # Skip external files (can't be downloaded)
            # Check the general file_type field (not the Notion-specific one)
            if not file_entity.url or file_entity.url.startswith("http") is False:
                self.logger.debug(f"Skipping file {file_entity.name} - no valid download URL")
                return None

            # Download the file using file downloader
            try:
                await self.file_downloader.download_from_url(
                    entity=file_entity,
                    http_client_factory=self.http_client,
                    access_token_provider=self.get_access_token,
                    logger=self.logger,
                )

                # Verify download succeeded
                if not file_entity.local_path:
                    raise ValueError(f"Download failed - no local path set for {file_entity.name}")

                self.logger.debug(
                    f"Successfully downloaded file {file_entity.name} "
                    f"to local_path: {file_entity.local_path}"
                )
                return file_entity

            except FileSkippedException as e:
                # File intentionally skipped (unsupported type, too large, etc.) - not an error
                self.logger.debug(f"Skipping file {file_entity.name}: {e.reason}")
                return None

            except Exception as e:
                self.logger.error(f"Failed to download file {file_entity.name}: {e}")
                return None

        except NotionSource.NotionAccessError as e:
            self.logger.warning(f"Access issue processing file {file_entity.name}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error processing file {file_entity.name}: {str(e)}")
            return None

    # Removed lazy page entity creation and related helpers to simplify to eager-only generation
