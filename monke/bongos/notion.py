"""Notion-specific bongo implementation.

Creates, updates, and deletes test pages via the real Notion API.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional


import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class NotionBongo(BaseBongo):
    """Bongo for Notion that creates pages for end-to-end testing."""

    connector_type = "notion"
    API_BASE = "https://api.notion.com/v1"
    API_VERSION = "2022-06-28"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Notion bongo."""
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 5))
        self.llm_model = kwargs.get("llm_model", None)

        # Rate limiting: ~3 requests per second
        rate_limit_ms = int(kwargs.get("rate_limit_delay_ms", 334))
        self.rate_limit_delay: float = rate_limit_ms / 1000.0

        # Optional parent page ID (recommended)
        raw_parent = kwargs.get("parent_page_id")
        # Ignore unset/placeholder env interpolation values like ${NOTION_PARENT_PAGE_ID}
        if isinstance(raw_parent, str) and raw_parent.startswith("${"):
            raw_parent = None
        self.parent_id: Optional[str] = raw_parent

        # Runtime state
        self._pages: List[Dict[str, Any]] = []
        self._parent_page_id: Optional[str] = None
        self._last_request_time = 0

        self.logger = get_logger("notion_bongo")

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a rate-limited request to the Notion API."""
        # Simple rate limiting
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        if time_since_last < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - time_since_last)

        url = f"{self.API_BASE}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Notion-Version": self.API_VERSION,
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=json_data)
            elif method == "PATCH":
                response = await client.patch(url, headers=headers, json=json_data)
            elif method == "DELETE":
                # Notion uses PATCH with archived=true
                json_data = {"archived": True}
                response = await client.patch(url, headers=headers, json=json_data)

            self._last_request_time = time.time()

            if response.status_code >= 400:
                self.logger.error(f"Notion API error: {response.status_code} - {response.text}")
                response.raise_for_status()

            return response.json()

    async def _resolve_parent_page(self) -> str:
        """Resolve a parent page to create pages under.

        Priority:
        1) Use provided parent_page_id
        2) Use the first accessible page from Notion search
        """
        if self.parent_id:
            self._parent_page_id = self.parent_id
            return self._parent_page_id

        # Fallback: search for any accessible page to use as parent
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Notion-Version": self.API_VERSION,
            "Content-Type": "application/json",
        }
        payload = {
            "filter": {"value": "page", "property": "object"},
            "page_size": 1,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.API_BASE}/search", headers=headers, json=payload)
            if resp.status_code != 200:
                self.logger.error(f"Notion search failed: {resp.status_code} - {resp.text}")
                resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                raise ValueError(
                    "No accessible Notion pages found for the integration. "
                    "Provide 'parent_page_id' in config_fields to specify a parent page."
                )
            self._parent_page_id = results[0]["id"]
            self.logger.info(f"📄 Using parent page: {self._parent_page_id}")
            return self._parent_page_id

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test pages via real Notion API."""
        self.logger.info(f"🥁 Creating {self.entity_count} test pages in Notion")

        parent_page_id = await self._resolve_parent_page()

        from monke.generation.notion import generate_notion_page

        created_pages = []

        for i in range(self.entity_count):
            token = str(uuid.uuid4())[:8]

            # Generate page content
            title, content_blocks = await generate_notion_page(self.llm_model, token)
            # Embed token in title to make it reliably searchable downstream
            title_with_token = f"{token} {title}"

            # Create the page
            page_data = {
                "parent": {"type": "page_id", "page_id": parent_page_id},
                # For pages under a page, the title property key is 'title'
                "properties": {
                    "title": [{"type": "text", "text": {"content": title_with_token}}]
                },
                "children": content_blocks
            }

            page = await self._make_request("POST", "pages", page_data)

            created_pages.append({
                "id": page["id"],
                "title": title_with_token,
                "token": token,
                "url": page["url"],
                # Use a natural phrase to aid vector search while still validating token presence
                "expected_content": f"Monke verification token {token}"
            })

            self.logger.info(f"📄 Created page: {title} (token: {token})")

        self._pages = created_pages
        self.created_entities = created_pages
        return created_pages

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update test pages via real Notion API."""
        if not self._pages:
            self.logger.warning("No pages to update")
            return []

        self.logger.info(f"🥁 Updating {len(self._pages)} test pages")

        from monke.generation.notion import generate_notion_page

        updated_pages = []
        pages_to_update = min(3, len(self._pages))

        for i in range(pages_to_update):
            page = self._pages[i]
            token = page["token"]

            # Generate new content
            title, content_blocks = await generate_notion_page(
                self.llm_model,
                token,
                update=True
            )

            # Update the page
            # Keep token in the updated title as well for reliable verification
            page_update = {
                "properties": {
                    "title": [{"type": "text", "text": {"content": f"{token} {title} (Updated)"}}]
                }
            }

            updated_page = await self._make_request("PATCH", f"pages/{page['id']}", page_update)

            updated_pages.append({
                "id": updated_page["id"],
                "title": f"{token} {title} (Updated)",
                "token": token,
                "url": updated_page["url"],
                "expected_content": f"Monke verification token {token}"
            })

            self.logger.info(f"📝 Updated page: {page['title']}")

        return updated_pages

    async def delete_entities(self) -> List[str]:
        """Delete all test pages via real Notion API."""
        if not self._pages:
            return []

        self.logger.info(f"🗑️ Deleting {len(self._pages)} test pages")

        deleted_ids = []

        for page in self._pages:
            await self._make_request("DELETE", f"pages/{page['id']}")
            deleted_ids.append(page["id"])
            self.logger.info(f"🗑️ Archived page: {page['title']}")

        # No database to archive

        return deleted_ids

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete specific pages via real Notion API."""
        self.logger.info(f"🗑️ Deleting {len(entities)} specific pages")

        deleted_ids = []

        for entity in entities:
            page_id = entity["id"]
            await self._make_request("DELETE", f"pages/{page_id}")
            deleted_ids.append(page_id)
            self.logger.info(f"🗑️ Archived page: {entity.get('title', page_id)}")

        # Remove from tracking
        deleted_id_set = set(deleted_ids)
        self._pages = [p for p in self._pages if p["id"] not in deleted_id_set]

        return deleted_ids

    async def cleanup(self):
        """Clean up any remaining test data."""
        self.logger.info("🧹 Cleaning up Notion test data")

        if self._pages:
            await self.delete_entities()

        self.logger.info("✅ Notion cleanup complete")
