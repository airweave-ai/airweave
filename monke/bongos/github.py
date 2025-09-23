"""GitHub-specific bongo implementation."""

import asyncio
import base64
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger
from monke.auth.keyvault_adapter import get_keyvault_adapter


class GitHubBongo(BaseBongo):
    """GitHub-specific bongo implementation.

    Creates, updates, and deletes test data via the real GitHub API.
    """

    connector_type = "github"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the GitHub bongo.

        Args:
            credentials: GitHub credentials with personal_access_token, repo_name
            **kwargs: Additional configuration (e.g., entity_count, file_types)
        """
        super().__init__(credentials)
        # Resolve GitHub PAT from env or Azure Key Vault (fallback to provided credential)
        adapter = get_keyvault_adapter()
        self.personal_access_token = adapter.get_env_or_secret(
            "GITHUB_PERSONAL_ACCESS_TOKEN", credentials.get("personal_access_token")
        )
        if not self.personal_access_token:
            raise RuntimeError(
                "GitHub PAT not found. Set GITHUB_PERSONAL_ACCESS_TOKEN in env or Key Vault."
            )
        self.repo_name = credentials["repo_name"]

        # Configuration from kwargs
        self.entity_count = kwargs.get("entity_count", 10)
        self.file_types = kwargs.get("file_types", ["markdown", "python", "json"])
        self.openai_model = kwargs.get("openai_model", "gpt-5")
        self.branch = kwargs.get("branch", "main")

        # Test data tracking
        self.test_files = []

        # Rate limiting (GitHub: 5000 requests/hour for authenticated users)
        self.last_request_time = 0
        self.rate_limit_delay = 1.0  # 1 second between requests (conservative)

        # Logger
        self.logger = get_logger("github_bongo")

        # Sanity check: repo should be in owner/repo format
        if "/" not in self.repo_name:
            self.logger.warning(
                "repo_name should be in 'owner/repo' format; got '%s'",
                self.repo_name,
            )

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test files in GitHub repository."""
        self.logger.info(f"🥁 Creating {self.entity_count} test entities in GitHub")
        entities = []

        # Create files based on configuration
        from monke.generation.github import generate_github_artifact, slugify

        for i in range(self.entity_count):
            file_type = self.file_types[i % len(self.file_types)]
            # Short unique token used in filename and body for verification
            token = str(uuid.uuid4())[:8]

            title, content = await generate_github_artifact(
                file_type, self.openai_model, token
            )
            slug = slugify(title)[:40] or f"monke-{token}"
            filename = f"{slug}-{token}.{self._get_file_extension(file_type)}"

            test_file = await self._create_test_file(filename, content)
            entities.append(
                {
                    "type": "file",
                    "path": test_file["content"]["path"],
                    "sha": test_file["content"]["sha"],
                    "file_type": file_type,
                    "title": title,
                    "token": token,
                    "expected_content": token,
                }
            )

            self.logger.info(f"📄 Created test file: {test_file['content']['path']}")

            # Rate limiting for larger test sizes
            if self.entity_count > 10:
                await asyncio.sleep(0.5)

        self.test_files = entities  # Store for later operations
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update test entities in GitHub."""
        self.logger.info("🥁 Updating test entities in GitHub")
        updated_entities = []

        # Update a subset of files based on configuration
        from monke.generation.github import generate_github_artifact

        files_to_update = min(
            3, self.entity_count
        )  # Update max 3 files for any test size

        for i in range(files_to_update):
            if i < len(self.test_files):
                file_info = self.test_files[i]
                file_type = file_info.get("file_type", "markdown")
                token = file_info.get("token") or str(uuid.uuid4())[:8]
                # Regenerate content with same token to indicate continuity
                title, updated_content = await generate_github_artifact(
                    file_type, self.openai_model, token
                )

                updated_file = await self._update_test_file(
                    file_info["path"], file_info["sha"], updated_content
                )
                updated_entities.append(
                    {
                        "type": "file",
                        "path": updated_file["content"]["path"],
                        "sha": updated_file["content"]["sha"],
                        "file_type": file_type,
                        "title": title,
                        "token": token,
                        "expected_content": token,
                    }
                )

                self.logger.info(
                    f"📝 Updated test file: {updated_file['content']['path']}"
                )

                # Rate limiting for larger test sizes
                if self.entity_count > 10:
                    await asyncio.sleep(0.5)

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all test entities from GitHub."""
        self.logger.info("🥁 Deleting all test entities from GitHub")

        # Use the specific deletion method to delete all entities
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(
        self, entities: List[Dict[str, Any]]
    ) -> List[str]:
        """Delete specific entities from GitHub."""
        self.logger.info(f"🥁 Deleting {len(entities)} specific entities from GitHub")

        deleted_paths = []

        for entity in entities:
            try:
                # Find the corresponding test file
                test_file = next(
                    (tf for tf in self.test_files if tf["path"] == entity["path"]), None
                )

                if test_file:
                    await self._delete_test_file(test_file["path"], test_file["sha"])
                    deleted_paths.append(test_file["path"])
                    self.logger.info(f"🗑️ Deleted test file: {test_file['path']}")
                else:
                    self.logger.warning(
                        f"⚠️ Could not find test file for entity: {entity['path']}"
                    )

                # Rate limiting for larger test sizes
                if len(entities) > 10:
                    await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete entity {entity['path']}: {e}")

        # VERIFICATION: Check if files are actually deleted from GitHub
        self.logger.info(
            "🔍 VERIFYING: Checking if files are actually deleted from GitHub"
        )
        for entity in entities:
            if entity["path"] in deleted_paths:
                is_deleted = await self._verify_file_deleted(entity["path"])
                if is_deleted:
                    self.logger.info(
                        f"✅ File {entity['path']} confirmed deleted from GitHub"
                    )
                else:
                    self.logger.warning(
                        f"⚠️ File {entity['path']} still exists in GitHub!"
                    )

        return deleted_paths

    async def cleanup(self):
        """Clean up any remaining test data."""
        self.logger.info("🧹 Cleaning up remaining test data in GitHub")

        # Force delete any remaining test files
        for test_file in self.test_files:
            try:
                await self._force_delete_file(test_file["path"])
                self.logger.info(f"🧹 Force deleted file: {test_file['path']}")
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Could not force delete file {test_file['path']}: {e}"
                )

    # Helper methods for GitHub API calls
    async def _create_test_file(self, filename: str, content: str) -> Dict[str, Any]:
        """Create a test file via GitHub API."""
        await self._rate_limit()

        self.logger.info(f"🔍 Creating file: {filename}")
        self.logger.info(f"   Repository: {self.repo_name}")
        self.logger.info(f"   Token: {self.personal_access_token[:8]}...")

        async with httpx.AsyncClient() as client:
            # First check if file exists to get current SHA
            try:
                self.logger.info("🔍 Checking if file exists...")
                check_response = await client.get(
                    f"https://api.github.com/repos/{self.repo_name}/contents/{filename}",
                    headers={
                        "Authorization": f"token {self.personal_access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    params={"ref": self.branch},
                )

                self.logger.info(
                    f"   Check response status: {check_response.status_code}"
                )

                if check_response.status_code == 200:
                    # File exists, get current SHA for update
                    file_info = check_response.json()
                    current_sha = file_info["sha"]
                    message = f"Update monke test file: {filename}"
                    self.logger.info(f"   File exists, SHA: {current_sha}")
                else:
                    # File doesn't exist, create new
                    current_sha = None
                    message = f"Add monke test file: {filename}"
                    self.logger.info("   File doesn't exist, will create new")

            except Exception as e:
                # Assume file doesn't exist
                current_sha = None
                message = f"Add monke test file: {filename}"
                self.logger.warning(f"   Exception during check: {e}")

            # Prepare request payload
            payload = {
                "message": message,
                "content": base64.b64encode(content.encode()).decode(),
                "branch": self.branch,
            }

            # Add SHA if updating existing file
            if current_sha:
                payload["sha"] = current_sha

            self.logger.info(f"   Creating file with payload: {payload}")
            self.logger.info(
                f"   URL: https://api.github.com/repos/{self.repo_name}/contents/{filename}"
            )

            response = await client.put(
                f"https://api.github.com/repos/{self.repo_name}/contents/{filename}",
                headers={
                    "Authorization": f"token {self.personal_access_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            self.logger.info(f"   Response status: {response.status_code}")
            self.logger.info(f"   Response text: {response.text}")

            if response.status_code not in [200, 201]:  # 200 = updated, 201 = created
                raise Exception(
                    f"Failed to create/update file: {response.status_code} - {response.text}"
                )

            result = response.json()
            self.test_files.append({"path": filename, "sha": result["content"]["sha"]})

            return result

    async def _update_test_file(
        self, filename: str, current_sha: str, new_content: str
    ) -> Dict[str, Any]:
        """Update a test file via GitHub API."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"https://api.github.com/repos/{self.repo_name}/contents/{filename}",
                headers={
                    "Authorization": f"token {self.personal_access_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "Content-Type": "application/json",
                },
                json={
                    "message": f"Update monke test file: {filename}",
                    "content": base64.b64encode(new_content.encode()).decode(),
                    "sha": current_sha,
                    "branch": self.branch,
                },
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to update file: {response.status_code} - {response.text}"
                )

            result = response.json()

            # Update the stored SHA
            for test_file in self.test_files:
                if test_file["path"] == filename:
                    test_file["sha"] = result["content"]["sha"]
                    break

            return result

    async def _delete_test_file(self, filename: str, sha: str):
        """Delete a test file via GitHub API."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            # Use request method for DELETE with body
            import json

            response = await client.request(
                "DELETE",
                f"https://api.github.com/repos/{self.repo_name}/contents/{filename}",
                headers={
                    "Authorization": f"token {self.personal_access_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "Content-Type": "application/json",
                },
                data=json.dumps(
                    {
                        "message": f"Remove monke test file: {filename}",
                        "sha": sha,
                        "branch": self.branch,
                    }
                ),
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to delete file: {response.status_code} - {response.text}"
                )

    async def _verify_file_deleted(self, filename: str) -> bool:
        """Verify if a file is actually deleted from GitHub."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.github.com/repos/{self.repo_name}/contents/{filename}",
                    headers={
                        "Authorization": f"token {self.personal_access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    params={"ref": self.branch},
                )

                if response.status_code == 404:
                    # File not found - successfully deleted
                    return True
                elif response.status_code == 200:
                    # File still exists
                    return False
                else:
                    # Unexpected response
                    self.logger.warning(
                        f"⚠️ Unexpected response checking {filename}: {response.status_code}"
                    )
                    return False

        except Exception as e:
            self.logger.warning(f"⚠️ Error verifying file deletion for {filename}: {e}")
            return False

    async def _force_delete_file(self, filename: str):
        """Force delete a file (try to get current SHA first)."""
        try:
            # Get current file info
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.github.com/repos/{self.repo_name}/contents/{filename}",
                    headers={
                        "Authorization": f"token {self.personal_access_token}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    params={"ref": self.branch},
                )

                if response.status_code == 200:
                    file_info = response.json()
                    # Use the request method for DELETE with body
                    import json

                    delete_response = await client.request(
                        "DELETE",
                        f"https://api.github.com/repos/{self.repo_name}/contents/{filename}",
                        headers={
                            "Authorization": f"token {self.personal_access_token}",
                            "Accept": "application/vnd.github.v3+json",
                            "Content-Type": "application/json",
                        },
                        data=json.dumps(
                            {
                                "message": f"Force delete monke test file: {filename}",
                                "sha": file_info["sha"],
                                "branch": "main",
                            }
                        ),
                    )

                    if delete_response.status_code == 200:
                        self.logger.info(f"🧹 Force deleted file: {filename}")
                    else:
                        self.logger.warning(
                            f"⚠️ Force delete failed for {filename}: {delete_response.status_code}"
                        )
                else:
                    # File might already be deleted
                    pass
        except Exception as e:
            # If we can't delete it, just log the warning
            self.logger.warning(f"Could not force delete {filename}: {e}")

    def _generate_updated_content(self, filename: str, file_num: int) -> str:
        """Generate updated content for a test file."""
        timestamp = str(int(time.time()))
        file_ext = filename.split(".")[-1] if "." in filename else "txt"

        if file_ext in ["md", "markdown"]:
            return f"""# Monke Test File {file_num} - UPDATED

This is an updated test file created by the monke framework to verify GitHub sync functionality.

## Test Content (Updated)
- File number: {file_num}
- Type: {file_ext}
- Status: UPDATED
- Updated at: {timestamp}

## Purpose
This file has been updated to test the update functionality of the monke framework.

## Changes Made
- Updated title and content
- Added new sections
- Enhanced test data
- Added timestamp

## Verification
This update should be detected by Airweave and synced to Qdrant for verification.

## New Features
- Update detection testing
- Content replacement verification
- Qdrant sync validation
"""
        elif file_ext in ["py", "python"]:
            return f'''"""Monke Test File {file_num} - UPDATED

A Python file for testing GitHub sync with updated code content.
"""

def monke_test_function_{file_num}_updated():
    """Updated test function for monke verification."""
    return f"Hello from UPDATED Monke Test File {file_num}!"


class MonkeTestClass{file_num}Updated:
    """Updated test class for monke verification."""

    def __init__(self):
        self.name = f"Monke Test Class {file_num} - UPDATED"
        self.purpose = "Testing GitHub sync update functionality"
        self.status = "UPDATED"
        self.timestamp = "{timestamp}"

    def get_info(self):
        """Get updated test class information."""
        return f"{{self.name}}: {{self.purpose}} - {{self.status}}"


if __name__ == "__main__":
    print(monke_test_function_{file_num}_updated())
    test_obj = MonkeTestClass{file_num}Updated()
    print(test_obj.get_info())
'''
        elif file_ext == "json":
            return f'''{{
  "test_file": "monke_test_{file_num}.json",
  "purpose": "Testing GitHub sync with UPDATED JSON content",
  "status": "UPDATED",
  "content": {{
    "title": "Monke Test File {file_num} - UPDATED",
    "description": "An UPDATED JSON file for testing GitHub sync functionality",
    "file_number": {file_num},
    "file_type": "{file_ext}",
    "update_timestamp": "{timestamp}",
    "features": [
      "JSON structure testing",
      "Content extraction",
      "Qdrant indexing",
      "Search verification",
      "UPDATE DETECTION"
    ],
    "metadata": {{
      "created_by": "monke",
      "test_type": "github_sync",
      "original_timestamp": "1755180320",
      "updated_timestamp": "{timestamp}",
      "status": "UPDATED"
    }}
  }}
}}'''
        else:  # yaml, txt, etc.
            return f"""Monke Test File {file_num} - UPDATED

This is an UPDATED test file created by the monke framework to verify GitHub sync functionality.

File Details:
- File number: {file_num}
- Type: {file_ext}
- Status: UPDATED
- Updated at: {timestamp}

Purpose:
This file has been UPDATED to test the update functionality of the monke framework.

Changes Made:
- Updated title and content
- Added new sections
- Enhanced test data
- Added update timestamp

Features:
- Content extraction testing
- Qdrant indexing verification
- Search relevance scoring
- UPDATE DETECTION testing

This is an updated plain text file for testing various content types and ensuring proper sync functionality.
"""

    def _get_file_extension(self, file_type: str) -> str:
        """Get file extension for a given file type."""
        extensions = {
            "markdown": "md",
            "python": "py",
            "json": "json",
            "yaml": "yml",
            "txt": "txt",
            "md": "md",
            "py": "py",
            "js": "js",
        }
        return extensions.get(file_type, "txt")

    def _generate_file_content(
        self, file_type: str, file_num: int, random_suffix: str
    ) -> str:
        """Generate content for a test file based on type."""
        timestamp = str(int(time.time()))

        if file_type in ["markdown", "md"]:
            return f"""# Monke Test File {file_num}

This is test file {file_num} created by the monke framework to verify GitHub sync functionality.

## Test Content
- File number: {file_num}
- Type: {file_type}
- Random suffix: {random_suffix}
- Created by: monke
- Timestamp: {timestamp}

## Purpose
This file will be synced to Airweave and indexed in Qdrant for end-to-end testing.

## Features
- Content extraction testing
- Qdrant indexing verification
- Search relevance scoring
- Update and deletion testing
"""
        elif file_type in ["python", "py"]:
            return f'''"""Monke Test File {file_num}

A Python file for testing GitHub sync with code content.
"""

def monke_test_function_{file_num}():
    """Test function for monke verification."""
    return f"Hello from Monke Test File {file_num}!"


class MonkeTestClass{file_num}:
    """Test class for monke verification."""

    def __init__(self):
        self.name = f"Monke Test Class {file_num}"
        self.purpose = "Testing GitHub sync functionality"
        self.file_type = "{file_type}"
        self.random_suffix = "{random_suffix}"
        self.timestamp = "{timestamp}"

    def get_info(self):
        """Get test class information."""
        return f"{{self.name}}: {{self.purpose}}"


if __name__ == "__main__":
    print(monke_test_function_{file_num}())
    test_obj = MonkeTestClass{file_num}()
    print(test_obj.get_info())
'''
        elif file_type == "json":
            return f'''{{
  "test_file": "monke_test_{file_num}.json",
  "purpose": "Testing GitHub sync with JSON content",
  "content": {{
    "title": "Monke Test File {file_num}",
    "description": "A JSON file for testing GitHub sync functionality",
    "file_number": {file_num},
    "file_type": "{file_type}",
    "random_suffix": "{random_suffix}",
    "features": [
      "JSON structure testing",
      "Content extraction",
      "Qdrant indexing",
      "Search verification"
    ],
    "metadata": {{
      "created_by": "monke",
      "test_type": "github_sync",
      "timestamp": "{timestamp}"
    }}
  }}
}}'''
        elif file_type == "yaml":
            return f"""# Monke Test File {file_num}
test_file: monke_test_{file_num}.yml
purpose: Testing GitHub sync with YAML content
content:
  title: Monke Test File {file_num}
  description: A YAML file for testing GitHub sync functionality
  file_number: {file_num}
  file_type: {file_type}
  features:
    - YAML structure testing
    - Content extraction
    - Qdrant indexing
    - Search verification
  metadata:
    created_by: monke
    test_type: github_sync
    timestamp: {timestamp}
"""
        else:  # txt, js, etc.
            return f"""Monke Test File {file_num}

This is test file {file_num} created by the monke framework to verify GitHub sync functionality.

File Details:
- File number: {file_num}
- Type: {file_type}
- Created by: monke
- Timestamp: {timestamp}

Purpose:
This file will be synced to Airweave and indexed in Qdrant for end-to-end testing.

Features:
- Content extraction testing
- Qdrant indexing verification
- Search relevance scoring
- Update and deletion testing

This is a plain text file for testing various content types and ensuring proper sync functionality.
"""

    async def _rate_limit(self):
        """Implement rate limiting for GitHub API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()
