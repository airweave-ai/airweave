"""Bitbucket-specific bongo implementation."""

import asyncio
import base64
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class BitbucketBongo(BaseBongo):
    """Bitbucket-specific bongo implementation.

    Creates, updates, and deletes test files via the real Bitbucket API.
    """

    connector_type = "bitbucket"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Bitbucket bongo.

        Args:
            credentials: Bitbucket credentials with username and app_password
            **kwargs: Additional configuration (e.g., entity_count, workspace, repo)
        """
        super().__init__(credentials)
        self.username = credentials["username"]
        self.app_password = credentials["app_password"]

        # Configuration from kwargs
        self.entity_count = kwargs.get('entity_count', 10)
        self.workspace = kwargs.get('workspace', self.username)  # Default to username
        self.repo_slug = kwargs.get('repo_slug', 'monke-test-repo')
        self.branch = kwargs.get('branch', 'main')
        self.llm_model = kwargs.get('llm_model', None)

        # Test data tracking
        self.test_files = []

        # Rate limiting (Bitbucket: 1000 requests per hour)
        self.last_request_time = 0
        self.rate_limit_delay = 0.5  # 0.5 second between requests

        # Logger
        self.logger = get_logger("bitbucket_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test files in Bitbucket."""
        self.logger.info(f"🥁 Creating {self.entity_count} test files in Bitbucket")
        entities = []

        # Ensure repository exists
        await self._ensure_test_repository()

        # Create files based on configuration
        from monke.generation.bitbucket import generate_bitbucket_artifact

        for i in range(self.entity_count):
            # Short unique token used in filename and content for verification
            token = str(uuid.uuid4())[:8]

            filename, content, file_type = await generate_bitbucket_artifact(
                self.llm_model, token
            )
            filepath = f"monke-test/{filename}-{token}.{file_type}"

            # Create file
            await self._create_test_file(filepath, content)

            entities.append({
                "type": "file",
                "path": filepath,
                "workspace": self.workspace,
                "repo": self.repo_slug,
                "file_type": file_type,
                "token": token,
                "expected_content": token,
            })

            self.logger.info(f"📄 Created test file: {filepath}")

            # Rate limiting
            if self.entity_count > 10:
                await asyncio.sleep(0.5)

        self.test_files = entities  # Store for later operations
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update test entities in Bitbucket."""
        self.logger.info("🥁 Updating test files in Bitbucket")
        updated_entities = []

        # Update a subset of files based on configuration
        from monke.generation.bitbucket import generate_bitbucket_artifact
        files_to_update = min(3, self.entity_count)  # Update max 3 files for any test size

        for i in range(files_to_update):
            if i < len(self.test_files):
                file_info = self.test_files[i]
                token = file_info.get("token") or str(uuid.uuid4())[:8]
                file_type = file_info.get("file_type", "py")

                # Generate new content with same token
                _, content, _ = await generate_bitbucket_artifact(
                    self.llm_model, token, is_update=True
                )

                # Update file
                await self._update_test_file(file_info["path"], content)

                updated_entities.append({
                    "type": "file",
                    "path": file_info["path"],
                    "workspace": self.workspace,
                    "repo": self.repo_slug,
                    "file_type": file_type,
                    "token": token,
                    "expected_content": token,
                    "updated": True,
                })

                self.logger.info(f"📝 Updated test file: {file_info['path']}")

                # Rate limiting
                if self.entity_count > 10:
                    await asyncio.sleep(0.5)

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all test entities from Bitbucket."""
        self.logger.info("🥁 Deleting all test files from Bitbucket")

        # Use the specific deletion method to delete all entities
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete specific entities from Bitbucket."""
        self.logger.info(f"🥁 Deleting {len(entities)} specific files from Bitbucket")

        deleted_paths = []

        for entity in entities:
            try:
                # Find the corresponding test file
                test_file = next((tf for tf in self.test_files if tf["path"] == entity.get("path")), None)

                if test_file:
                    await self._delete_test_file(test_file["path"])
                    deleted_paths.append(test_file["path"])
                    self.logger.info(f"🗑️ Deleted test file: {test_file['path']}")
                else:
                    self.logger.warning(f"⚠️ Could not find test file for entity: {entity.get('path')}")

                # Rate limiting
                if len(entities) > 10:
                    await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete entity {entity.get('path')}: {e}")

        # VERIFICATION: Check if files are actually deleted
        self.logger.info("🔍 VERIFYING: Checking if files are actually deleted from Bitbucket")
        for entity in entities:
            path = entity.get("path")
            if path and path in deleted_paths:
                is_deleted = await self._verify_file_deleted(path)
                if is_deleted:
                    self.logger.info(f"✅ File {path} confirmed deleted from Bitbucket")
                else:
                    self.logger.warning(f"⚠️ File {path} still exists in Bitbucket!")

        return deleted_paths

    async def cleanup(self):
        """Clean up any remaining test data."""
        self.logger.info("🧹 Cleaning up remaining test files in Bitbucket")

        # Delete all files in the test directory
        try:
            await self._delete_test_directory()
            self.logger.info("🧹 Deleted test directory from Bitbucket")
        except Exception as e:
            self.logger.warning(f"⚠️ Could not delete test directory: {e}")

    # Helper methods for Bitbucket API calls
    async def _ensure_test_repository(self):
        """Ensure the test repository exists."""
        await self._rate_limit()

        # Check if repo exists
        auth = base64.b64encode(f"{self.username}:{self.app_password}".encode()).decode()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.bitbucket.org/2.0/repositories/{self.workspace}/{self.repo_slug}",
                headers={
                    "Authorization": f"Basic {auth}",
                    "Accept": "application/json"
                }
            )

            if response.status_code == 404:
                # Create repository
                self.logger.info(f"📁 Creating test repository: {self.repo_slug}")
                response = await client.post(
                    f"https://api.bitbucket.org/2.0/repositories/{self.workspace}/{self.repo_slug}",
                    headers={
                        "Authorization": f"Basic {auth}",
                        "Accept": "application/json",
                        "Content-Type": "application/json"
                    },
                    json={
                        "scm": "git",
                        "is_private": True,
                        "description": "Temporary repository for Monke testing"
                    }
                )

                if response.status_code not in [200, 201]:
                    raise Exception(f"Failed to create repository: {response.status_code} - {response.text}")

            elif response.status_code == 200:
                self.logger.info(f"📁 Using existing repository: {self.repo_slug}")
            else:
                raise Exception(f"Failed to check repository: {response.status_code} - {response.text}")

    async def _create_test_file(self, filepath: str, content: str):
        """Create a test file via Bitbucket API."""
        await self._rate_limit()

        auth = base64.b64encode(f"{self.username}:{self.app_password}".encode()).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.bitbucket.org/2.0/repositories/{self.workspace}/{self.repo_slug}/src",
                headers={
                    "Authorization": f"Basic {auth}",
                    "Accept": "application/json"
                },
                data={
                    filepath: content,
                    "message": f"Add monke test file: {filepath}",
                    "branch": self.branch
                }
            )

            if response.status_code not in [200, 201]:
                raise Exception(f"Failed to create file: {response.status_code} - {response.text}")

            # Track created file
            self.created_entities.append({
                "path": filepath
            })

    async def _update_test_file(self, filepath: str, new_content: str):
        """Update a test file via Bitbucket API."""
        await self._rate_limit()

        auth = base64.b64encode(f"{self.username}:{self.app_password}".encode()).decode()

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.bitbucket.org/2.0/repositories/{self.workspace}/{self.repo_slug}/src",
                headers={
                    "Authorization": f"Basic {auth}",
                    "Accept": "application/json"
                },
                data={
                    filepath: new_content,
                    "message": f"Update monke test file: {filepath}",
                    "branch": self.branch
                }
            )

            if response.status_code not in [200, 201]:
                raise Exception(f"Failed to update file: {response.status_code} - {response.text}")

    async def _delete_test_file(self, filepath: str):
        """Delete a test file via Bitbucket API."""
        await self._rate_limit()

        auth = base64.b64encode(f"{self.username}:{self.app_password}".encode()).decode()

        # Bitbucket doesn't have a direct delete API, so we update with empty content
        # and a delete commit message
        async with httpx.AsyncClient() as client:
            # First, we need to get the file to delete it properly
            # We'll use the src endpoint with files parameter
            response = await client.post(
                f"https://api.bitbucket.org/2.0/repositories/{self.workspace}/{self.repo_slug}/src",
                headers={
                    "Authorization": f"Basic {auth}",
                    "Accept": "application/json"
                },
                data={
                    "files": filepath,
                    "message": f"Delete monke test file: {filepath}",
                    "branch": self.branch
                }
            )

            if response.status_code not in [200, 201, 204]:
                self.logger.warning(f"Could not delete file via API: {response.status_code}")

    async def _verify_file_deleted(self, filepath: str) -> bool:
        """Verify if a file is actually deleted from Bitbucket."""
        try:
            auth = base64.b64encode(f"{self.username}:{self.app_password}".encode()).decode()

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.bitbucket.org/2.0/repositories/{self.workspace}/{self.repo_slug}/src/{self.branch}/{filepath}",
                    headers={
                        "Authorization": f"Basic {auth}"
                    }
                )

                if response.status_code == 404:
                    # File not found - successfully deleted
                    return True
                elif response.status_code == 200:
                    # File still exists
                    return False
                else:
                    # Unexpected response
                    self.logger.warning(f"⚠️ Unexpected response checking {filepath}: {response.status_code}")
                    return False

        except Exception as e:
            self.logger.warning(f"⚠️ Error verifying file deletion for {filepath}: {e}")
            return False

    async def _delete_test_directory(self):
        """Delete the entire test directory."""
        # For Bitbucket, we would need to delete files individually
        # This is a simplified version
        self.logger.info("Cleaning up test directory...")

    async def _rate_limit(self):
        """Implement rate limiting for Bitbucket API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()
