"""OneNote bongo implementation.

Creates, updates, and deletes test entities via the real Microsoft Graph API.
"""

import asyncio
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.generation.onenote import generate_onenote_page
from monke.utils.logging import get_logger

GRAPH = "https://graph.microsoft.com/v1.0"


class OneNoteBongo(BaseBongo):
    """Bongo for OneNote that creates test entities for E2E testing.

    Key responsibilities:
    - Create test notebook, section, and pages
    - Embed verification tokens in page content
    - Update pages to test incremental sync
    - Delete pages to test deletion detection
    - Clean up all test data
    """

    connector_type = "onenote"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        super().__init__(credentials)
        self.access_token: str = credentials["access_token"]
        self.entity_count: int = int(kwargs.get("entity_count", 3))
        self.openai_model: str = kwargs.get("openai_model", "gpt-4.1-mini")
        self.rate_limit_delay = float(kwargs.get("rate_limit_delay_ms", 500)) / 1000.0
        self.logger = get_logger("onenote_bongo")

        # Track created resources for cleanup
        self._test_notebook_id: Optional[str] = None
        self._test_section_id: Optional[str] = None
        self._pages: List[Dict[str, Any]] = []
        self._last_req = 0.0

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test notebook, section, and pages in OneNote."""
        self.logger.info(
            f"🥁 Creating OneNote test structure with {self.entity_count} pages"
        )
        out: List[Dict[str, Any]] = []

        async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
            # Step 1: Create test notebook
            await self._pace()
            test_notebook_name = f"Monke Test Notebook {uuid.uuid4().hex[:8]}"
            self.logger.info(f"📓 Creating test notebook: {test_notebook_name}")

            nb_payload = {"displayName": test_notebook_name}
            r = await client.post(
                "/me/onenote/notebooks", headers=self._hdrs(), json=nb_payload
            )

            if r.status_code not in (200, 201):
                self.logger.error(f"Create notebook failed {r.status_code}: {r.text}")
                r.raise_for_status()

            notebook = r.json()
            self._test_notebook_id = notebook["id"]
            self.logger.info(f"✅ Created notebook: {self._test_notebook_id}")

            # Step 2: Create test section
            await self._pace()
            test_section_name = f"Monke Test Section {uuid.uuid4().hex[:8]}"
            self.logger.info(f"📂 Creating test section: {test_section_name}")

            section_payload = {"displayName": test_section_name}
            r = await client.post(
                f"/me/onenote/notebooks/{self._test_notebook_id}/sections",
                headers=self._hdrs(),
                json=section_payload,
            )

            if r.status_code not in (200, 201):
                self.logger.error(f"Create section failed {r.status_code}: {r.text}")
                r.raise_for_status()

            section = r.json()
            self._test_section_id = section["id"]
            self.logger.info(f"✅ Created section: {self._test_section_id}")

            # Step 3: Create test pages with embedded tokens
            tokens = [uuid.uuid4().hex[:8] for _ in range(self.entity_count)]

            for token in tokens:
                await self._pace()

                # Generate page content
                title, html_content = await generate_onenote_page(
                    self.openai_model, token
                )

                # Create page in section
                # OneNote API requires multipart/form-data with HTML
                page_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <title>{title}</title>
                </head>
                <body>
                    {html_content}
                </body>
                </html>
                """

                r = await client.post(
                    f"/me/onenote/sections/{self._test_section_id}/pages",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "text/html",
                    },
                    content=page_html,
                )

                if r.status_code not in (200, 201):
                    self.logger.error(f"Create page failed {r.status_code}: {r.text}")
                    r.raise_for_status()

                page = r.json()
                page_id = page["id"]

                ent = {
                    "type": "page",
                    "id": page_id,
                    "title": title,
                    "token": token,
                    "expected_content": token,
                }
                out.append(ent)
                self._pages.append(ent)
                self.created_entities.append({"id": page_id, "name": title})
                self.logger.info(f"📄 Created page with token: {token}")

                # Brief delay between page creations
                if self.entity_count > 10:
                    await asyncio.sleep(0.5)

        return out

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update pages by appending new content."""
        if not self._pages:
            return []

        self.logger.info(f"🥁 Updating {min(3, len(self._pages))} OneNote pages")
        updated = []

        async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
            for ent in self._pages[: min(3, len(self._pages))]:
                await self._pace()

                # Generate updated content with same token
                title, html_content = await generate_onenote_page(
                    self.openai_model, ent["token"], is_update=True
                )

                # Append content to existing page
                # OneNote PATCH API uses a special format
                patch_content = [
                    {
                        "target": "body",
                        "action": "append",
                        "content": f"<div>{html_content}</div>",
                    }
                ]

                r = await client.patch(
                    f"/me/onenote/pages/{ent['id']}/content",
                    headers=self._hdrs(),
                    json=patch_content,
                )

                if r.status_code in (200, 204):
                    updated.append({**ent, "updated": True})
                    self.logger.info(f"📝 Updated page for token: {ent['token']}")
                else:
                    self.logger.warning(
                        f"Failed to update page: {r.status_code} - {r.text[:200]}"
                    )

        return updated

    async def delete_entities(self) -> List[str]:
        """Delete all test pages."""
        return await self.delete_specific_entities(self._pages)

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific pages by ID."""
        self.logger.info(f"🥁 Deleting {len(entities)} OneNote pages")
        deleted: List[str] = []

        async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
            for ent in entities:
                try:
                    await self._pace()

                    page_id = ent.get("id")
                    if not page_id:
                        self.logger.warning(f"No page ID for entity, skipping: {ent}")
                        continue

                    # Delete page
                    r = await client.delete(
                        f"/me/onenote/pages/{page_id}", headers=self._hdrs()
                    )

                    if r.status_code == 204:
                        # Return the page ID (not token) for proper entity tracking
                        deleted.append(page_id)
                        self.logger.info(
                            f"✅ Deleted page: {ent.get('title', 'Unknown')[:50]}"
                        )
                    else:
                        self.logger.warning(
                            f"Delete failed for {page_id}: {r.status_code} - {r.text[:200]}"
                        )

                except Exception as e:
                    self.logger.warning(
                        f"Delete error for page {ent.get('id', 'unknown')}: {e}"
                    )

        return deleted

    async def cleanup(self):
        """Comprehensive cleanup of all test resources."""
        self.logger.info("🧹 Starting comprehensive OneNote cleanup")

        cleanup_stats = {
            "pages_deleted": 0,
            "sections_deleted": 0,
            "notebooks_deleted": 0,
            "errors": 0,
        }

        try:
            async with httpx.AsyncClient(base_url=GRAPH, timeout=30) as client:
                # Delete remaining pages
                if self._pages:
                    self.logger.info(f"🗑️ Cleaning up {len(self._pages)} pages")
                    deleted = await self.delete_specific_entities(self._pages)
                    cleanup_stats["pages_deleted"] += len(deleted)
                    self._pages.clear()

                # Delete test section
                if self._test_section_id:
                    await self._pace()
                    self.logger.info(
                        f"🗑️ Deleting test section: {self._test_section_id}"
                    )
                    r = await client.delete(
                        f"/me/onenote/sections/{self._test_section_id}",
                        headers=self._hdrs(),
                    )
                    if r.status_code == 204:
                        cleanup_stats["sections_deleted"] += 1
                        self.logger.info("✅ Deleted test section")
                    else:
                        cleanup_stats["errors"] += 1
                        self.logger.warning(f"Section delete failed: {r.status_code}")
                    self._test_section_id = None

                # Delete test notebook
                if self._test_notebook_id:
                    await self._pace()
                    self.logger.info(
                        f"🗑️ Deleting test notebook: {self._test_notebook_id}"
                    )
                    r = await client.delete(
                        f"/me/onenote/notebooks/{self._test_notebook_id}",
                        headers=self._hdrs(),
                    )
                    if r.status_code == 204:
                        cleanup_stats["notebooks_deleted"] += 1
                        self.logger.info("✅ Deleted test notebook")
                    else:
                        cleanup_stats["errors"] += 1
                        self.logger.warning(f"Notebook delete failed: {r.status_code}")
                    self._test_notebook_id = None

                # Search for and cleanup any orphaned test notebooks
                await self._cleanup_orphaned_notebooks(client, cleanup_stats)

            self.logger.info(
                f"🧹 Cleanup completed: {cleanup_stats['notebooks_deleted']} notebooks, "
                f"{cleanup_stats['sections_deleted']} sections, "
                f"{cleanup_stats['pages_deleted']} pages deleted, "
                f"{cleanup_stats['errors']} errors"
            )
        except Exception as e:
            self.logger.error(f"❌ Error during comprehensive cleanup: {e}")

    async def _cleanup_orphaned_notebooks(
        self, client: httpx.AsyncClient, stats: Dict[str, Any]
    ):
        """Find and delete orphaned test notebooks from previous runs.

        Note: OneNote's recycle bin can cause notebooks to appear in the list
        even after deletion. They return 404 when attempting to delete again.
        We silently skip these as they're already being cleaned up by OneNote.
        """
        try:
            await self._pace()
            r = await client.get("/me/onenote/notebooks", headers=self._hdrs())

            if r.status_code == 200:
                notebooks = r.json().get("value", [])

                # Find test notebooks that haven't been deleted yet
                test_notebooks = [
                    nb for nb in notebooks if "Monke Test" in nb.get("displayName", "")
                ]

                if test_notebooks:
                    self.logger.info(
                        f"🔍 Found {len(test_notebooks)} test notebooks in OneNote"
                    )

                    actually_deleted = 0
                    already_deleted = 0

                    for nb in test_notebooks:
                        try:
                            # Delete the notebook - OneNote will cascade delete all sections and pages
                            await self._pace()
                            del_r = await client.delete(
                                f"/me/onenote/notebooks/{nb['id']}",
                                headers=self._hdrs(),
                            )
                            if del_r.status_code == 204:
                                actually_deleted += 1
                                stats["notebooks_deleted"] += 1
                                self.logger.info(
                                    f"✅ Deleted notebook: {nb.get('displayName', 'Unknown')}"
                                )
                            elif del_r.status_code == 404:
                                # Notebook is in recycle bin or being deleted
                                already_deleted += 1
                            else:
                                stats["errors"] += 1
                                self.logger.warning(
                                    f"⚠️ Failed to delete notebook {nb['id']}: status {del_r.status_code}"
                                )
                        except httpx.HTTPStatusError as e:
                            if e.response.status_code == 404:
                                already_deleted += 1
                            else:
                                stats["errors"] += 1
                                self.logger.warning(
                                    f"⚠️ Failed to delete notebook {nb['id']}: {e}"
                                )
                        except Exception as e:
                            stats["errors"] += 1
                            self.logger.warning(
                                f"⚠️ Failed to delete notebook {nb['id']}: {e}"
                            )

                    if actually_deleted > 0:
                        self.logger.info(
                            f"✅ Deleted {actually_deleted} active notebooks"
                        )
                    if already_deleted > 0:
                        self.logger.info(
                            f"ℹ️ Skipped {already_deleted} notebooks already in recycle bin "
                            "(OneNote will permanently delete them soon)"
                        )
                else:
                    self.logger.info("✅ No test notebooks found")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not search for notebooks: {e}")

    def _hdrs(self) -> Dict[str, str]:
        """Get standard headers for Graph API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    async def _pace(self):
        """Rate limiting helper."""
        now = time.time()
        if (delta := now - self._last_req) < self.rate_limit_delay:
            await asyncio.sleep(self.rate_limit_delay - delta)
        self._last_req = time.time()
