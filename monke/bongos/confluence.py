"""Confluence-specific bongo implementation."""

import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class ConfluenceBongo(BaseBongo):
    """Confluence-specific bongo implementation.

    Creates, updates, and deletes test pages via the real Confluence API.
    """

    connector_type = "confluence"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Confluence bongo.

        Args:
            credentials: Confluence credentials with access_token and cloud_id
            **kwargs: Configuration from config file
        """
        super().__init__(credentials)
        self.access_token = credentials["access_token"]
        self.cloud_id = credentials.get("cloud_id", "")

        # Configuration from config file
        self.entity_count = int(kwargs.get("entity_count", 3))
        self.openai_model = kwargs.get("openai_model", "gpt-4.1-mini")

        # Test data tracking
        self.test_pages = []
        self.test_space_key = None

        # Rate limiting (Confluence: varies by endpoint)
        self.last_request_time = 0
        self.rate_limit_delay = 0.5  # 0.5 second between requests

        # Logger
        self.logger = get_logger("confluence_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test pages in Confluence."""
        self.logger.info(f"🥁 Creating {self.entity_count} test pages in Confluence")

        # Get cloud ID if not provided
        if not self.cloud_id:
            self.cloud_id = await self._get_cloud_id()

        # Get or create a test space
        await self._ensure_test_space()

        # Import generation function
        from monke.generation.confluence import generate_confluence_artifact

        async def create_single_page(index: int) -> Dict[str, Any]:
            """Create a single Confluence page."""
            # Short unique token used in title and content for verification
            token = str(uuid.uuid4())[:8]

            title, content = await generate_confluence_artifact(self.openai_model, token)
            unique_title = f"{title} [{token}]"

            # Create page
            page_data = await self._create_test_page(self.test_space_key, unique_title, content)

            self.logger.info(f"📄 Created test page: {page_data['title']}")

            return {
                "type": "page",
                "id": page_data["id"],
                "title": unique_title,  # Store the unique title
                "space_key": self.test_space_key,
                "token": token,
                "expected_content": token,
            }

        # Create all pages in parallel
        tasks = [create_single_page(i) for i in range(self.entity_count)]
        entities = await asyncio.gather(*tasks)

        self.test_pages = entities  # Store for later operations
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update test entities in Confluence."""
        self.logger.info("🥁 Updating test pages in Confluence")

        # Import generation function
        from monke.generation.confluence import generate_confluence_artifact

        pages_to_update = min(3, self.entity_count)  # Update max 3 pages for any test size

        async def update_single_page(page_info: Dict[str, Any]) -> Dict[str, Any]:
            """Update a single Confluence page."""
            token = page_info.get("token") or str(uuid.uuid4())[:8]

            # Generate new content with same token
            # Keep the original title to avoid conflicts in Confluence
            original_title = page_info.get("title")
            _, content = await generate_confluence_artifact(
                self.openai_model, token, is_update=True
            )

            # Update page with original title (Confluence doesn't allow duplicate titles in a space)
            await self._update_test_page(page_info["id"], original_title, content)

            self.logger.info(f"📝 Updated test page: {original_title}")

            return {
                "type": "page",
                "id": page_info["id"],
                "title": original_title,  # Keep original title
                "space_key": self.test_space_key,
                "token": token,
                "expected_content": token,
                "updated": True,
            }

        # Update pages in parallel
        pages_to_process = self.test_pages[:pages_to_update]
        tasks = [update_single_page(page_info) for page_info in pages_to_process]
        updated_entities = await asyncio.gather(*tasks)

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all test entities from Confluence."""
        self.logger.info("🥁 Deleting all test pages from Confluence")

        # Use the specific deletion method to delete all entities
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete specific entities from Confluence."""
        self.logger.info(f"🥁 Deleting {len(entities)} specific pages from Confluence")

        deleted_ids = []

        for entity in entities:
            try:
                # Find the corresponding test page
                test_page = next((tp for tp in self.test_pages if tp["id"] == entity["id"]), None)

                if test_page:
                    await self._delete_test_page(test_page["id"])
                    deleted_ids.append(test_page["id"])
                    self.logger.info(f"🗑️ Deleted test page: {test_page['title']}")
                else:
                    self.logger.warning(
                        f"⚠️ Could not find test page for entity: {entity.get('id')}"
                    )

                # Rate limiting
                if len(entities) > 10:
                    await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete entity {entity.get('id')}: {e}")

        # VERIFICATION: Check if pages are actually deleted
        self.logger.info("🔍 VERIFYING: Checking if pages are actually deleted from Confluence")
        for entity in entities:
            if entity["id"] in deleted_ids:
                is_deleted = await self._verify_page_deleted(entity["id"])
                if is_deleted:
                    self.logger.info(f"✅ Page {entity['id']} confirmed deleted from Confluence")
                else:
                    self.logger.warning(f"⚠️ Page {entity['id']} still exists in Confluence!")

        return deleted_ids

    async def cleanup(self):
        """Clean up any remaining test data."""
        self.logger.info("🧹 Cleaning up remaining test pages in Confluence")

        # Force delete any remaining test pages
        for test_page in self.test_pages:
            try:
                await self._force_delete_page(test_page["id"])
                self.logger.info(f"🧹 Force deleted page: {test_page['title']}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not force delete page {test_page['title']}: {e}")

    # Helper methods for Confluence API calls
    async def _get_cloud_id(self) -> str:
        """Get the Confluence cloud ID."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.atlassian.com/oauth/token/accessible-resources",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                raise Exception(f"Failed to get cloud ID: {response.status_code} - {response.text}")

            resources = response.json()
            if not resources:
                raise Exception("No accessible Confluence resources found")

            return resources[0]["id"]

    async def _ensure_test_space(self):
        """Ensure we have a test space to work with."""
        await self._rate_limit()

        # For Confluence, we'll use the first available space
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/wiki/api/v2/spaces",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                },
                params={"limit": 10},
            )

            if response.status_code != 200:
                raise Exception(f"Failed to get spaces: {response.status_code} - {response.text}")

            data = response.json()
            spaces = data.get("results", [])
            if not spaces:
                raise Exception("No spaces found in Confluence")

            # Use the first space
            self.test_space_key = spaces[0]["key"]
            self.test_space_id = spaces[0]["id"]
            self.logger.info(f"📁 Using space: {self.test_space_key}")

    async def _create_test_page(self, space_key: str, title: str, content: str) -> Dict[str, Any]:
        """Create a test page via Confluence API."""
        await self._rate_limit()

        page_data = {
            "spaceId": self.test_space_id,
            "status": "current",
            "title": title,
            "body": {"representation": "storage", "value": f"<p>{content}</p>"},
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/wiki/api/v2/pages",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=page_data,
            )

            if response.status_code != 200:
                raise Exception(f"Failed to create page: {response.status_code} - {response.text}")

            result = response.json()

            # Track created page
            self.created_entities.append({"id": result["id"], "title": result["title"]})

            return result

    async def _update_test_page(self, page_id: str, title: str, content: str) -> Dict[str, Any]:
        """Update a test page via Confluence API."""
        await self._rate_limit()

        # First get the current page version
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/wiki/api/v2/pages/{page_id}",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                raise Exception(f"Failed to get page: {response.status_code} - {response.text}")

            page = response.json()
            current_version = page["version"]["number"]

            # Update the page
            update_data = {
                "id": page_id,
                "status": "current",
                "title": title,
                "body": {"representation": "storage", "value": f"<p>{content}</p>"},
                "version": {"number": current_version + 1, "message": "Updated by Monke test"},
            }

            response = await client.put(
                f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/wiki/api/v2/pages/{page_id}",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=update_data,
            )

            if response.status_code != 200:
                raise Exception(f"Failed to update page: {response.status_code} - {response.text}")

            return response.json()

    async def _delete_test_page(self, page_id: str):
        """Delete a test page via Confluence API."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/wiki/api/v2/pages/{page_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code != 204:
                raise Exception(f"Failed to delete page: {response.status_code} - {response.text}")

    async def _verify_page_deleted(self, page_id: str) -> bool:
        """Verify if a page is actually deleted from Confluence."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.atlassian.com/ex/confluence/{self.cloud_id}/wiki/api/v2/pages/{page_id}",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )

                if response.status_code == 404:
                    # Page not found - successfully deleted
                    return True
                elif response.status_code == 200:
                    # Check if page is trashed
                    page = response.json()
                    return page.get("status") == "trashed"
                else:
                    # Unexpected response
                    self.logger.warning(
                        f"⚠️ Unexpected response checking {page_id}: {response.status_code}"
                    )
                    return False

        except Exception as e:
            self.logger.warning(f"⚠️ Error verifying page deletion for {page_id}: {e}")
            return False

    async def _force_delete_page(self, page_id: str):
        """Force delete a page."""
        try:
            await self._delete_test_page(page_id)
        except Exception as e:
            self.logger.warning(f"Could not force delete {page_id}: {e}")

    async def _rate_limit(self):
        """Implement rate limiting for Confluence API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()
