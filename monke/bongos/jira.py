"""Jira-specific bongo implementation."""

import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class JiraBongo(BaseBongo):
    """Jira-specific bongo implementation.

    Creates, updates, and deletes test issues via the real Jira API.
    """

    connector_type = "jira"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Jira bongo.

        Args:
            credentials: Jira credentials with access_token and cloud_id
            **kwargs: Additional configuration (e.g., entity_count)
        """
        super().__init__(credentials)
        self.access_token = credentials["access_token"]
        self.cloud_id = credentials.get("cloud_id", "")

        # Configuration from config file
        self.entity_count = int(kwargs.get("entity_count", 3))
        self.openai_model = kwargs.get("openai_model", "gpt-4.1-mini")

        # Test data tracking
        self.test_issues = []
        self.test_project_key = None
        self.valid_issue_types = []  # Store valid issue types for the project

        # Rate limiting (Jira: varies by endpoint)
        self.last_request_time = 0
        self.rate_limit_delay = 0.5  # 0.5 second between requests

        # Logger
        self.logger = get_logger("jira_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test issues in Jira."""
        self.logger.info(f"🥁 Creating {self.entity_count} test issues in Jira")
        entities = []

        # Get cloud ID if not provided
        if not self.cloud_id:
            self.cloud_id = await self._get_cloud_id()

        # Get or create a test project
        await self._ensure_test_project()

        # Determine which issue type to use (prefer standard types)
        issue_type_to_use = self._get_preferred_issue_type()

        # Create issues based on configuration
        from monke.generation.jira import generate_jira_artifact

        for i in range(self.entity_count):
            # Short unique token used in summary and description for verification
            token = str(uuid.uuid4())[:8]

            summary, description, _ = await generate_jira_artifact(
                self.openai_model, token
            )

            # Create issue with a valid issue type
            issue_data = await self._create_test_issue(
                self.test_project_key, summary, description, issue_type_to_use
            )

            entities.append(
                {
                    "type": "issue",
                    "id": issue_data["id"],
                    "key": issue_data["key"],
                    "project_key": self.test_project_key,
                    "summary": summary,
                    "token": token,
                    "expected_content": token,
                }
            )

            self.logger.info(f"🎫 Created test issue: {issue_data['key']}")

            # Rate limiting
            if self.entity_count > 10:
                await asyncio.sleep(0.5)

        self.test_issues = entities  # Store for later operations
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update test entities in Jira."""
        self.logger.info("🥁 Updating test issues in Jira")
        updated_entities = []

        # Update a subset of issues based on configuration
        from monke.generation.jira import generate_jira_artifact

        issues_to_update = min(3, self.entity_count)  # Update max 3 issues for any test size

        for i in range(issues_to_update):
            if i < len(self.test_issues):
                issue_info = self.test_issues[i]
                token = issue_info.get("token") or str(uuid.uuid4())[:8]

                # Generate new content with same token
                summary, description, _ = await generate_jira_artifact(
                    self.openai_model, token, is_update=True
                )

                # Update issue
                await self._update_test_issue(issue_info["id"], summary, description)

                updated_entities.append(
                    {
                        "type": "issue",
                        "id": issue_info["id"],
                        "key": issue_info["key"],
                        "project_key": self.test_project_key,
                        "summary": summary,
                        "token": token,
                        "expected_content": token,
                        "updated": True,
                    }
                )

                self.logger.info(f"📝 Updated test issue: {issue_info['key']}")

                # Rate limiting
                if self.entity_count > 10:
                    await asyncio.sleep(0.5)

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all test entities from Jira."""
        self.logger.info("🥁 Deleting all test issues from Jira")

        # Use the specific deletion method to delete all entities
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete specific entities from Jira.
        
        Returns:
            List of entity IDs that were successfully deleted
        """
        self.logger.info(f"🥁 Deleting {len(entities)} specific issues from Jira")

        deleted_ids = []

        for entity in entities:
            try:
                # Find the corresponding test issue
                test_issue = next((ti for ti in self.test_issues if ti["id"] == entity["id"]), None)

                if test_issue:
                    await self._delete_test_issue(test_issue["id"])
                    deleted_ids.append(test_issue["id"])  # Return ID, not key
                    self.logger.info(f"🗑️ Deleted test issue: {test_issue['key']}")
                else:
                    self.logger.warning(
                        f"⚠️ Could not find test issue for entity: {entity.get('id')}"
                    )

                # Rate limiting
                if len(entities) > 10:
                    await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete entity {entity.get('id')}: {e}")

        # VERIFICATION: Check if issues are actually deleted
        self.logger.info("🔍 VERIFYING: Checking if issues are actually deleted from Jira")
        for entity in entities:
            if entity.get("id") in deleted_ids:
                is_deleted = await self._verify_issue_deleted(entity["id"])
                if is_deleted:
                    self.logger.info(f"✅ Issue {entity['key']} confirmed deleted from Jira")
                else:
                    self.logger.warning(f"⚠️ Issue {entity['key']} still exists in Jira!")

        return deleted_ids

    async def cleanup(self):
        """Clean up any remaining test data."""
        self.logger.info("🧹 Cleaning up remaining test issues in Jira")

        # Force delete any remaining test issues
        for test_issue in self.test_issues:
            try:
                await self._force_delete_issue(test_issue["id"])
                self.logger.info(f"🧹 Force deleted issue: {test_issue['key']}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not force delete issue {test_issue['key']}: {e}")

    # Helper methods for Jira API calls
    async def _get_cloud_id(self) -> str:
        """Get the Jira cloud ID."""
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
                raise Exception("No accessible Jira resources found")

            return resources[0]["id"]

    async def _ensure_test_project(self):
        """Ensure we have a test project to work with."""
        await self._rate_limit()

        # For Jira, we'll use the first available project
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/project",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                raise Exception(f"Failed to get projects: {response.status_code} - {response.text}")

            projects = response.json()
            if not projects:
                raise Exception("No projects found in Jira")

            # Use the first project
            self.test_project_key = projects[0]["key"]
            self.logger.info(f"📁 Using project: {self.test_project_key}")

            # Fetch valid issue types for this project
            await self._fetch_valid_issue_types()

    async def _fetch_valid_issue_types(self):
        """Fetch valid issue types for the current project."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/project/{self.test_project_key}",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to get project details: {response.status_code} - {response.text}"
                )

            project_data = response.json()
            issue_types = project_data.get("issueTypes", [])
            
            if not issue_types:
                raise Exception(f"No issue types found for project {self.test_project_key}")

            # Store valid issue type names
            self.valid_issue_types = [it["name"] for it in issue_types]
            self.logger.info(
                f"✅ Found {len(self.valid_issue_types)} valid issue types: {', '.join(self.valid_issue_types)}"
            )

    def _get_preferred_issue_type(self) -> str:
        """Get a preferred issue type from the available types.
        
        Prefers standard types like Task, Bug, or Story.
        Falls back to the first available type.
        """
        if not self.valid_issue_types:
            raise Exception("No valid issue types available")

        # Preferred types in order
        preferred_types = ["Task", "Bug", "Story"]
        
        for preferred in preferred_types:
            if preferred in self.valid_issue_types:
                self.logger.info(f"🎯 Using issue type: {preferred}")
                return preferred
        
        # Fall back to first available type
        fallback_type = self.valid_issue_types[0]
        self.logger.info(f"🎯 Using fallback issue type: {fallback_type}")
        return fallback_type

    async def _create_test_issue(
        self, project_key: str, summary: str, description: str, issue_type: str = "Task"
    ) -> Dict[str, Any]:
        """Create a test issue via Jira API."""
        await self._rate_limit()

        issue_data = {
            "fields": {
                "project": {"key": project_key},
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": description}]}
                    ],
                },
                "issuetype": {"name": issue_type},
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/issue",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=issue_data,
            )

            if response.status_code != 201:
                raise Exception(f"Failed to create issue: {response.status_code} - {response.text}")

            result = response.json()

            # Track created issue
            self.created_entities.append({"id": result["id"], "key": result["key"]})

            return result

    async def _update_test_issue(
        self, issue_id: str, summary: str, description: str
    ) -> Dict[str, Any]:
        """Update a test issue via Jira API."""
        await self._rate_limit()

        update_data = {
            "fields": {
                "summary": summary,
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": description}]}
                    ],
                },
            }
        }

        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/issue/{issue_id}",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                json=update_data,
            )

            if response.status_code != 204:
                raise Exception(f"Failed to update issue: {response.status_code} - {response.text}")

            return {"id": issue_id, "status": "updated"}

    async def _delete_test_issue(self, issue_id: str):
        """Delete a test issue via Jira API."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/issue/{issue_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code != 204:
                raise Exception(f"Failed to delete issue: {response.status_code} - {response.text}")

    async def _verify_issue_deleted(self, issue_id: str) -> bool:
        """Verify if an issue is actually deleted from Jira."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.atlassian.com/ex/jira/{self.cloud_id}/rest/api/3/issue/{issue_id}",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )

                if response.status_code == 404:
                    # Issue not found - successfully deleted
                    return True
                elif response.status_code == 200:
                    # Issue still exists
                    return False
                else:
                    # Unexpected response
                    self.logger.warning(
                        f"⚠️ Unexpected response checking {issue_id}: {response.status_code}"
                    )
                    return False

        except Exception as e:
            self.logger.warning(f"⚠️ Error verifying issue deletion for {issue_id}: {e}")
            return False

    async def _force_delete_issue(self, issue_id: str):
        """Force delete an issue."""
        try:
            await self._delete_test_issue(issue_id)
        except Exception as e:
            self.logger.warning(f"Could not force delete {issue_id}: {e}")

    async def _rate_limit(self):
        """Implement rate limiting for Jira API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()
