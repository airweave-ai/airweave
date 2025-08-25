"""Notion connector for syncing content from Notion workspaces to Airweave.

This module provides a comprehensive source implementation for extracting databases and pages
with full aggregated content from Notion, handling API rate limits, and converting API
responses to entity objects.
"""

import asyncio
from datetime import datetime
from typing import Any, AsyncGenerator, ClassVar, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

import httpx
from httpx import HTTPStatusError, ReadTimeout, TimeoutException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.notion import (
    NotionDatabaseEntity,
    NotionFileEntity,
    NotionPageEntity,
    NotionPropertyEntity,
)
from airweave.platform.file_handling.file_manager import file_manager
from airweave.platform.sources._base import BaseSource


@source(
    name="Notion",
    short_name="notion",
    auth_type=AuthType.oauth2,
    auth_config_class="NotionAuthConfig",
    config_class="NotionConfig",
    labels=["Knowledge Base", "Productivity"],
)
class NotionSource(BaseSource):
    """Notion source connector integrates with the Notion API to extract and synchronize content.

    Connects to your Notion workspace.

    It provides comprehensive access to databases, pages, and content with advanced content
    aggregation, lazy loading, and file processing capabilities for optimal performance.

    Concurrency knobs:
      - `batch_generation` (bool): when True, cap concurrent page materializations using
        `batch_size`. When False, behavior matches the original implementation (no source-level
        concurrency gate for materialization).
      - `batch_size` (int): max concurrent page materializations when `batch_generation=True`.
      - `_shared_wait_for_rate_limit`: caps request rate (RPS) against Notion API globally.
    """

    # Rate limiting constants
    TIMEOUT_SECONDS = 60.0  # Increased from 30.0
    RATE_LIMIT_REQUESTS = 2  # Reduced from 3 to be more conservative
    RATE_LIMIT_PERIOD = 1.0  # Time period in seconds
    MAX_RETRIES = 5  # Increased from 3

    # Class-level shared rate limiter
    _shared_rate_limiter: ClassVar[Optional[asyncio.Semaphore]] = None
    _shared_request_times: ClassVar[List[float]] = []
    _shared_lock: ClassVar[asyncio.Lock] = asyncio.Lock()

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
        logger.info("Initialized comprehensive Notion source with content aggregation")
        self._client_ref = None

        # NEW: per-instance controls (defaults preserve original behavior)
        self.batch_generation: bool = True  # off = original flow (no source-level gate)
        self.batch_size: int = 6  # used only when batch_generation=True
        self._materialize_semaphore: asyncio.Semaphore = asyncio.Semaphore(self.batch_size)

    @classmethod
    async def create(cls, credentials, config: Optional[Dict[str, Any]] = None) -> "NotionSource":
        """Create a new Notion source.

        Config options:
          - batch_generation (bool): enable/disable source-level gating of page materialization.
            False = original behavior. True = use batch_size.
          - batch_size (int): max concurrent page materializations when batch_generation=True.
        """
        logger.info("Creating new Notion source")
        instance = cls()
        instance.access_token = credentials.access_token

        # Drive-like knobs for symmetry (while keeping original default behavior)
        config = config or {}
        try:
            instance.batch_generation = bool(
                config.get("batch_generation", instance.batch_generation)
            )
        except Exception:
            instance.batch_generation = False
        try:
            instance.batch_size = int(config.get("batch_size", instance.batch_size))
        except Exception:
            instance.batch_size = 6

        # Rebuild semaphore in case batch_size changed
        instance._materialize_semaphore = asyncio.Semaphore(instance.batch_size)

        return instance

    @classmethod
    async def _get_shared_rate_limiter(cls):
        """Get or create the shared rate limiter for all Notion instances."""
        if cls._shared_rate_limiter is None:
            cls._shared_rate_limiter = asyncio.Semaphore(cls.RATE_LIMIT_REQUESTS)
        return cls._shared_rate_limiter

    @classmethod
    async def _shared_wait_for_rate_limit(cls):
        """Shared rate limiting across all Notion instances."""
        async with cls._shared_lock:
            current_time = asyncio.get_event_loop().time()

            # Remove old request times
            cls._shared_request_times = [
                t for t in cls._shared_request_times if current_time - t < cls.RATE_LIMIT_PERIOD
            ]

            if len(cls._shared_request_times) >= cls.RATE_LIMIT_REQUESTS:
                sleep_time = cls._shared_request_times[0] + cls.RATE_LIMIT_PERIOD - current_time
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

                # Clean up again after waiting
                current_time = asyncio.get_event_loop().time()
                cls._shared_request_times = [
                    t for t in cls._shared_request_times if current_time - t < cls.RATE_LIMIT_PERIOD
                ]

            cls._shared_request_times.append(current_time)

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
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=10, max=60),
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
            self.logger.debug(f"GET response from {url}: status={response.status_code}")

            if response.status_code != 200:
                self.logger.warning(
                    f"Non-200 response from Notion API: {response.status_code} for {url}"
                )
                self.logger.debug(f"Response body: {response.text[:200]}...")

            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"Error during GET request to {url}: {str(e)}")
            raise

    @retry(
        retry=retry_if_exception_type((TimeoutException, ReadTimeout, HTTPStatusError)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=10, max=60),
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
        except Exception as e:
            self.logger.error(f"Error during POST request to {url}: {str(e)}")
            raise

    async def _search_objects(
        self, client: httpx.AsyncClient, object_type: str
    ) -> AsyncGenerator[dict, None]:
        """Search for objects of a specific type."""
        url = "https://api.notion.com/v1/search"
        has_more = True
        start_cursor = None

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

                for obj in results:
                    yield obj

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            except Exception as e:
                self.logger.error(f"Error searching for {object_type}: {str(e)}")
                raise

    async def _query_database_pages(
        self, client: httpx.AsyncClient, database_id: str
    ) -> AsyncGenerator[dict, None]:
        """Query all pages in a database."""
        url = f"https://api.notion.com/v1/databases/{database_id}/query"
        has_more = True
        start_cursor = None

        while has_more:
            json_data = {"page_size": 100}
            if start_cursor:
                json_data["start_cursor"] = start_cursor

            try:
                response = await self._post_with_auth(client, url, json_data)
                results = response.get("results", [])

                for page in results:
                    yield page

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            except Exception as e:
                self.logger.error(f"Error querying database {database_id}: {str(e)}")
                raise

    # Child Database Processing
    async def _process_child_databases(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process child databases discovered during page content extraction."""
        self.logger.info("Processing child databases")

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

            self.logger.info(f"Processing {len(unprocessed_databases)} child databases")

            for database_id in unprocessed_databases:
                try:
                    self.logger.info(f"Processing child database: {database_id}")

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
                            page_breadcrumbs = breadcrumbs + [
                                Breadcrumb(
                                    entity_id=database_id,
                                    name=database_entity.title,
                                    type="database",
                                )
                            ]

                            # Always use lazy loading for better performance
                            page_entity = await self._create_lazy_page_entity(
                                page, page_breadcrumbs, database_id, schema
                            )
                            yield page_entity

                            # Don't yield files separately - they'll be handled
                            # during materialization
                            self._processed_pages.add(page_id)

                        except Exception as e:
                            self.logger.error(
                                f"Error processing child database page {page_id}: {str(e)}"
                            )
                            continue

                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        self.logger.warning(
                            f"Child database {database_id} not found (404). "
                            f"This is expected if the user doesn't have access to this database. "
                            f"Skipping."
                        )
                        self._processed_databases.add(
                            database_id
                        )  # Mark as processed to avoid retrying
                        continue
                    else:
                        self.logger.error(
                            f"HTTP error processing child database {database_id}: {str(e)}"
                        )
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
                    parent_title = self._extract_page_title(parent_page)
                    breadcrumbs.insert(
                        0, Breadcrumb(entity_id=parent_id, name=parent_title, type="page")
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

        self.logger.info(f"Creating comprehensive page entity: {title} ({page_id})")

        # Reset child database tracking for this page
        self._child_databases_to_process.clear()

        # Aggregate all content from blocks
        content_result = await self._aggregate_page_content(client, page_id, breadcrumbs)

        # Extract properties if this is a database page
        property_entities = []
        if database_id and database_schema:
            property_entities = await self._extract_page_properties(
                page, database_id, database_schema
            )

        # Create the comprehensive page entity
        parent = page.get("parent", {})

        page_entity = NotionPageEntity(
            entity_id=page_id,
            breadcrumbs=breadcrumbs,
            page_id=page_id,
            parent_id=parent.get("page_id") or parent.get("database_id") or "",
            parent_type=parent.get("type", "workspace"),
            title=title,
            content=content_result["content"],
            properties=page.get("properties", {}),
            property_entities=property_entities,
            files=[],  # Don't include files in page entity - they'll be yielded separately
            icon=page.get("icon"),
            cover=page.get("cover"),
            archived=page.get("archived", False),
            in_trash=page.get("in_trash", False),
            url=page.get("url", ""),
            content_blocks_count=content_result["blocks_count"],
            max_depth=content_result["max_depth"],
            created_time=self._parse_datetime(page.get("created_time")),
            last_edited_time=self._parse_datetime(page.get("last_edited_time")),
        )

        # Set breadcrumbs on file entities
        files_with_breadcrumbs = []
        for file_entity in content_result["files"]:
            file_entity.breadcrumbs = breadcrumbs.copy()
            files_with_breadcrumbs.append(file_entity)

        self.logger.info(
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

        return {
            "content": full_content,
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
            url_with_params = url
            if start_cursor:
                url_with_params = f"{url}?start_cursor={start_cursor}"

            try:
                response = await self._get_with_auth(client, url_with_params)
                blocks = response.get("results", [])

                for block in blocks:
                    # Format this block
                    block_result = await self._format_block_content(block, depth, page_breadcrumbs)

                    if block_result["content"]:
                        yield block_result

                    # Process children recursively if they exist
                    if block.get("has_children", False):
                        async for child_result in self._extract_blocks_recursive(
                            client, block["id"], depth + 1, page_breadcrumbs
                        ):
                            yield child_result

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            except Exception as e:
                self.logger.error(f"Error extracting blocks from {block_id}: {str(e)}")
                raise

    async def _format_block_content(
        self, block: dict, depth: int, page_breadcrumbs: List[Breadcrumb]
    ) -> Dict[str, Any]:
        """Format a single block into markdown content."""
        block_type = block.get("type", "")
        block_content = block.get(block_type, {})

        # Delegate to specific formatters based on block type
        if block_type == "paragraph":
            content = self._extract_rich_text_markdown(block_content.get("rich_text", []))
            files = []
        elif block_type in ["heading_1", "heading_2", "heading_3"]:
            content = self._format_heading_block(block_content, block_type)
            files = []
        elif block_type in ["bulleted_list_item", "numbered_list_item", "to_do"]:
            content = self._format_list_blocks(block_content, block_type, depth)
            files = []
        elif block_type in ["quote", "callout", "code"]:
            content = self._format_text_blocks(block_content, block_type)
            files = []
        elif block_type in ["image", "video", "file", "pdf"]:
            content, files = self._format_file_block(block_content, block_type)
        elif block_type in ["embed", "bookmark", "equation", "divider"]:
            content = self._format_simple_blocks(block_content, block_type)
            files = []
        elif block_type in ["child_page", "child_database"]:
            content = self._format_child_blocks(block_content, block_type, page_breadcrumbs)
            files = []
        else:
            content = self._format_other_blocks(block_content, block_type)
            files = []

        return {"content": content, "files": files, "depth": depth}

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
            content = f"[{block_type.title()}]({url})"
            if caption:
                content += f"\n*{caption}*"
            return content
        elif block_type == "equation":
            expression = block_content.get("expression", "")
            return f"$$\n{expression}\n$$"
        elif block_type == "divider":
            return "---"
        else:
            return "**Table of Contents**"  # table_of_contents

    def _format_child_blocks(
        self, block_content: dict, block_type: str, page_breadcrumbs: List[Breadcrumb]
    ) -> str:
        """Format child page and database blocks."""
        if block_type == "child_page":
            title = block_content.get("title", "Untitled Page")
            return f"📄 **[{title}]** (Child Page)"
        else:  # child_database
            return self._format_child_database_block(block_content, page_breadcrumbs)

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
        self, block_content: dict, block_type: str
    ) -> Tuple[str, List[NotionFileEntity]]:
        """Format file blocks and return content and file entities."""
        file_entity = self._create_file_entity_from_block(block_content, block_type)
        files = [file_entity]
        caption = self._extract_rich_text_plain(block_content.get("caption", []))

        if block_type == "image":
            content = f"![{file_entity.name}]({file_entity.url})"
        else:
            content = f"[{file_entity.name}]({file_entity.url})"

        if caption:
            content += f"\n*{caption}*"

        return content, files

    def _format_child_database_block(
        self, block_content: dict, page_breadcrumbs: List[Breadcrumb]
    ) -> str:
        """Format child database blocks."""
        title = block_content.get("title", "Untitled Database")
        database_id = block_content.get("id") or ""  # Notion uses block id for child_database

        # Queue this child database for processing with proper breadcrumbs
        if database_id:
            self._child_databases_to_process.add(database_id)
            self._child_database_breadcrumbs[database_id] = page_breadcrumbs.copy()

        self._stats["child_databases_found"] += 1
        breadcrumb_names = [b.name for b in page_breadcrumbs]
        self.logger.info(
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
        if not rich_text:
            return ""

        result_parts = []
        for text_obj in rich_text:
            text = text_obj.get("plain_text", "")
            if not text:
                continue

            annotations = text_obj.get("annotations", {})
            href = text_obj.get("href")

            # Apply formatting
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

            # Handle links
            if href:
                text = f"[{text}]({href})"

            result_parts.append(text)

        return "".join(result_parts)

    def _extract_rich_text_plain(self, rich_text: List[dict]) -> str:
        """Extract plain text from rich text objects."""
        if not rich_text:
            return ""

        text_parts = []
        for text_obj in rich_text:
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

        parent = database.get("parent", {})

        return NotionDatabaseEntity(
            entity_id=database_id,
            breadcrumbs=[],
            database_id=database_id,
            title=title or "Untitled Database",
            description=description,
            properties=database.get("properties", {}),
            parent_id=parent.get("page_id", ""),
            parent_type=parent.get("type", "workspace"),
            icon=database.get("icon"),
            cover=database.get("cover"),
            archived=database.get("archived", False),
            is_inline=database.get("is_inline", False),
            url=database.get("url", ""),
            created_time=self._parse_datetime(database.get("created_time")),
            last_edited_time=self._parse_datetime(database.get("last_edited_time")),
        )

    def _create_property_entity(
        self, prop_name: str, prop_value: dict, schema_prop: dict, page_id: str, database_id: str
    ) -> NotionPropertyEntity:
        """Create a property entity from page property data."""
        prop_type = prop_value.get("type", "")
        formatted_value = self._format_property_value(prop_value, prop_type)

        return NotionPropertyEntity(
            entity_id=f"{page_id}_{schema_prop.get('id', prop_name)}",
            breadcrumbs=[],
            property_id=schema_prop.get("id", ""),
            property_name=prop_name,
            property_type=prop_type,
            page_id=page_id,
            database_id=database_id,
            value=prop_value.get(prop_type),
            formatted_value=formatted_value,
        )

    def _create_file_entity_from_block(
        self, block_content: dict, parent_type_or_id: str
    ) -> NotionFileEntity:
        """Create a file entity from block content."""
        file_type = block_content.get("type", "external")

        # Handle different file types according to Notion API
        if file_type == "file":
            # Notion-hosted file (uploaded via UI)
            file_data = block_content.get("file", {})
            url = file_data.get("url", "")
            expiry_time = self._parse_datetime(file_data.get("expiry_time"))
            file_id = url  # Use URL as file_id for Notion-hosted files
            download_url = url
        elif file_type == "file_upload":
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

        return NotionFileEntity(
            entity_id=f"file_{hash((file_type, file_id))}",
            breadcrumbs=[],
            file_id=file_id,
            name=name or "Untitled File",
            mime_type=mime_type,
            size=None,  # Notion API doesn't provide size in block content
            download_url=download_url,
            should_skip=False,
            file_type=file_type,
            url=url,
            expiry_time=expiry_time,
            caption=caption,
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

    def _parse_datetime(self, datetime_str: Optional[str]) -> Optional[datetime]:
        """Parse datetime string to datetime object."""
        if not datetime_str:
            return None

        try:
            # Handle ISO format with timezone
            if datetime_str.endswith("Z"):
                datetime_str = datetime_str[:-1] + "+00:00"
            return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            self.logger.warning(f"Could not parse datetime: {datetime_str}")
            return None

    # Main Entry Point
    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all entities from Notion using streaming discovery."""
        self.logger.info("Starting streaming Notion entity generation with content aggregation")
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
            async with httpx.AsyncClient() as client:
                self._client_ref = client  # Store for lazy operations

                # Phase 1 & 2: Databases + schema
                self.logger.info("Phase 1 & 2: Streaming database discovery and schema analysis")
                async for entity in self._stream_database_discovery(client):
                    yield entity

                # Phase 3: Standalone pages
                self.logger.info("Phase 3: Streaming standalone page discovery")
                async for entity in self._stream_page_discovery(client):
                    yield entity

                # Phase 4: Child databases encountered during page processing
                self.logger.info("Phase 4: Processing child databases")
                async for entity in self._process_child_databases(client):
                    yield entity

            self.logger.info(f"Notion sync complete. Final stats: {self._stats}")

        except Exception as e:
            self.logger.error(
                f"Error during streaming Notion entity generation: {str(e)}", exc_info=True
            )
            raise

    async def _stream_database_discovery(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Stream database discovery and immediately yield database entities with their pages."""
        self.logger.info("Streaming database discovery...")

        # Search for databases and process them one by one
        async for database in self._search_objects(client, "database"):
            database_id = database["id"]
            if database_id in self._processed_databases:
                continue

            self._stats["databases_found"] += 1

            try:
                # Get the database schema
                self.logger.info(f"Fetching schema for database: {database_id}")
                schema = await self._get_with_auth(
                    client, f"https://api.notion.com/v1/databases/{database_id}"
                )
                self._processed_databases.add(database_id)

                # Yield the database entity immediately
                database_entity = self._create_database_entity(schema)
                yield database_entity

                database_title = self._extract_rich_text_plain(schema.get("title", []))
                self.logger.info(f"Processing pages in database: {database_title}")

                # Query and yield pages in this database
                async for page in self._query_database_pages(client, database_id):
                    page_id = page["id"]
                    if page_id in self._processed_pages:
                        continue

                    try:
                        # Create breadcrumbs for database pages
                        breadcrumbs = [
                            Breadcrumb(
                                entity_id=database_id, name=database_entity.title, type="database"
                            )
                        ]

                        # Always use lazy loading for better performance
                        page_entity = await self._create_lazy_page_entity(
                            page, breadcrumbs, database_id, schema
                        )
                        yield page_entity

                        self._processed_pages.add(page_id)

                    except Exception as e:
                        self.logger.error(f"Error processing database page {page_id}: {str(e)}")
                        continue

            except Exception as e:
                self.logger.error(f"Error processing database {database_id}: {str(e)}")
                continue

    async def _stream_page_discovery(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Stream page discovery and immediately yield page entities."""
        self.logger.info("Streaming page discovery...")

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

                # Always use lazy loading for better performance
                page_entity = await self._create_lazy_page_entity(full_page, breadcrumbs)
                yield page_entity

                self._processed_pages.add(page_id)

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
            if file_entity.file_type == "external":
                self.logger.info(f"Skipping external file {file_entity.name} - external URL")
                return None

            # Download the file using BaseSource.process_file_entity
            if file_entity.file_type == "file_upload":
                # For file_upload type, we need special headers and access token
                headers = {"Notion-Version": "2022-06-28"}
                processed_entity = await self.process_file_entity(
                    file_entity=file_entity, access_token=self.access_token, headers=headers
                )
            else:  # file_type == "file"
                # For Notion-hosted files, use the temporary URL directly
                # Pre-signed URLs don't need authentication
                try:
                    processed_entity = await self.process_file_entity(
                        file_entity=file_entity, access_token=self.access_token
                    )
                except Exception:
                    self.logger.info(
                        f"Falling back to pre-signed URL processing for {file_entity.name}"
                    )
                    processed_entity = await self._process_presigned_file(file_entity)

            if processed_entity and not processed_entity.airweave_system_metadata.should_skip:
                self.logger.info(
                    f"Successfully processed file {processed_entity.name} "
                    f"with local_path: {processed_entity.airweave_system_metadata.local_path}"
                )
                return processed_entity
            else:
                self.logger.warning(f"File {file_entity.name} was skipped during processing")
                return None

        except Exception as e:
            self.logger.error(f"Error processing file {file_entity.name}: {str(e)}")
            return None

    async def _process_presigned_file(
        self, file_entity: NotionFileEntity
    ) -> Optional[NotionFileEntity]:
        """Process a file with a pre-signed URL that doesn't need authentication."""
        self.logger.info(f"Processing pre-signed file entity: {file_entity.name}")

        try:
            # Create stream without access token for pre-signed URLs
            file_stream = file_manager.stream_file_from_url(
                file_entity.download_url, access_token=None, headers=None, logger=self.logger
            )

            # Process entity directly with the file manager
            processed_entity = await file_manager.handle_file_entity(
                stream=file_stream, entity=file_entity, logger=self.logger
            )

            # Skip if file was too large
            if processed_entity.airweave_system_metadata.should_skip:
                error_msg = "Unknown reason"
                if processed_entity.metadata:
                    error_msg = processed_entity.metadata.get("error", "Unknown reason")
                self.logger.warning(f"Skipping file {processed_entity.name}: {error_msg}")

            return processed_entity
        except Exception as e:
            self.logger.error(f"Error processing pre-signed file {file_entity.name}: {e}")
            return None

    async def _create_lazy_page_entity(
        self,
        page: dict,
        breadcrumbs: List[Breadcrumb],
        database_id: Optional[str] = None,
        database_schema: Optional[dict] = None,
    ) -> NotionPageEntity:
        """Create lazy entity with self-contained operations."""
        page_id = page["id"]
        parent = page.get("parent", {})

        self.logger.info(f"🦴 LAZY_SKELETON Creating skeleton entity for page: {page_id}")

        # Create entity with only immediately available data
        entity = NotionPageEntity(
            entity_id=page_id,
            page_id=page_id,
            title=self._extract_page_title(page),
            parent_id=parent.get("page_id") or parent.get("database_id") or "",
            parent_type=parent.get("type", "workspace"),
            breadcrumbs=breadcrumbs,
            properties=page.get("properties", {}),
            url=page.get("url", ""),
            icon=page.get("icon"),
            cover=page.get("cover"),
            archived=page.get("archived", False),
            in_trash=page.get("in_trash", False),
            created_time=self._parse_datetime(page.get("created_time")),
            last_edited_time=self._parse_datetime(page.get("last_edited_time")),
            # Lazy fields - will be populated during materialization
            content=None,
            content_blocks_count=0,
            max_depth=0,
            property_entities=[],
            files=[],
        )

        # Add lazy operation for content aggregation
        entity.add_lazy_operation(
            "aggregate_content",
            self._create_content_fetcher(
                access_token=self.access_token,
                rate_limit_config={
                    "requests_per_second": self.RATE_LIMIT_REQUESTS,
                    "period": self.RATE_LIMIT_PERIOD,
                    "timeout": self.TIMEOUT_SECONDS,
                    "max_retries": self.MAX_RETRIES,
                },
            ),
            page_id,
            breadcrumbs,
        )

        self.logger.info(
            f"🔄 LAZY_OPERATION Added content aggregation operation for page: {page_id}"
        )

        # If it's a database page, add property extraction operation
        if database_id and database_schema:
            entity.add_lazy_operation(
                "extract_properties",
                self._create_property_extractor(self.access_token),
                page,
                database_id,
                database_schema,
            )
            self.logger.info(
                f"🔄 LAZY_OPERATION Added property extraction operation for page: {page_id}"
            )

        return entity

    def _create_content_fetcher(self, access_token: str, rate_limit_config: dict):
        """Create a content fetcher.

        Uses shared RPS limiting and optional concurrency gating.
        """

        async def fetch_content(page_id: str, breadcrumbs: List[Breadcrumb]) -> dict:
            """Fetch page content.

            If `batch_generation` is True, gate concurrent
            materializations with `_materialize_semaphore`.
            If False, run exactly like the original implementation
            (no source-level gate).
            """

            async def _do_fetch() -> dict:
                async with httpx.AsyncClient() as client:
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Notion-Version": "2022-06-28",
                    }

                    # Create request helper with shared rate limiting
                    async def make_request(method: str, url: str, **kwargs):
                        await NotionSource._shared_wait_for_rate_limit()
                        response = await getattr(client, method.lower())(
                            url, headers=headers, **kwargs
                        )
                        response.raise_for_status()
                        return response.json()

                    # Fetch all blocks and aggregate content
                    return await self._fetch_and_aggregate_blocks(
                        make_request, page_id, breadcrumbs
                    )

            if self.batch_generation:
                async with self._materialize_semaphore:
                    self.logger.debug(
                        f"[Notion] Materializing page {page_id} (batch_generation=True, "
                        f"batch_size={self.batch_size})"
                    )
                    return await _do_fetch()
            else:
                # Original flow: no semaphore gate
                return await _do_fetch()

        return fetch_content

    async def _fetch_and_aggregate_blocks(
        self, make_request, page_id: str, breadcrumbs: List[Breadcrumb]
    ) -> dict:
        """Fetch blocks and aggregate content."""
        content_parts = []
        files = []
        blocks_count = 0
        max_depth = 0

        async def fetch_blocks(block_id: str, depth: int = 0):
            nonlocal blocks_count, max_depth

            url = f"https://api.notion.com/v1/blocks/{block_id}/children"
            has_more = True
            start_cursor = None

            while has_more:
                params = {"start_cursor": start_cursor} if start_cursor else {}

                try:
                    response = await make_request("GET", url, params=params)
                    blocks = response.get("results", [])

                    for block in blocks:
                        blocks_count += 1
                        max_depth = max(max_depth, depth)

                        # Format block content
                        block_result = await self._format_block_content(block, depth, breadcrumbs)

                        if block_result["content"]:
                            content_parts.append(block_result["content"])

                        files.extend(block_result["files"])

                        # Process children if present
                        if block.get("has_children", False):
                            await fetch_blocks(block["id"], depth + 1)

                    has_more = response.get("has_more", False)
                    start_cursor = response.get("next_cursor")

                except Exception as e:
                    self.logger.error(f"Error fetching blocks for {block_id}: {str(e)}")
                    raise e

        # Start fetching from the page
        await fetch_blocks(page_id)

        return {
            "content": "\n\n".join(filter(None, content_parts)),
            "blocks_count": blocks_count,
            "max_depth": max_depth,
            "files": files,
        }

    def _create_property_extractor(self, access_token: str):
        """Create a self-contained property extractor."""

        async def extract_properties(
            page: dict, database_id: str, database_schema: dict
        ) -> List[NotionPropertyEntity]:
            """Extract properties with proper entity creation."""
            # Create notion instance for property formatting
            notion_source = NotionSource()

            page_id = page["id"]
            page_properties = page.get("properties", {})
            schema_properties = database_schema.get("properties", {})

            property_entities = []

            for prop_name, prop_value in page_properties.items():
                if prop_name in schema_properties:
                    schema_prop = schema_properties[prop_name]

                    try:
                        # Use the existing create_property_entity method
                        property_entity = notion_source._create_property_entity(
                            prop_name, prop_value, schema_prop, page_id, database_id
                        )
                        property_entities.append(property_entity)

                    except Exception as e:
                        self.logger.warning(
                            f"Error processing property {prop_name} for page {page_id}: {str(e)}"
                        )

            return property_entities

        return extract_properties
