"""Notion source implementation."""

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
    NotionDatabaseEntity,
    NotionPageEntity,
)
from airweave.platform.sources._base import BaseSource


@source("Notion", "notion", AuthType.oauth2, labels=["Knowledge Base", "Productivity"])
class NotionSource(BaseSource):
    """Notion source implementation."""

    # Add class constants for configuration
    TIMEOUT_SECONDS = 30.0
    RATE_LIMIT_REQUESTS = 3  # Maximum requests per second
    RATE_LIMIT_PERIOD = 1.0  # Time period in seconds
    MAX_RETRIES = 3

    @classmethod
    async def create(cls, access_token: str) -> "NotionSource":
        """Create a new Notion source."""
        instance = cls()
        instance.access_token = access_token
        return instance

    def __init__(self):
        """Initialize rate limiting state."""
        super().__init__()
        self._request_times = []
        self._lock = asyncio.Lock()

    async def _wait_for_rate_limit(self):
        """Implement rate limiting for Notion API requests."""
        async with self._lock:
            current_time = asyncio.get_event_loop().time()

            # Remove old request times
            self._request_times = list(
                filter(lambda t: current_time - t < self.RATE_LIMIT_PERIOD, self._request_times)
            )

            if len(self._request_times) >= self.RATE_LIMIT_REQUESTS:
                # Wait until enough time has passed
                sleep_time = self._request_times[0] + self.RATE_LIMIT_PERIOD - current_time
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

                # Clean up old requests again after waiting
                self._request_times = [
                    t for t in self._request_times if current_time - t < self.RATE_LIMIT_PERIOD
                ]

            self._request_times.append(current_time)

    @retry(
        retry=retry_if_exception_type((TimeoutException, ReadTimeout)),
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=4, max=10),
    )
    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Dict:
        """Make an authenticated GET request to the Notion API with rate limiting."""
        await self._wait_for_rate_limit()

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Notion-Version": "2022-06-28",
        }

        try:
            response = await client.get(url, headers=headers, timeout=self.TIMEOUT_SECONDS)
            response.raise_for_status()
            return response.json()
        except (TimeoutException, ReadTimeout) as e:
            logger.warning(f"Timeout while requesting {url}. Retrying... Error: {str(e)}")
            raise

    async def _post_with_auth(self, client: httpx.AsyncClient, url: str, json_data: Dict) -> Dict:
        """Make an authenticated POST request to the Notion API."""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Notion-Version": "2022-06-28",
        }
        response = await client.post(url, headers=headers, json=json_data)
        response.raise_for_status()
        return response.json()

    async def _search_notion_objects(
        self, client: httpx.AsyncClient, query: str = "", filter_type: str = None
    ) -> AsyncGenerator[Dict, None]:
        """Search for Notion objects using the search endpoint.

        Args:
            client: httpx.AsyncClient
            query: Optional search query
            filter_type: Optional filter for object type ("page" or "database")

        Returns:
            AsyncGenerator[Dict, None]: A generator of Notion objects
        """
        url = "https://api.notion.com/v1/search"
        has_more = True
        start_cursor = None

        while has_more:
            json_data = {"query": query}
            if filter_type:
                json_data["filter"] = {"property": "object", "value": filter_type}
            if start_cursor:
                json_data["start_cursor"] = start_cursor

            response = await self._post_with_auth(client, url, json_data)

            for result in response.get("results", []):
                yield result

            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

    async def _get_block_children(
        self, client: httpx.AsyncClient, block_id: str
    ) -> AsyncGenerator[Dict, None]:
        """Retrieve all children blocks of a block."""
        url = f"https://api.notion.com/v1/blocks/{block_id}/children"
        has_more = True
        start_cursor = None

        while has_more:
            url_with_params = url
            if start_cursor:
                url_with_params = f"{url}?start_cursor={start_cursor}"

            response = await self._get_with_auth(client, url_with_params)

            for block in response.get("results", []):
                yield block

            has_more = response.get("has_more", False)
            start_cursor = response.get("next_cursor")

    def _extract_block_content(self, block: Dict) -> str:
        """Extract text content from a Notion block according to the API specification.

        Reference: https://developers.notion.com/reference/block

        Args:
            block (Dict): The Notion block object

        Returns:
            str: The extracted text content
        """
        block_type = block.get("type", "")
        if not block_type or block_type == "unsupported":
            return ""

        block_content = block.get(block_type, {})

        # Use dedicated handlers for different block types
        if "rich_text" in block_content:
            return self._handle_rich_text_block(block_type, block_content)
        elif block_type == "code":
            return self._handle_code_block(block_content)
        elif block_type in ["image", "video", "file", "pdf"]:
            return self._handle_media_block(block_type, block_content)
        elif block_type in ["child_page", "child_database"]:
            return self._handle_child_block(block_type, block_content)
        elif block_type in ["column", "column_list", "template", "synced_block"]:
            return ""

        return ""

    def _handle_rich_text_block(self, block_type: str, block_content: Dict) -> str:
        """Handle blocks that contain rich text arrays."""
        text_parts = [text_entry.get("plain_text", "") for text_entry in block_content["rich_text"]]
        text = " ".join(text_parts)

        # Format based on block type
        if block_type == "bulleted_list_item":
            return f"• {text}"
        elif block_type == "numbered_list_item":
            return text  # Number prefixes handled by parent context
        elif block_type == "to_do":
            checkbox = "☑" if block_content.get("checked", False) else "☐"
            return f"{checkbox} {text}"
        elif block_type in ["heading_1", "heading_2", "heading_3"]:
            prefix = "▸ " if block_content.get("is_toggleable", False) else ""
            return f"{prefix}{text}"

        return text

    def _handle_code_block(self, block_content: Dict) -> str:
        """Handle code blocks with language and caption."""
        language = block_content.get("language", "")
        code_text = " ".join(
            text.get("plain_text", "") for text in block_content.get("rich_text", [])
        )
        caption = " ".join(text.get("plain_text", "") for text in block_content.get("caption", []))

        if caption:
            return f"```{language}\n{code_text}\n```\n{caption}"
        return f"```{language}\n{code_text}\n```"

    def _handle_media_block(self, block_type: str, block_content: Dict) -> str:
        """Handle media blocks (image, video, file, pdf)."""
        caption = " ".join(text.get("plain_text", "") for text in block_content.get("caption", []))
        url = block_content.get("external", {}).get("url", "") or block_content.get("file", {}).get(
            "url", ""
        )

        if caption:
            return f"[{block_type}: {caption}]({url})"
        return f"[{block_type}]({url})"

    def _handle_child_block(self, block_type: str, block_content: Dict) -> str:
        """Handle child page and database blocks."""
        if block_type == "child_page":
            return f"[Page: {block_content.get('title', '')}]"
        return f"[Database: {block_content.get('title', '')}]"

    def _create_database_entity(self, database: Dict) -> NotionDatabaseEntity:
        """Create a database entity from API response."""
        # Safely extract database title
        title = "Untitled"
        if database.get("title"):
            title_items = database.get("title", [])
            if title_items and isinstance(title_items, list) and len(title_items) > 0:
                first_title = title_items[0]
                if isinstance(first_title, dict):
                    title = first_title.get("plain_text", "Untitled")

        return NotionDatabaseEntity(
            database_id=database["id"],
            entity_id=database["id"],
            name=title,
            description="",  # Databases don't have descriptions in the same way as pages
            created_time=database.get("created_time"),
            last_edited_time=database.get("last_edited_time"),
        )

    def _create_page_entity(self, page: Dict, breadcrumbs: List[Breadcrumb]) -> NotionPageEntity:
        """Create a page entity from API response."""
        parent = page.get("parent", {})

        # Safely extract title with proper nesting and fallbacks
        title = (
            page.get("properties", {})
            .get("title", {})
            .get("title", [{}])[0:1][  # Get first element or empty list
                0
            ]  # Get first element (safe because of [0:1] above)
            .get("plain_text", "Untitled")
            if isinstance(page.get("properties", {}).get("title"), dict)
            else "Untitled"
        )

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
        """Create a block entity from API response."""
        text_content = self._extract_block_content(block)

        return NotionBlockEntity(
            block_id=block["id"],
            entity_id=block["id"],
            breadcrumbs=breadcrumbs,
            parent_id=parent_id,
            block_type=block["type"],
            text_content=text_content,
            has_children=block.get("has_children", False),
            children_ids=[],  # Will be populated if has_children is True
            created_time=block.get("created_time"),
            last_edited_time=block.get("last_edited_time"),
        )

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all entities from Notion.

        Instead of traversing a hierarchy, we use Notion's search endpoint to get:
        1. All databases
        2. All pages (both in databases and standalone)
        3. All blocks within pages
        """
        async with httpx.AsyncClient() as client:
            # 1. Get all databases
            async for database in self._search_notion_objects(client, filter_type="database"):
                database_entity = self._create_database_entity(database)
                yield database_entity

            # 2. Get all pages
            async for page in self._search_notion_objects(client, filter_type="page"):
                # Create breadcrumbs based on parent
                breadcrumbs = []
                parent = page.get("parent", {})
                if parent.get("type") == "database_id":
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=parent["database_id"],
                            name="Parent Database",  # We could cache database names if needed
                            type="database",
                        )
                    )
                elif parent.get("type") == "page_id":
                    breadcrumbs.append(
                        Breadcrumb(
                            entity_id=parent["page_id"],
                            name="Parent Page",  # We could cache page names if needed
                            type="page",
                        )
                    )

                page_entity = self._create_page_entity(page, breadcrumbs)
                yield page_entity

                # 3. Get all blocks for this page
                page_breadcrumb = Breadcrumb(
                    entity_id=page["id"], name=page_entity.title, type="page"
                )
                block_breadcrumbs = [*breadcrumbs, page_breadcrumb]

                async for block in self._get_block_children(client, page["id"]):
                    block_entity = self._create_block_entity(block, page["id"], block_breadcrumbs)
                    yield block_entity

                    # If block has children, get them too
                    if block["has_children"]:
                        block_breadcrumb = Breadcrumb(
                            entity_id=block["id"],
                            name=block_entity.text_content or "Block",
                            type="block",
                        )
                        child_breadcrumbs = [*block_breadcrumbs, block_breadcrumb]

                        async for child_block in self._get_block_children(client, block["id"]):
                            child_entity = self._create_block_entity(
                                child_block, block["id"], child_breadcrumbs
                            )
                            yield child_entity
