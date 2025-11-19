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
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")

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
        self, method: str, endpoint: str, json_data: Optional[Dict[str, Any]] = None
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
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient() as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            elif method == "POST":
                response = await client.post(url, headers=headers, json=json_data)
            elif method == "PATCH":
                response = await client.patch(url, headers=headers, json=json_data)
            elif method == "DELETE":
                # Notion uses PATCH with archived=true to archive (trash) pages.
                # There is no dedicated DELETE for pages; we standardize on archived.
                json_data = {"archived": True}
                response = await client.patch(url, headers=headers, json=json_data)

            self._last_request_time = time.time()

            if response.status_code >= 400:
                self.logger.error(
                    f"Notion API error: {response.status_code} - {response.text}"
                )
                response.raise_for_status()

            return response.json()

    async def _resolve_parent_page(self) -> str:
        """Resolve or create a parent page for monke test pages.

        Creates a dedicated "Monke Test Container" page to hold all test pages.
        This allows clean deletion of all test pages by archiving the container.

        Note: Workspace-root pages cannot be archived via Notion API, so we need
        a deletable parent page.
        """
        if self.parent_id:
            self._parent_page_id = self.parent_id
            self.logger.info(f"📄 Using configured parent page: {self._parent_page_id}")
            return self._parent_page_id

        # Check if a monke test container already exists
        search_payload = {
            "query": "Monke Test Container",
            "filter": {"value": "page", "property": "object"},
            "page_size": 1,
        }

        response = await self._make_request("POST", "search", search_payload)
        results = response.get("results", [])

        if results:
            # Reuse existing container
            self._parent_page_id = results[0]["id"]
            self.logger.info(
                f"📄 Using existing Monke Test Container: {self._parent_page_id}"
            )
            return self._parent_page_id

        # Create a new container page at workspace root
        container_data = {
            "parent": {"type": "workspace", "workspace": True},
            "properties": {
                "title": {"title": [{"text": {"content": "Monke Test Container"}}]}
            },
        }

        container = await self._make_request("POST", "pages", container_data)
        self._parent_page_id = container["id"]
        self.logger.info(f"📄 Created Monke Test Container: {self._parent_page_id}")
        return self._parent_page_id

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test pages via real Notion API."""
        self.logger.info("📝 ============================================")
        self.logger.info(f"📝 Creating {self.entity_count} test pages in Notion")
        self.logger.info("📝 ============================================")

        parent_page_id = await self._resolve_parent_page()
        self.logger.info(f"📝 Parent page ID for new pages: {parent_page_id}")

        from monke.generation.notion import generate_notion_page

        created_pages = []

        for i in range(self.entity_count):
            token = str(uuid.uuid4())[:8]
            self.logger.info(
                f"📝 Creating page {i + 1}/{self.entity_count} with token: {token}"
            )

            # Generate page content
            title, content_blocks = await generate_notion_page(self.openai_model, token)
            # Embed token in title to make it reliably searchable downstream
            title_with_token = f"{token} {title}"

            self.logger.info(f"📝 Generated title: {title_with_token}")
            self.logger.info(f"📝 Generated {len(content_blocks)} content blocks")

            # Create the page WITHOUT children first
            # Note: Notion API doesn't allow children in page creation when parent is a page_id
            # Children must be added via PATCH to blocks/{page_id}/children
            page_data = {
                "parent": {"type": "page_id", "page_id": parent_page_id},
                # Correct Notion API structure for page title property
                "properties": {
                    "title": {"title": [{"text": {"content": title_with_token}}]}
                },
            }

            self.logger.info("📝 Creating page via API...")
            page = await self._make_request("POST", "pages", page_data)
            page_id = page["id"]
            self.logger.info(f"✅ Page created: {page_id}")

            # Now add the content blocks to the created page
            if content_blocks:
                try:
                    self.logger.info(
                        f"📝 Adding {len(content_blocks)} content blocks to page..."
                    )
                    await self._make_request(
                        "PATCH",
                        f"blocks/{page['id']}/children",
                        {"children": content_blocks},
                    )
                    self.logger.info(
                        f"✅ Added {len(content_blocks)} blocks to page {page['id']}"
                    )
                except Exception as e:
                    self.logger.warning(
                        f"⚠️  Failed to add content blocks to page {page['id']}: {e}"
                    )

            created_pages.append(
                {
                    "id": page["id"],
                    "title": title_with_token,
                    "token": token,
                    "url": page["url"],
                    # Use a natural phrase to aid vector search while still validating token presence
                    "expected_content": f"Monke verification token {token}",
                }
            )

            self.logger.info(
                f"✅ Page {i + 1}/{self.entity_count} created: {title_with_token} [{page_id}]"
            )

        self._pages = created_pages
        self.created_entities = created_pages

        self.logger.info("📝 ============================================")
        self.logger.info(f"📝 Successfully created {len(created_pages)} pages")
        self.logger.info("📝 Page IDs:")
        for p in created_pages:
            self.logger.info(f"   - {p['title']} [{p['id']}]")
        self.logger.info("📝 ============================================")

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
                self.openai_model, token, update=True
            )

            # Update the page
            # Keep token in the updated title as well for reliable verification
            page_update = {
                "properties": {
                    "title": {
                        "title": [{"text": {"content": f"{token} {title} (Updated)"}}]
                    }
                }
            }

            updated_page = await self._make_request(
                "PATCH", f"pages/{page['id']}", page_update
            )

            updated_pages.append(
                {
                    "id": updated_page["id"],
                    "title": f"{token} {title} (Updated)",
                    "token": token,
                    "url": updated_page["url"],
                    "expected_content": f"Monke verification token {token}",
                }
            )

            self.logger.info(f"📝 Updated page: {page['title']}")

        return updated_pages

    async def delete_entities(self) -> List[str]:
        """Delete all test pages via real Notion API (moves them to trash)."""
        if not self._pages:
            self.logger.info("ℹ️  No pages to delete")
            return []

        self.logger.info("🗑️ ============================================")
        self.logger.info(f"🗑️ Trashing {len(self._pages)} test pages")
        self.logger.info("🗑️ ============================================")

        deleted_ids = []

        for i, page in enumerate(self._pages, 1):
            page_id = page["id"]
            page_title = page["title"]
            self.logger.info(
                f"🗑️ Trashing page {i}/{len(self._pages)}: {page_title} [{page_id}]"
            )

            # Trash the page (DELETE sets in_trash=true)
            trashed_page = await self._make_request("DELETE", f"pages/{page_id}")
            deleted_ids.append(page_id)

            # Verify the page is actually marked as trashed
            is_trashed = trashed_page.get("in_trash", False)
            is_archived = trashed_page.get("archived", False)
            self.logger.info(
                f"✅ Trashed: {page_title} [{page_id}] "
                f"- API returned: in_trash={is_trashed}, archived={is_archived}"
            )

            if not is_trashed:
                self.logger.error(
                    f"❌ WARNING: Page {page_id} was 'trashed' but API returned in_trash={is_trashed}! "
                    f"This page may still appear in searches."
                )

        self.logger.info("🗑️ ============================================")
        self.logger.info(f"🗑️ Successfully trashed {len(deleted_ids)} pages")
        self.logger.info("🗑️ ============================================")

        return deleted_ids

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific pages via real Notion API (moves them to trash)."""
        self.logger.info(f"🗑️ Trashing {len(entities)} specific pages")

        deleted_ids = []

        for entity in entities:
            page_id = entity["id"]
            await self._make_request("DELETE", f"pages/{page_id}")
            deleted_ids.append(page_id)
            self.logger.info(f"🗑️ Trashed page: {entity.get('title', page_id)}")

        # Remove from tracking
        deleted_id_set = set(deleted_ids)
        self._pages = [p for p in self._pages if p["id"] not in deleted_id_set]

        return deleted_ids

    async def cleanup(self):
        """Comprehensive cleanup of ALL monke test pages.

        Searches for all pages containing monke test tokens (8-char hex prefixes)
        and archives them, not just the ones from the current session.

        Note: The "Monke Test Container" persists at workspace root (can't be archived via API).
        """
        self.logger.info("🧹 ============================================")
        self.logger.info("🧹 Starting comprehensive Notion cleanup")
        self.logger.info("🧹 ============================================")

        cleanup_stats = {"pages_trashed": 0, "errors": 0}

        try:
            # Ensure we have the parent page ID resolved
            if not self._parent_page_id:
                self.logger.info("🔍 Resolving parent page...")
                await self._resolve_parent_page()
                self.logger.info(f"✅ Parent page ID: {self._parent_page_id}")
            else:
                self.logger.info(
                    f"✅ Using existing parent page ID: {self._parent_page_id}"
                )

            # Clean up current session pages first
            if self._pages:
                self.logger.info(
                    f"🗑️ Step 1: Trashing {len(self._pages)} current session pages"
                )
                current_page_ids = [p["id"] for p in self._pages]
                self.logger.info(f"   Current session page IDs: {current_page_ids}")
                await self.delete_entities()
                cleanup_stats["pages_trashed"] += len(self._pages)
                self.logger.info(
                    f"✅ Step 1 complete: Trashed {len(self._pages)} current session pages"
                )
            else:
                self.logger.info("ℹ️  Step 1: No current session pages to trash")

            # Find and clean up ALL monke test pages (including orphans from failed runs)
            self.logger.info("🔍 Step 2: Searching for orphaned monke test pages...")
            orphaned_pages = await self._find_monke_test_pages()
            self.logger.info(f"🔍 Step 2: Found {len(orphaned_pages)} orphaned pages")

            if orphaned_pages:
                # Separate active pages from already-trashed pages
                active_orphans = [
                    p for p in orphaned_pages if not p.get("in_trash", False)
                ]
                already_trashed = [
                    p for p in orphaned_pages if p.get("in_trash", False)
                ]

                self.logger.info(
                    f"📊 Orphaned pages breakdown: "
                    f"total={len(orphaned_pages)}, "
                    f"active={len(active_orphans)}, "
                    f"already_trashed={len(already_trashed)}"
                )

                if already_trashed:
                    self.logger.info("ℹ️  Already-trashed orphaned pages (skipping):")
                    for page in already_trashed:
                        self.logger.info(
                            f"   - {page.get('title', page['id'])} [{page['id']}]"
                        )

                if active_orphans:
                    self.logger.info(
                        f"🗑️ Trashing {len(active_orphans)} active orphaned pages:"
                    )
                    for page in active_orphans:
                        try:
                            self.logger.info(
                                f"   🗑️ Trashing: {page.get('title', page['id'])} [{page['id']}]"
                            )
                            trashed_page = await self._make_request(
                                "DELETE", f"pages/{page['id']}"
                            )
                            cleanup_stats["pages_trashed"] += 1

                            # Verify the page is actually marked as trashed
                            is_trashed = trashed_page.get("in_trash", False)
                            is_archived = trashed_page.get("archived", False)
                            self.logger.info(
                                f"   ✅ Trashed: {page.get('title', page['id'])} "
                                f"- API returned: in_trash={is_trashed}, archived={is_archived}"
                            )

                            if not is_trashed:
                                self.logger.error(
                                    f"   ❌ WARNING: Orphaned page {page['id']} was 'trashed' "
                                    f"but API returned in_trash={is_trashed}!"
                                )
                        except Exception as e:
                            cleanup_stats["errors"] += 1
                            self.logger.warning(
                                f"   ⚠️ Failed to trash page {page['id']}: {e}"
                            )
                else:
                    self.logger.info("✅ No active orphaned pages to trash")
            else:
                self.logger.info("✅ No orphaned pages found")

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['pages_trashed']} pages trashed, "
                f"{cleanup_stats['errors']} errors"
            )

        except Exception as e:
            self.logger.error(f"❌ Error during cleanup: {e}")

        self.logger.info("✅ Notion cleanup complete")

    async def _find_monke_test_pages(self) -> List[Dict[str, Any]]:
        """Find all monke test pages in the workspace.

        Searches for pages with titles matching the monke test pattern:
        - 8-character hex token prefix (like "8a04af44 Knowledge Base Overview")
        - Located in "Monke Test Container" (if it exists)
        - Includes both active AND archived pages (we want to clean up everything)
        """
        self.logger.info("🔍 _find_monke_test_pages: Starting search")
        monke_pages = []

        # If no parent page ID, there are no monke test pages to clean up
        if not self._parent_page_id:
            self.logger.info(
                "ℹ️  _find_monke_test_pages: No Monke Test Container found, skipping search"
            )
            return monke_pages

        self.logger.info(
            f"🔍 _find_monke_test_pages: Searching for pages (parent={self._parent_page_id})"
        )

        try:
            # Search for all pages in the workspace (including archived)
            # NOTE: Notion search API does NOT return trashed pages by default!
            # We paginate using has_more/next_cursor to ensure we see all pages.
            base_search_payload = {
                "filter": {
                    "property": "object",
                    "value": "page",
                },
                "page_size": 100,
            }

            current_page_ids = {p["id"] for p in self._pages}
            self.logger.info(
                f"🔍 _find_monke_test_pages: Current session has {len(current_page_ids)} pages"
            )

            pages_checked = 0
            pages_in_container = 0
            pages_with_token = 0

            has_more = True
            next_cursor: Optional[str] = None

            while has_more:
                search_payload = dict(base_search_payload)
                if next_cursor:
                    search_payload["start_cursor"] = next_cursor

                self.logger.info(
                    f"🔍 _find_monke_test_pages: Making search request with payload: {search_payload}"
                )
                response = await self._make_request("POST", "search", search_payload)
                results = response.get("results", [])
                has_more = response.get("has_more", False)
                next_cursor = response.get("next_cursor")

                self.logger.info(
                    f"🔍 _find_monke_test_pages: Search page returned {len(results)} pages "
                    f"(has_more={has_more})"
                )

                for page in results:
                    pages_checked += 1
                    page_id = page.get("id", "unknown")

                    # Check if page is a child of the Monke Test Container
                    parent = page.get("parent", {})
                    parent_type = parent.get("type")
                    parent_page_id = parent.get("page_id")

                    if (
                        parent_type == "page_id"
                        and parent_page_id == self._parent_page_id
                    ):
                        pages_in_container += 1

                        # Extract title
                        title_prop = page.get("properties", {}).get("title", {})
                        title_content = title_prop.get("title", [])
                        if (
                            title_content
                            and isinstance(title_content, list)
                            and len(title_content) > 0
                        ):
                            title = title_content[0].get("text", {}).get("content", "")

                            # Check if starts with 8-char hex pattern
                            if len(title) >= 8:
                                prefix = title[:8].lower()
                                if all(c in "0123456789abcdef" for c in prefix):
                                    pages_with_token += 1

                                    # Skip if it's already in our current session pages
                                    if page["id"] not in current_page_ids:
                                        is_archived = page.get("archived", False)
                                        is_trashed = page.get("in_trash", False)

                                        monke_pages.append(
                                            {
                                                "id": page["id"],
                                                "title": title,
                                                "archived": is_archived,
                                                "in_trash": is_trashed,
                                            }
                                        )
                                        status = []
                                        if is_archived:
                                            status.append("archived")
                                        if is_trashed:
                                            status.append("trashed")
                                        status_str = (
                                            f" ({', '.join(status)})" if status else ""
                                        )
                                        self.logger.info(
                                            f"   ✅ Found orphaned monke page: {title}{status_str} [{page_id}]"
                                        )
                                    else:
                                        self.logger.debug(
                                            f"   ⏭️  Skipping current session page: {title} [{page_id}]"
                                        )

            self.logger.info(
                f"🔍 _find_monke_test_pages: Checked {pages_checked} pages, "
                f"{pages_in_container} in container, "
                f"{pages_with_token} with token pattern, "
                f"{len(monke_pages)} orphaned monke pages found"
            )

        except Exception as e:
            self.logger.warning(f"Error searching for monke test pages: {e}")

        return monke_pages
