"""ClickUp source implementation.

Retrieves data (read-only) from a user's ClickUp workspace:
    - Workspaces (Teams)
    - Spaces (within each workspace)
    - Folders (within each space)
    - Lists (within each folder)
    - Tasks (within each list)
    - Comments (within each task)

References:
    https://clickup.com/api/
    https://clickup.com/api/developer-portal/
"""

import logging
from typing import Any, AsyncGenerator, Dict, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities.clickup import (
    ClickUpCommentEntity,
    ClickUpFolderEntity,
    ClickUpListEntity,
    ClickUpSpaceEntity,
    ClickUpTaskEntity,
    ClickUpWorkspaceEntity,
)
from airweave.platform.sources._base import BaseSource

logger = logging.getLogger(__name__)


@source(
    "ClickUp", "clickup", AuthType.oauth2
)  # Using oauth2 as ClickUp doesn't support refresh tokens yet (as of March 2024)
class ClickUpSource(BaseSource):
    """ClickUp source implementation.

    This connector retrieves hierarchical data from ClickUp's REST API:
        - Workspaces (Teams)
        - Spaces (within each workspace)
        - Folders (within each space)
        - Lists (within each folder)
        - Tasks (within each list)
        - Comments (within each task)
    """

    BASE_URL = "https://api.clickup.com/api/v2/"

    @classmethod
    async def create(cls, access_token: str) -> "ClickUpSource":
        """Create a new Slack source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _make_request(
        self, client: httpx.AsyncClient, method: str, endpoint: str, params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make an authenticated HTTP request to the ClickUp API."""
        url = f"{self.BASE_URL}{endpoint}"
        print(f"Making request to: {url}")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        response = await client.request(method, url, headers=headers, params=params)
        print(f"Response: {response}")
        print(f"Response status: {response.status_code}")
        response.raise_for_status()
        return response.json()

    async def _fetch_workspaces(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[Dict[str, Any], None]:
        print("Generating Workspace entities")
        data = await self._make_request(client, "GET", "team")
        for workspace in data.get("teams", []):
            yield workspace

    async def _generate_space_entities(
        self, client: httpx.AsyncClient, workspace_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        print(f"Generating Space entities for workspace: {workspace_id}")
        data = await self._make_request(client, "GET", f"team/{workspace_id}/space")
        print(f"Space entities: {data}")
        for space in data.get("spaces", []):
            yield space

    async def _generate_folder_entities(
        self, client: httpx.AsyncClient, space_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        print(f"Generating Folder entities for space: {space_id}")
        data = await self._make_request(client, "GET", f"space/{space_id}/folder")
        print(f"Folder entities: {data}")
        for folder in data.get("folders", []):
            yield folder

    async def _generate_list_entities(
        self, client: httpx.AsyncClient, folder_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        print(f"Generating List entities for folder: {folder_id}")
        data = await self._make_request(client, "GET", f"folder/{folder_id}/list")
        print(f"List entities: {data}")
        for list_ in data.get("lists", []):
            yield list_

    async def _generate_task_entities(
        self, client: httpx.AsyncClient, list_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        print(f"Generating Task entities for list: {list_id}")
        page = 0
        while True:
            params = {"page": page, "per_page": 100, "subtasks": True, "include_closed": True}
            data = await self._make_request(client, "GET", f"list/{list_id}/task", params=params)
            tasks = data.get("tasks", [])
            if not tasks:
                break
            for task in tasks:
                yield task
            page += 1

    async def _generate_comment_entities(
        self, client: httpx.AsyncClient, task_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        print(f"Generating Comment entities for task: {task_id}")
        data = await self._make_request(client, "GET", f"task/{task_id}/comment")
        print(f"Comment entities: {data}")
        for comment in data.get("comments", []):
            yield comment

    async def generate_entities(self) -> AsyncGenerator[Any, None]:
        """Generate all ClickUp entities (Workspaces, Spaces, Folders, Lists, Tasks, Comments)."""
        print("Generating ClickUp entities")
        async with httpx.AsyncClient() as client:
            # Generate Workspace entities
            async for workspace in self._fetch_workspaces(client):
                print(f"Generating Workspace entity: {workspace}")
                workspace_entity = ClickUpWorkspaceEntity(
                    entity_id=workspace.get("id"),
                    workspace_id=workspace.get("id"),
                    name=workspace.get("name"),
                    color=workspace.get("color"),
                    avatar=workspace.get("avatar"),
                    members=workspace.get("members", []),
                )
                yield workspace_entity

                async for space in self._generate_space_entities(client, workspace["id"]):
                    space_entity = ClickUpSpaceEntity(
                        entity_id=space["id"],
                        space_id=space["id"],
                        name=space["name"],
                        private=space.get("private", False),
                        status=space.get("status", {}),
                        multiple_assignees=space.get("multiple_assignees", False),
                        features=space.get("features", {}),
                    )
                    yield space_entity

                    async for folder in self._generate_folder_entities(client, space["id"]):
                        folder_entity = ClickUpFolderEntity(
                            entity_id=folder["id"],
                            folder_id=folder["id"],
                            name=folder["name"],
                            hidden=folder.get("hidden", False),
                            space_id=space["id"],
                            task_count=folder.get("task_count"),
                        )
                        yield folder_entity

                        async for list_ in self._generate_list_entities(client, folder["id"]):
                            print(f"Generating List entity: {list_}")
                            list_entity = ClickUpListEntity(
                                entity_id=list_["id"],
                                list_id=list_["id"],
                                name=list_["name"],
                                folder_id=folder["id"],
                                space_id=space["id"],
                                content=list_.get("content", ""),
                                status=list_.get("status", {}),
                                priority=list_.get("priority", {}),
                                assignee=list_.get("assignee", None),
                                task_count=list_.get("task_count", 0),
                                due_date=list_.get("due_date", None),
                                start_date=list_.get("start_date", None),
                                folder_name=list_.get("folder").get("name"),
                                space_name=list_.get("space").get("name"),
                            )
                            yield list_entity

                            async for task in self._generate_task_entities(client, list_["id"]):
                                task_entity = ClickUpTaskEntity(
                                    entity_id=task["id"],
                                    task_id=task["id"],
                                    name=task["name"],
                                    status=task.get("status", {}),
                                    priority=task.get("priority"),
                                    assignees=task.get("assignees", []),
                                    tags=task.get("tags", []),
                                    due_date=task.get("due_date"),
                                    start_date=task.get("start_date"),
                                    time_estimate=task.get("time_estimate"),
                                    time_spent=task.get("time_spent"),
                                    custom_fields=task.get("custom_fields", []),
                                    list_id=list_["id"],
                                    folder_id=folder["id"],
                                    space_id=space["id"],
                                    url=task.get("url"),
                                    description=task.get("description", ""),
                                    parent=task.get("parent"),
                                )
                                yield task_entity

                                async for comment in self._generate_comment_entities(
                                    client, task["id"]
                                ):
                                    comment_entity = ClickUpCommentEntity(
                                        entity_id=comment["id"],
                                        comment_id=comment["id"],
                                        task_id=task["id"],
                                        user=comment.get("user", {}),
                                        text_content=comment.get("text_content", ""),
                                        resolved=comment.get("resolved", False),
                                        assignee=comment.get("assignee"),
                                        assigned_by=comment.get("assigned_by"),
                                        reactions=comment.get("reactions", []),
                                        date=comment["date"],
                                    )
                                    yield comment_entity
