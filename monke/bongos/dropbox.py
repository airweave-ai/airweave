"""Dropbox-specific bongo implementation."""

import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class DropboxBongo(BaseBongo):
    """Dropbox-specific bongo implementation.

    Creates, updates, and deletes test files via the real Dropbox API.
    """

    connector_type = "dropbox"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Dropbox bongo.

        Args:
            credentials: Dropbox credentials with access_token
            **kwargs: Additional configuration (e.g., entity_count, file_types)
        """
        super().__init__(credentials)
        self.access_token = credentials["access_token"]

        # Configuration from kwargs
        self.entity_count = int(kwargs.get("entity_count", 3))
        self.file_types = kwargs.get("file_types", ["markdown", "text", "json"])
        self.openai_model = kwargs.get("openai_model", "gpt-4.1-mini")

        # Test data tracking
        self.test_files = []
        self.test_folder_path = None

        # Rate limiting (Dropbox: varies by endpoint)
        self.last_request_time = 0
        self.rate_limit_delay = 0.5  # 0.5 second between requests (conservative)

        # Logger
        self.logger = get_logger("dropbox_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test files in Dropbox."""
        self.logger.info(f"🥁 Creating {self.entity_count} test files in Dropbox")
        entities = []

        # Create a test folder
        await self._ensure_test_folder()

        # Create files based on configuration
        from monke.generation.dropbox import generate_dropbox_artifact

        for i in range(self.entity_count):
            file_type = self.file_types[i % len(self.file_types)]
            # Short unique token used in filename and content for verification
            token = str(uuid.uuid4())[:8]

            title, content = await generate_dropbox_artifact(file_type, self.openai_model, token)
            filename = f"{title}-{token}.{self._get_file_extension(file_type)}"
            file_path = f"{self.test_folder_path}/{filename}"

            # Create file
            file_data = await self._create_test_file(file_path, content)

            entities.append(
                {
                    "type": "file",
                    "path": file_data["path_display"],
                    "id": file_data["id"],
                    "name": file_data["name"],
                    "file_type": file_type,
                    "token": token,
                    "expected_content": token,
                }
            )

            self.logger.info(f"📄 Created test file: {file_data['path_display']}")

            # Rate limiting
            if self.entity_count > 10:
                await asyncio.sleep(0.5)

        self.test_files = entities  # Store for later operations
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update test entities in Dropbox."""
        self.logger.info("🥁 Updating test files in Dropbox")
        updated_entities = []

        # Update a subset of files based on configuration
        from monke.generation.dropbox import generate_dropbox_artifact

        files_to_update = min(3, self.entity_count)  # Update max 3 files for any test size

        for i in range(files_to_update):
            if i < len(self.test_files):
                file_info = self.test_files[i]
                file_type = file_info.get("file_type", "text")
                token = file_info.get("token") or str(uuid.uuid4())[:8]

                # Generate new content with same token
                title, content = await generate_dropbox_artifact(
                    file_type, self.openai_model, token, is_update=True
                )

                # Update file content
                updated_file = await self._update_test_file(file_info["path"], content)

                updated_entities.append(
                    {
                        "type": "file",
                        "path": updated_file["path_display"],
                        "id": updated_file["id"],
                        "name": updated_file["name"],
                        "file_type": file_type,
                        "token": token,
                        "expected_content": token,
                        "updated": True,
                    }
                )

                self.logger.info(f"📝 Updated test file: {updated_file['path_display']}")

                # Rate limiting
                if self.entity_count > 10:
                    await asyncio.sleep(0.5)

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all test entities from Dropbox."""
        self.logger.info("🥁 Deleting all test files from Dropbox")

        # Use the specific deletion method to delete all entities
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete specific entities from Dropbox."""
        self.logger.info(f"🥁 Deleting {len(entities)} specific files from Dropbox")

        deleted_paths = []

        for entity in entities:
            try:
                # Find the corresponding test file
                test_file = next((tf for tf in self.test_files if tf["id"] == entity["id"]), None)

                if test_file:
                    await self._delete_test_file(test_file["path"])
                    deleted_paths.append(test_file["path"])
                    self.logger.info(f"🗑️ Deleted test file: {test_file['path']}")
                else:
                    self.logger.warning(
                        f"⚠️ Could not find test file for entity: {entity.get('id')}"
                    )

                # Rate limiting
                if len(entities) > 10:
                    await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete entity {entity.get('id')}: {e}")

        # VERIFICATION: Check if files are actually deleted
        self.logger.info("🔍 VERIFYING: Checking if files are actually deleted from Dropbox")
        for entity in entities:
            path = entity.get("path")
            if path and path in deleted_paths:
                is_deleted = await self._verify_file_deleted(path)
                if is_deleted:
                    self.logger.info(f"✅ File {path} confirmed deleted from Dropbox")
                else:
                    self.logger.warning(f"⚠️ File {path} still exists in Dropbox!")

        return deleted_paths

    async def cleanup(self):
        """Clean up any remaining test data."""
        self.logger.info("🧹 Cleaning up remaining test files in Dropbox")

        # Force delete the entire test folder
        if self.test_folder_path:
            try:
                await self._force_delete_folder(self.test_folder_path)
                self.logger.info(f"🧹 Deleted test folder: {self.test_folder_path}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete test folder: {e}")

    # Helper methods for Dropbox API calls
    async def _ensure_test_folder(self):
        """Ensure we have a test folder to work with."""
        await self._rate_limit()

        # Create a new test folder
        self.test_folder_path = f"/Monke-Test-{str(uuid.uuid4())[:8]}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.dropboxapi.com/2/files/create_folder_v2",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={"path": self.test_folder_path, "autorename": False},
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to create folder: {response.status_code} - {response.text}"
                )

            self.logger.info(f"📁 Created test folder: {self.test_folder_path}")

    async def _create_test_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Create a test file via Dropbox API."""
        await self._rate_limit()

        content_bytes = content.encode("utf-8")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://content.dropboxapi.com/2/files/upload",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Dropbox-API-Arg": f'{{"path": "{file_path}", "mode": "add", "autorename": true}}',
                    "Content-Type": "application/octet-stream",
                },
                content=content_bytes,
            )

            if response.status_code != 200:
                raise Exception(f"Failed to create file: {response.status_code} - {response.text}")

            result = response.json()

            # Track created file
            self.created_entities.append({"id": result["id"], "path": result["path_display"]})

            return result

    async def _update_test_file(self, file_path: str, new_content: str) -> Dict[str, Any]:
        """Update a test file via Dropbox API."""
        await self._rate_limit()

        content_bytes = new_content.encode("utf-8")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://content.dropboxapi.com/2/files/upload",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Dropbox-API-Arg": f'{{"path": "{file_path}", "mode": "overwrite"}}',
                    "Content-Type": "application/octet-stream",
                },
                content=content_bytes,
            )

            if response.status_code != 200:
                raise Exception(f"Failed to update file: {response.status_code} - {response.text}")

            return response.json()

    async def _delete_test_file(self, file_path: str):
        """Delete a test file via Dropbox API."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.dropboxapi.com/2/files/delete_v2",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={"path": file_path},
            )

            if response.status_code != 200:
                raise Exception(f"Failed to delete file: {response.status_code} - {response.text}")

    async def _verify_file_deleted(self, file_path: str) -> bool:
        """Verify if a file is actually deleted from Dropbox."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.dropboxapi.com/2/files/get_metadata",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"path": file_path, "include_deleted": True},
                )

                if response.status_code == 409:  # Path not found
                    # File not found - successfully deleted
                    return True
                elif response.status_code == 200:
                    # Check if file is deleted
                    data = response.json()
                    return data.get("is_deleted", False)
                else:
                    # Unexpected response
                    self.logger.warning(
                        f"⚠️ Unexpected response checking {file_path}: {response.status_code}"
                    )
                    return False

        except Exception as e:
            self.logger.warning(f"⚠️ Error verifying file deletion for {file_path}: {e}")
            return False

    async def _force_delete_folder(self, folder_path: str):
        """Force delete an entire folder."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.dropboxapi.com/2/files/delete_v2",
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"path": folder_path},
                )

                if response.status_code == 200:
                    self.logger.info(f"🧹 Force deleted folder: {folder_path}")
                else:
                    self.logger.warning(
                        f"⚠️ Force delete failed for {folder_path}: {response.status_code}"
                    )
        except Exception as e:
            self.logger.warning(f"Could not force delete {folder_path}: {e}")

    def _get_file_extension(self, file_type: str) -> str:
        """Get file extension for a given file type."""
        extensions = {"markdown": "md", "text": "txt", "json": "json", "yaml": "yml"}
        return extensions.get(file_type, "txt")

    async def _rate_limit(self):
        """Implement rate limiting for Dropbox API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()
