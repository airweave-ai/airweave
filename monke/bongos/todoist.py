"""Todoist-specific bongo implementation."""

import asyncio
import time
import uuid
from typing import Any, Dict, List

import httpx
from monke.bongos.base_bongo import BaseBongo
from monke.utils.logging import get_logger


class TodoistBongo(BaseBongo):
    """Todoist-specific bongo implementation.

    Creates, updates, and deletes test tasks via the real Todoist API.
    """

    connector_type = "todoist"

    def __init__(self, credentials: Dict[str, Any], **kwargs):
        """Initialize the Todoist bongo.

        Args:
            credentials: Todoist credentials with access_token
            **kwargs: Additional configuration (e.g., entity_count)
        """
        super().__init__(credentials)
        self.access_token = credentials["access_token"]

        # Configuration from config file
        self.entity_count = int(kwargs.get("entity_count", 3))
        self.openai_model = kwargs.get("openai_model", "gpt-4.1-mini")

        # Test data tracking
        self.test_tasks = []
        self.test_project_id = None

        # Rate limiting (Todoist: 450 requests per 15 minutes)
        self.last_request_time = 0
        self.rate_limit_delay = 0.5  # 0.5 second between requests

        # Logger
        self.logger = get_logger("todoist_bongo")

    async def create_entities(self) -> List[Dict[str, Any]]:
        """Create test tasks in Todoist."""
        self.logger.info(f"🥁 Creating {self.entity_count} test tasks in Todoist")
        entities = []

        # Create a test project
        await self._ensure_test_project()

        # Create tasks based on configuration
        from monke.generation.todoist import generate_todoist_artifact

        for i in range(self.entity_count):
            # Short unique token used in content for verification
            token = str(uuid.uuid4())[:8]

            content, description, priority = await generate_todoist_artifact(
                self.openai_model, token
            )

            # Create task
            task_data = await self._create_test_task(
                self.test_project_id, content, description, priority
            )

            entities.append(
                {
                    "type": "task",
                    "id": task_data["id"],
                    "project_id": self.test_project_id,
                    "content": content,
                    "token": token,
                    "expected_content": token,
                }
            )

            self.logger.info(f"✅ Created test task: {task_data['content']}")

            # Rate limiting
            if self.entity_count > 10:
                await asyncio.sleep(0.5)

        self.test_tasks = entities  # Store for later operations
        return entities

    async def update_entities(self) -> List[Dict[str, Any]]:
        """Update test entities in Todoist."""
        self.logger.info("🥁 Updating test tasks in Todoist")
        updated_entities = []

        # Update a subset of tasks based on configuration
        from monke.generation.todoist import generate_todoist_artifact

        tasks_to_update = min(3, self.entity_count)  # Update max 3 tasks for any test size

        for i in range(tasks_to_update):
            if i < len(self.test_tasks):
                task_info = self.test_tasks[i]
                token = task_info.get("token") or str(uuid.uuid4())[:8]

                # Generate new content with same token
                content, description, priority = await generate_todoist_artifact(
                    self.openai_model, token, is_update=True
                )

                # Update task
                await self._update_test_task(task_info["id"], content, description)

                updated_entities.append(
                    {
                        "type": "task",
                        "id": task_info["id"],
                        "project_id": self.test_project_id,
                        "content": content,
                        "token": token,
                        "expected_content": token,
                        "updated": True,
                    }
                )

                self.logger.info(f"📝 Updated test task: {content}")

                # Rate limiting
                if self.entity_count > 10:
                    await asyncio.sleep(0.5)

        return updated_entities

    async def delete_entities(self) -> List[str]:
        """Delete all test entities from Todoist."""
        self.logger.info("🥁 Deleting all test tasks from Todoist")

        # Use the specific deletion method to delete all entities
        return await self.delete_specific_entities(self.created_entities)

    async def delete_specific_entities(self, entities: List[Dict[str, Any]]) -> List[str]:
        """Delete specific entities from Todoist."""
        self.logger.info(f"🥁 Deleting {len(entities)} specific tasks from Todoist")

        deleted_ids = []

        for entity in entities:
            try:
                # Find the corresponding test task
                test_task = next((tt for tt in self.test_tasks if tt["id"] == entity["id"]), None)

                if test_task:
                    await self._delete_test_task(test_task["id"])
                    deleted_ids.append(test_task["id"])
                    self.logger.info(f"🗑️ Deleted test task: {test_task['content']}")
                else:
                    self.logger.warning(
                        f"⚠️ Could not find test task for entity: {entity.get('id')}"
                    )

                # Rate limiting
                if len(entities) > 10:
                    await asyncio.sleep(0.5)

            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete entity {entity.get('id')}: {e}")

        # VERIFICATION: Check if tasks are actually deleted
        self.logger.info("🔍 VERIFYING: Checking if tasks are actually deleted from Todoist")
        for entity in entities:
            if entity["id"] in deleted_ids:
                is_deleted = await self._verify_task_deleted(entity["id"])
                if is_deleted:
                    self.logger.info(f"✅ Task {entity['id']} confirmed deleted from Todoist")
                else:
                    self.logger.warning(f"⚠️ Task {entity['id']} still exists in Todoist!")

        return deleted_ids

    async def cleanup(self):
        """Clean up any remaining test data."""
        self.logger.info("🧹 Cleaning up remaining test tasks in Todoist")

        # Delete the test project
        if self.test_project_id:
            try:
                await self._delete_test_project(self.test_project_id)
                self.logger.info(f"🧹 Deleted test project: {self.test_project_id}")
            except Exception as e:
                self.logger.warning(f"⚠️ Could not delete test project: {e}")

    # Helper methods for Todoist API calls
    async def _ensure_test_project(self):
        """Ensure we have a test project to work with."""
        await self._rate_limit()

        # Create a new test project
        project_name = f"Monke Test Project - {str(uuid.uuid4())[:8]}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.todoist.com/api/v1/projects",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json={"name": project_name, "color": "red"},
            )

            if response.status_code != 200:
                raise Exception(
                    f"Failed to create project: {response.status_code} - {response.text}"
                )

            result = response.json()
            self.test_project_id = result["id"]
            self.logger.info(f"📁 Created test project: {project_name}")

    async def _create_test_task(
        self, project_id: str, content: str, description: str, priority: int = 1
    ) -> Dict[str, Any]:
        """Create a test task via Todoist API."""
        await self._rate_limit()

        task_data = {
            "content": content,
            "description": description,
            "project_id": project_id,
            "priority": priority,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.todoist.com/api/v1/tasks",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json=task_data,
            )

            if response.status_code != 200:
                raise Exception(f"Failed to create task: {response.status_code} - {response.text}")

            result = response.json()

            # Track created task
            self.created_entities.append({"id": result["id"], "content": result["content"]})

            return result

    async def _update_test_task(self, task_id: str, content: str, description: str):
        """Update a test task via Todoist API."""
        await self._rate_limit()

        update_data = {"content": content, "description": description}

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.todoist.com/api/v1/tasks/{task_id}",
                headers={
                    "Authorization": f"Bearer {self.access_token}",
                    "Content-Type": "application/json",
                },
                json=update_data,
            )

            if response.status_code != 200:
                raise Exception(f"Failed to update task: {response.status_code} - {response.text}")

    async def _delete_test_task(self, task_id: str):
        """Delete a test task via Todoist API."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"https://api.todoist.com/api/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code != 204:
                raise Exception(f"Failed to delete task: {response.status_code} - {response.text}")

    async def _verify_task_deleted(self, task_id: str) -> bool:
        """Verify if a task is actually deleted from Todoist."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.todoist.com/api/v1/tasks/{task_id}",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                )

                if response.status_code == 404:
                    # Task not found - successfully deleted
                    return True
                elif response.status_code == 200:
                    # Task still exists
                    return False
                else:
                    # Unexpected response
                    self.logger.warning(
                        f"⚠️ Unexpected response checking {task_id}: {response.status_code}"
                    )
                    return False

        except Exception as e:
            self.logger.warning(f"⚠️ Error verifying task deletion for {task_id}: {e}")
            return False

    async def _delete_test_project(self, project_id: str):
        """Delete the test project."""
        await self._rate_limit()

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"https://api.todoist.com/api/v1/projects/{project_id}",
                headers={"Authorization": f"Bearer {self.access_token}"},
            )

            if response.status_code != 204:
                raise Exception(
                    f"Failed to delete project: {response.status_code} - {response.text}"
                )

    async def _rate_limit(self):
        """Implement rate limiting for Todoist API."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()
