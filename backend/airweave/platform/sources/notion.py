"""Notion connector for syncing content from Notion workspaces to Airweave.

This module provides a source implementation for extracting pages and blocks from Notion,
handling API rate limits, and converting API responses to entity objects.
"""

import asyncio
from typing import AsyncGenerator, Dict, List

import httpx
from httpx import ReadTimeout, TimeoutException
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.notion import (
    NotionBlockEntity,
    NotionPageEntity,
)
from airweave.platform.sources._base import BaseSource


@source("Notion", "notion", AuthType.oauth2, labels=["Knowledge Base", "Productivity"])
class NotionSource(BaseSource):
    """Notion source implementation."""

    # Rate limiting constants
    TIMEOUT_SECONDS = 30.0
    RATE_LIMIT_REQUESTS = 3  # Maximum requests per second
    RATE_LIMIT_PERIOD = 1.0  # Time period in seconds
    MAX_RETRIES = 3

    @classmethod
    async def create(cls, access_token: str) -> "NotionSource":
        """Create a new Notion source."""
        logger.info("Creating new Notion source")
        instance = cls()
        instance.access_token = access_token
        return instance

    def __init__(self):
        """Initialize rate limiting state."""
        super().__init__()
        self._request_times = []
        self._lock = asyncio.Lock()
        self._stats = {
            "api_calls": 0,
            "rate_limit_waits": 0,
            "pages_found": 0,
            "blocks_found": 0,
            "max_depth": 0,
        }
        logger.info("Initialized Notion source")

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
                    logger.debug(
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

    @retry(
        retry=retry_if_exception_type((TimeoutException, ReadTimeout)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> dict:
        """Make an authenticated GET request to the Notion API."""
        await self._wait_for_rate_limit()
        logger.debug(f"GET request to {url}")
        self._stats["api_calls"] += 1

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Notion-Version": "2022-06-28",
        }

        try:
            response = await client.get(url, headers=headers, timeout=self.TIMEOUT_SECONDS)
            logger.debug(f"GET response from {url}: status={response.status_code}")

            if response.status_code != 200:
                logger.warning(
                    f"Non-200 response from Notion API: {response.status_code} for {url}"
                )
                logger.debug(f"Response body: {response.text[:200]}...")

            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error during GET request to {url}: {str(e)}")
            raise

    @retry(
        retry=retry_if_exception_type((TimeoutException, ReadTimeout)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def _post_with_auth(self, client: httpx.AsyncClient, url: str, json_data: dict) -> dict:
        """Make an authenticated POST request to the Notion API."""
        await self._wait_for_rate_limit()
        logger.debug(f"POST request to {url}")
        self._stats["api_calls"] += 1

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Notion-Version": "2022-06-28",
        }

        try:
            response = await client.post(
                url, headers=headers, json=json_data, timeout=self.TIMEOUT_SECONDS
            )
            logger.debug(f"POST response from {url}: status={response.status_code}")

            if response.status_code != 200:
                logger.warning(
                    f"Non-200 response from Notion API: {response.status_code} for {url}"
                )
                logger.debug(f"Response body: {response.text[:200]}...")

            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error during POST request to {url}: {str(e)}")
            raise

    async def get_all_pages(self) -> AsyncGenerator[dict, None]:
        """Retrieve all pages from Notion.

        Returns:
            AsyncGenerator yielding each page object from the Notion API.
        """
        logger.info("Fetching all pages from Notion")

        async with httpx.AsyncClient() as client:
            url = "https://api.notion.com/v1/search"
            has_more = True
            start_cursor = None
            results_count = 0

            while has_more:
                # Prepare search request with pagination
                json_data = {
                    "filter": {"property": "object", "value": "page"},
                    "page_size": 100,  # Maximum allowed by API
                }

                if start_cursor:
                    json_data["start_cursor"] = start_cursor
                    logger.debug(f"Continuing page search with cursor: {start_cursor}")

                try:
                    # Make authenticated request to search endpoint
                    response = await self._post_with_auth(client, url, json_data)

                    # Process results
                    page_results = response.get("results", [])
                    page_count = len(page_results)
                    results_count += page_count
                    self._stats["pages_found"] += page_count

                    logger.info(f"Found {page_count} pages in this batch (total: {results_count})")

                    # Yield each page individually
                    for page in page_results:
                        yield page

                    # Check if more pages are available
                    has_more = response.get("has_more", False)
                    start_cursor = response.get("next_cursor")

                    if has_more:
                        logger.debug("More pages available, will continue with next cursor")
                    else:
                        logger.info(f"Completed page search, found {results_count} total pages")

                except Exception as e:
                    logger.error(f"Error fetching pages from Notion: {str(e)}")
                    raise

    async def _get_block_children_recursive(
        self,
        client: httpx.AsyncClient,
        block_id: str,
        parent_id: str,
        breadcrumbs: List[Breadcrumb],
        depth: int = 0,
    ) -> AsyncGenerator[NotionBlockEntity, None]:
        """Retrieve all children blocks of a block recursively.

        Args:
            client: HTTP client to use for requests
            block_id: ID of the block to get children for
            parent_id: ID of the parent block or page
            breadcrumbs: List of breadcrumbs for the block
            depth: Current depth in the block hierarchy (used for logging and statistics)

        Yields:
            NotionBlockEntity objects for each block and its children
        """
        logger.debug(f"Getting children of block {block_id} at depth {depth}")

        # Track max depth for statistics
        if depth > self._stats["max_depth"]:
            self._stats["max_depth"] = depth

        url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        has_more = True
        start_cursor = None

        while has_more:
            url_with_params = url
            if start_cursor:
                url_with_params = f"{url}?start_cursor={start_cursor}"
                logger.debug(f"Continuing block children fetch with cursor: {start_cursor}")

            try:
                response = await self._get_with_auth(client, url_with_params)
                blocks = response.get("results", [])

                logger.debug(f"Found {len(blocks)} children blocks for {block_id} at depth {depth}")
                self._stats["blocks_found"] += len(blocks)

                # Process each block
                for block in blocks:
                    # Create and yield the block entity
                    block_entity = self._create_block_entity(block, parent_id, breadcrumbs)
                    yield block_entity

                    # If block has children, get them recursively
                    if block.get("has_children", False):
                        # Create a new breadcrumb for this block
                        block_breadcrumb = Breadcrumb(
                            entity_id=block["id"],
                            name=block_entity.text_content[:30] + "..."
                            if len(block_entity.text_content) > 30
                            else block_entity.text_content or "Block",
                            type="block",
                        )

                        # Add it to the existing breadcrumbs
                        child_breadcrumbs = breadcrumbs + [block_breadcrumb]

                        # Recursively get children of this block
                        async for child_entity in self._get_block_children_recursive(
                            client, block["id"], block["id"], child_breadcrumbs, depth + 1
                        ):
                            yield child_entity

                # Check for pagination
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

            except Exception as e:
                logger.error(f"Error fetching children of block {block_id}: {str(e)}")
                raise

    def _extract_block_content(self, block: Dict) -> str:
        """Extract text content from a Notion block.

        Args:
            block: Block object from Notion API

        Returns:
            Extracted text content as string
        """
        block_type = block.get("type", "")

        if not block_type or block_type == "unsupported":
            return ""

        block_content = block.get(block_type, {})

        # Handle different block types
        if "rich_text" in block_content:
            return self._extract_rich_text_content(block_type, block_content)
        elif block_type == "code":
            return self._extract_code_block_content(block_content)
        elif block_type in ["image", "video", "file", "pdf"]:
            return self._extract_media_block_content(block_type, block_content)
        elif block_type == "child_page":
            return f"[Page: {block_content.get('title', '')}]"
        elif block_type == "child_database":
            return f"[Database: {block_content.get('title', '')}]"

        # For other block types or if no content could be extracted
        return ""

    def _extract_rich_text_content(self, block_type: str, block_content: Dict) -> str:
        """Extract content from rich text blocks.

        Args:
            block_type: Type of the block
            block_content: Content of the block

        Returns:
            Formatted text content
        """
        text_parts = [
            text_entry.get("plain_text", "") for text_entry in block_content.get("rich_text", [])
        ]
        text = " ".join(text_parts)

        # Format based on block type
        if block_type == "bulleted_list_item":
            return f"• {text}"
        elif block_type == "numbered_list_item":
            return text
        elif block_type == "to_do":
            checkbox = "☑" if block_content.get("checked", False) else "☐"
            return f"{checkbox} {text}"
        elif block_type in ["heading_1", "heading_2", "heading_3"]:
            prefix = "▸ " if block_content.get("is_toggleable", False) else ""
            return f"{prefix}{text}"

        return text

    def _extract_code_block_content(self, block_content: Dict) -> str:
        """Extract content from code blocks.

        Args:
            block_content: Content of the code block

        Returns:
            Formatted code content
        """
        language = block_content.get("language", "")
        code_text = " ".join(
            text.get("plain_text", "") for text in block_content.get("rich_text", [])
        )
        caption = " ".join(text.get("plain_text", "") for text in block_content.get("caption", []))

        if caption:
            return f"```{language}\n{code_text}\n```\n{caption}"
        return f"```{language}\n{code_text}\n```"

    def _extract_media_block_content(self, block_type: str, block_content: Dict) -> str:
        """Extract content from media blocks.

        Args:
            block_type: Type of the media block
            block_content: Content of the block

        Returns:
            Formatted media content with optional caption
        """
        caption = " ".join(text.get("plain_text", "") for text in block_content.get("caption", []))
        url = block_content.get("external", {}).get("url", "") or block_content.get("file", {}).get(
            "url", ""
        )

        if caption:
            return f"[{block_type}: {caption}]({url})"
        return f"[{block_type}]({url})"

    def _create_page_entity(self, page: Dict, breadcrumbs: List[Breadcrumb]) -> NotionPageEntity:
        """Create a page entity from API response.

        Args:
            page: Page object from Notion API
            breadcrumbs: List of breadcrumbs for this page

        Returns:
            NotionPageEntity representing this page
        """
        page_id = page["id"]
        logger.info(f"Creating page entity for {page_id}")
        parent = page.get("parent", {})

        # Log breadcrumb information
        if breadcrumbs:
            breadcrumb_info = ", ".join([f"{b.type}:{b.entity_id}" for b in breadcrumbs])
            logger.debug(f"Page {page_id} breadcrumbs: {breadcrumb_info}")
        else:
            logger.debug(f"Page {page_id} has no breadcrumbs (likely workspace-level)")

        # Safely extract title with proper nesting and fallbacks
        try:
            title = (
                page.get("properties", {})
                .get("title", {})
                .get("title", [{}])[0:1][0]  # Get first element safely
                .get("plain_text", "Untitled")
                if isinstance(page.get("properties", {}).get("title"), dict)
                else "Untitled"
            )
        except (IndexError, AttributeError, KeyError) as e:
            logger.warning(f"Error extracting title for page {page_id}: {str(e)}")
            title = "Untitled"

        logger.debug(f"Page {page_id} title: '{title}'")

        return NotionPageEntity(
            page_id=page["id"],
            entity_id=page["id"],
            breadcrumbs=breadcrumbs,
            parent_id=parent.get("page_id") or parent.get("database_id") or "",
            parent_type=parent.get("type", "workspace"),
            title=title,
            created_time=page.get("created_time"),
            last_edited_time=page.get("last_edited_time"),
            archived=page.get("archived", False),
            content=None,  # Will be populated from blocks
        )

    def _create_block_entity(
        self, block: Dict, parent_id: str, breadcrumbs: List[Breadcrumb]
    ) -> NotionBlockEntity:
        """Create a block entity from API response.

        Args:
            block: Block object from Notion API
            parent_id: ID of the parent block or page
            breadcrumbs: List of breadcrumbs for this block

        Returns:
            NotionBlockEntity representing this block
        """
        block_id = block["id"]
        block_type = block["type"]
        logger.debug(
            f"Creating block entity {block_id} of type '{block_type}' under parent {parent_id}"
        )

        # Extract text content from the block
        text_content = self._extract_block_content(block)
        content_preview = text_content[:30] + "..." if len(text_content) > 30 else text_content
        logger.debug(f"Block {block_id} content preview: '{content_preview}'")

        # Log breadcrumb information
        if breadcrumbs:
            logger.debug(f"Block {block_id} breadcrumbs depth: {len(breadcrumbs)}")

        return NotionBlockEntity(
            block_id=block["id"],
            entity_id=block["id"],
            breadcrumbs=breadcrumbs,
            parent_id=parent_id,
            block_type=block["type"],
            text_content=text_content,
            has_children=block.get("has_children", False),
            children_ids=[],  # Not used since we're fetching children immediately
            created_time=block.get("created_time"),
            last_edited_time=block.get("last_edited_time"),
        )

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all entities from Notion.

        This function:
        1. Fetches all pages using get_all_pages
        2. For each page, creates a page entity with breadcrumbs
        3. For each page, recursively fetches all block content
        4. Yields all entities (pages and blocks)

        Returns:
            AsyncGenerator yielding NotionPageEntity and NotionBlockEntity objects
        """
        logger.info("Starting Notion entity generation")
        self._stats = {
            "api_calls": 0,
            "rate_limit_waits": 0,
            "pages_found": 0,
            "blocks_found": 0,
            "max_depth": 0,
        }

        try:
            # First, collect all pages and build a page map for breadcrumb creation
            page_map = {}
            all_pages = []

            async for page in self.get_all_pages():
                page_id = page["id"]
                page_map[page_id] = page
                all_pages.append(page)

            logger.info(
                f"Collected {len(all_pages)} pages, now generating entities with breadcrumbs"
            )

            # Now process each page to create entities with proper breadcrumbs
            async with httpx.AsyncClient() as client:
                for page in all_pages:
                    page_id = page["id"]
                    parent = page.get("parent", {})
                    parent_type = parent.get("type", "")
                    breadcrumbs = []

                    # Create breadcrumb if parent is a page
                    if parent_type == "page_id":
                        parent_page_id = parent.get("page_id")
                        if parent_page_id in page_map:
                            parent_page = page_map[parent_page_id]
                            # Extract parent title
                            parent_title = "Untitled"
                            try:
                                parent_title = (
                                    parent_page.get("properties", {})
                                    .get("title", {})
                                    .get("title", [{}])[0]
                                    .get("plain_text", "Untitled")
                                )
                            except (IndexError, AttributeError, KeyError):
                                logger.warning(
                                    f"Error extracting title for parent page {parent_page_id}"
                                )

                            breadcrumbs.append(
                                Breadcrumb(entity_id=parent_page_id, name=parent_title, type="page")
                            )
                            logger.debug(
                                f"Added parent page breadcrumb for {page_id}: "
                                f"{parent_title} ({parent_page_id})"
                            )

                    # Create and yield the page entity
                    page_entity = self._create_page_entity(page, breadcrumbs)
                    yield page_entity

                    # Create breadcrumb for this page to use in blocks
                    page_breadcrumb = Breadcrumb(
                        entity_id=page_id, name=page_entity.title, type="page"
                    )

                    # Now fetch all blocks for this page recursively
                    logger.info(f"Fetching blocks for page {page_entity.title} ({page_id})")

                    async for block_entity in self._get_block_children_recursive(
                        client, page_id, page_id, [*breadcrumbs, page_breadcrumb], 0
                    ):
                        yield block_entity

            logger.info(f"Notion sync complete. Stats: {self._stats}")

        except Exception as e:
            logger.error(f"Error during Notion entity generation: {str(e)}", exc_info=True)
            raise
