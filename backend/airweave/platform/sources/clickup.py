"""ClickUp source implementation for Airweave platform."""

from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs.auth import ClickUpAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.clickup import (
    ClickUpCommentEntity,
    ClickUpFolderEntity,
    ClickUpListEntity,
    ClickUpSpaceEntity,
    ClickUpTaskEntity,
    ClickUpWorkspaceEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    name="ClickUp",
    short_name="clickup",
    auth_type=AuthType.oauth2,
    auth_config_class="ClickUpAuthConfig",
    config_class="ClickUpConfig",
    labels=["Project Management"],
)
class ClickUpSource(BaseSource):
    """ClickUp source connector integrates with the ClickUp REST API to extract project data.

    Connects to your ClickUp workspaces.

    This connector retrieves hierarchical data from ClickUp's REST API:
    - Workspaces (Teams)
    - Spaces (within each workspace)
    - Folders (within each space)
    - Lists (within each folder)
    - Tasks (within each list)
    - Comments (within each task)

    """

    # ClickUp API constants
    BASE_URL = "https://api.clickup.com/api/v2"
    REQUESTS_PER_MINUTE = 100  # ClickUp rate limit
    
    def __init__(self):
        """Initialize the ClickUpSource."""
        super().__init__()

    @classmethod
    async def create(
        cls, credentials: ClickUpAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "ClickUpSource":
        """Create instance of the ClickUp source with authentication token and config.

        Args:
            credentials: ClickUp auth configuration containing access token
            config: Optional configuration parameters

        Returns:
            Configured ClickUpSource instance
        """
        instance = cls()
        instance.access_token = credentials.access_token
        
        # Store config values as instance attributes
        if config:
            # Add any ClickUp-specific config handling here
            pass
        
        return instance

    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=2, max=10), 
        reraise=True
    )
    async def _make_request(
        self, 
        client: httpx.AsyncClient, 
        endpoint: str, 
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated request to ClickUp API.

        Args:
            client: HTTP client to use for the request
            endpoint: API endpoint (without base URL)
            params: Optional query parameters

        Returns:
            JSON response from ClickUp API

        Raises:
            Exception: If request fails after retries
        """
        url = f"{self.BASE_URL}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        self.logger.debug(f"Making request to ClickUp API: {endpoint}")
        
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        
        return response.json()

    async def _get_workspaces(self, client: httpx.AsyncClient) -> List[Dict[str, Any]]:
        """Fetch all accessible workspaces (teams) from ClickUp.

        Args:
            client: HTTP client for API requests

        Returns:
            List of workspace data from ClickUp API
        """
        self.logger.info("Fetching workspaces from ClickUp")
        response = await self._make_request(client, "/team")
        return response.get("teams", [])

    async def _get_spaces(
        self, client: httpx.AsyncClient, workspace_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch all spaces within a workspace.

        Args:
            client: HTTP client for API requests
            workspace_id: ID of the workspace to fetch spaces from

        Returns:
            List of space data from ClickUp API
        """
        self.logger.debug(f"Fetching spaces for workspace {workspace_id}")
        response = await self._make_request(client, f"/team/{workspace_id}/space")
        return response.get("spaces", [])

    async def _get_folders(
        self, client: httpx.AsyncClient, space_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch all folders within a space.

        Args:
            client: HTTP client for API requests
            space_id: ID of the space to fetch folders from

        Returns:
            List of folder data from ClickUp API
        """
        self.logger.debug(f"Fetching folders for space {space_id}")
        response = await self._make_request(client, f"/space/{space_id}/folder")
        return response.get("folders", [])

    async def _get_lists(
        self, client: httpx.AsyncClient, folder_id: Optional[str] = None, space_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all lists within a folder or space.

        Args:
            client: HTTP client for API requests
            folder_id: ID of the folder to fetch lists from (if any)
            space_id: ID of the space to fetch lists from (for folderless lists)

        Returns:
            List of list data from ClickUp API
        """
        if folder_id:
            self.logger.debug(f"Fetching lists for folder {folder_id}")
            endpoint = f"/folder/{folder_id}/list"
        elif space_id:
            self.logger.debug(f"Fetching folderless lists for space {space_id}")
            endpoint = f"/space/{space_id}/list"
        else:
            raise ValueError("Either folder_id or space_id must be provided")
            
        response = await self._make_request(client, endpoint)
        return response.get("lists", [])

    async def _get_tasks(
        self, client: httpx.AsyncClient, list_id: str, page: int = 0
    ) -> Dict[str, Any]:
        """Fetch tasks from a specific list with pagination.

        Args:
            client: HTTP client for API requests
            list_id: ID of the list to fetch tasks from
            page: Page number for pagination

        Returns:
            Task data with pagination info from ClickUp API
        """
        params = {
            "archived": "false",
            "page": page,
            "order_by": "created",
            "reverse": "true",
            "include_closed": "true"
        }
        
        self.logger.debug(f"Fetching tasks for list {list_id}, page {page}")
        response = await self._make_request(client, f"/list/{list_id}/task", params)
        return response

    async def _get_task_comments(
        self, client: httpx.AsyncClient, task_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch all comments for a specific task.

        Args:
            client: HTTP client for API requests
            task_id: ID of the task to fetch comments from

        Returns:
            List of comment data from ClickUp API
        """
        self.logger.debug(f"Fetching comments for task {task_id}")
        response = await self._make_request(client, f"/task/{task_id}/comment")
        return response.get("comments", [])

    async def sync(self) -> AsyncGenerator[Any, None]:
        """Main sync method that orchestrates the hierarchical data fetch.

        Yields entities in the following order:
        1. Workspaces
        2. Spaces (within each workspace)
        3. Folders (within each space)
        4. Lists (within each folder + folderless lists)
        5. Tasks (within each list)
        6. Comments (within each task)

        Yields:
            ClickUp entities in hierarchical order
        """
        self.logger.info("Starting ClickUp sync")
        
        async with httpx.AsyncClient() as client:
            # 1. Fetch and yield workspaces
            workspaces = await self._get_workspaces(client)
            workspace_map = {}
            
            for workspace_data in workspaces:
                workspace_entity = self._create_workspace_entity(workspace_data)
                workspace_map[workspace_data["id"]] = workspace_data
                yield workspace_entity

            # 2. Fetch and yield spaces for each workspace
            space_map = {}
            for workspace_id, workspace_data in workspace_map.items():
                spaces = await self._get_spaces(client, workspace_id)
                
                for space_data in spaces:
                    space_entity = self._create_space_entity(space_data, workspace_data)
                    space_map[space_data["id"]] = {
                        "space_data": space_data,
                        "workspace_data": workspace_data
                    }
                    yield space_entity

            # 3. Fetch and yield folders for each space
            folder_map = {}
            for space_id, space_info in space_map.items():
                space_data = space_info["space_data"]
                workspace_data = space_info["workspace_data"]
                
                folders = await self._get_folders(client, space_id)
                
                for folder_data in folders:
                    folder_entity = self._create_folder_entity(folder_data, space_data, workspace_data)
                    folder_map[folder_data["id"]] = {
                        "folder_data": folder_data,
                        "space_data": space_data,
                        "workspace_data": workspace_data
                    }
                    yield folder_entity

            # 4. Fetch and yield lists for each folder + folderless lists
            list_map = {}
            
            # Lists within folders
            for folder_id, folder_info in folder_map.items():
                folder_data = folder_info["folder_data"]
                space_data = folder_info["space_data"]
                workspace_data = folder_info["workspace_data"]
                
                lists = await self._get_lists(client, folder_id=folder_id)
                
                for list_data in lists:
                    list_entity = self._create_list_entity(
                        list_data, folder_data, space_data, workspace_data
                    )
                    list_map[list_data["id"]] = {
                        "list_data": list_data,
                        "folder_data": folder_data,
                        "space_data": space_data,
                        "workspace_data": workspace_data
                    }
                    yield list_entity

            # Folderless lists (directly in spaces)
            for space_id, space_info in space_map.items():
                space_data = space_info["space_data"]
                workspace_data = space_info["workspace_data"]
                
                folderless_lists = await self._get_lists(client, space_id=space_id)
                
                for list_data in folderless_lists:
                    # Skip lists we already processed (they were in folders)
                    if list_data["id"] not in list_map:
                        list_entity = self._create_list_entity(
                            list_data, None, space_data, workspace_data
                        )
                        list_map[list_data["id"]] = {
                            "list_data": list_data,
                            "folder_data": None,
                            "space_data": space_data,
                            "workspace_data": workspace_data
                        }
                        yield list_entity

            # 5. Fetch and yield tasks for each list
            task_map = {}
            for list_id, list_info in list_map.items():
                list_data = list_info["list_data"]
                folder_data = list_info["folder_data"]
                space_data = list_info["space_data"]
                workspace_data = list_info["workspace_data"]
                
                # Handle pagination for tasks
                page = 0
                while True:
                    task_response = await self._get_tasks(client, list_id, page)
                    tasks = task_response.get("tasks", [])
                    
                    if not tasks:
                        break
                        
                    for task_data in tasks:
                        task_entity = self._create_task_entity(
                            task_data, list_data, folder_data, space_data, workspace_data
                        )
                        task_map[task_data["id"]] = {
                            "task_data": task_data,
                            "list_data": list_data,
                            "folder_data": folder_data,
                            "space_data": space_data,
                            "workspace_data": workspace_data
                        }
                        yield task_entity
                    
                    # Check if there are more pages
                    if not task_response.get("last_page", True):
                        page += 1
                    else:
                        break

            # 6. Fetch and yield comments for each task
            for task_id, task_info in task_map.items():
                task_data = task_info["task_data"]
                list_data = task_info["list_data"]
                space_data = task_info["space_data"]
                workspace_data = task_info["workspace_data"]
                
                comments = await self._get_task_comments(client, task_id)
                
                for comment_data in comments:
                    comment_entity = self._create_comment_entity(
                        comment_data, task_data, list_data, space_data, workspace_data
                    )
                    yield comment_entity

        self.logger.info("ClickUp sync completed")

    def _create_workspace_entity(self, workspace_data: Dict[str, Any]) -> ClickUpWorkspaceEntity:
        """Create a ClickUpWorkspaceEntity from ClickUp API data.

        Args:
            workspace_data: Raw workspace data from ClickUp API

        Returns:
            Configured ClickUpWorkspaceEntity
        """
        return ClickUpWorkspaceEntity(
            breadcrumbs=[Breadcrumb(name=workspace_data.get("name", ""), entity_id=workspace_data["id"])],
            clickup_id=workspace_data["id"],
            name=workspace_data.get("name", ""),
            color=workspace_data.get("color"),
            avatar=workspace_data.get("avatar"),
            members=workspace_data.get("members", [])
        )

    def _create_space_entity(
        self, space_data: Dict[str, Any], workspace_data: Dict[str, Any]
    ) -> ClickUpSpaceEntity:
        """Create a ClickUpSpaceEntity from ClickUp API data.

        Args:
            space_data: Raw space data from ClickUp API
            workspace_data: Parent workspace data

        Returns:
            Configured ClickUpSpaceEntity
        """
        return ClickUpSpaceEntity(
            breadcrumbs=[
                Breadcrumb(name=workspace_data.get("name", ""), entity_id=workspace_data["id"]),
                Breadcrumb(name=space_data.get("name", ""), entity_id=space_data["id"])
            ],
            clickup_id=space_data["id"],
            workspace_id=workspace_data["id"],
            workspace_name=workspace_data.get("name", ""),
            name=space_data.get("name", ""),
            color=space_data.get("color"),
            private=space_data.get("private", False),
            avatar=space_data.get("avatar"),
            multiple_assignees=space_data.get("multiple_assignees", False),
            features=space_data.get("features", {}),
            members=space_data.get("members", [])
        )

    def _create_folder_entity(
        self, 
        folder_data: Dict[str, Any], 
        space_data: Dict[str, Any], 
        workspace_data: Dict[str, Any]
    ) -> ClickUpFolderEntity:
        """Create a ClickUpFolderEntity from ClickUp API data.

        Args:
            folder_data: Raw folder data from ClickUp API
            space_data: Parent space data
            workspace_data: Parent workspace data

        Returns:
            Configured ClickUpFolderEntity
        """
        return ClickUpFolderEntity(
            breadcrumbs=[
                Breadcrumb(name=workspace_data.get("name", ""), entity_id=workspace_data["id"]),
                Breadcrumb(name=space_data.get("name", ""), entity_id=space_data["id"]),
                Breadcrumb(name=folder_data.get("name", ""), entity_id=folder_data["id"])
            ],
            clickup_id=folder_data["id"],
            space_id=space_data["id"],
            space_name=space_data.get("name", ""),
            workspace_id=workspace_data["id"],
            name=folder_data.get("name", ""),
            orderindex=folder_data.get("orderindex", 0),
            override_statuses=folder_data.get("override_statuses", False),
            hidden=folder_data.get("hidden", False),
            statuses=folder_data.get("statuses", [])
        )

    def _create_list_entity(
        self,
        list_data: Dict[str, Any],
        folder_data: Optional[Dict[str, Any]],
        space_data: Dict[str, Any],
        workspace_data: Dict[str, Any]
    ) -> ClickUpListEntity:
        """Create a ClickUpListEntity from ClickUp API data.

        Args:
            list_data: Raw list data from ClickUp API
            folder_data: Parent folder data (None for folderless lists)
            space_data: Parent space data
            workspace_data: Parent workspace data

        Returns:
            Configured ClickUpListEntity
        """
        breadcrumbs = [
            Breadcrumb(name=workspace_data.get("name", ""), entity_id=workspace_data["id"]),
            Breadcrumb(name=space_data.get("name", ""), entity_id=space_data["id"])
        ]
        
        if folder_data:
            breadcrumbs.append(
                Breadcrumb(name=folder_data.get("name", ""), entity_id=folder_data["id"])
            )
            
        breadcrumbs.append(
            Breadcrumb(name=list_data.get("name", ""), entity_id=list_data["id"])
        )

        return ClickUpListEntity(
            breadcrumbs=breadcrumbs,
            clickup_id=list_data["id"],
            folder_id=folder_data["id"] if folder_data else None,
            folder_name=folder_data.get("name") if folder_data else None,
            space_id=space_data["id"],
            space_name=space_data.get("name", ""),
            workspace_id=workspace_data["id"],
            name=list_data.get("name", ""),
            content=list_data.get("content"),
            orderindex=list_data.get("orderindex", 0),
            priority=list_data.get("priority"),
            assignee=list_data.get("assignee"),
            task_count=list_data.get("task_count"),
            due_date=list_data.get("due_date"),
            due_date_time=list_data.get("due_date_time", False),
            start_date=list_data.get("start_date"),
            start_date_time=list_data.get("start_date_time", False),
            archived=list_data.get("archived", False),
            statuses=list_data.get("statuses", [])
        )

    def _create_task_entity(
        self,
        task_data: Dict[str, Any],
        list_data: Dict[str, Any],
        folder_data: Optional[Dict[str, Any]],
        space_data: Dict[str, Any],
        workspace_data: Dict[str, Any]
    ) -> ClickUpTaskEntity:
        """Create a ClickUpTaskEntity from ClickUp API data.

        Args:
            task_data: Raw task data from ClickUp API
            list_data: Parent list data
            folder_data: Parent folder data (None for folderless lists)
            space_data: Parent space data
            workspace_data: Parent workspace data

        Returns:
            Configured ClickUpTaskEntity
        """
        from datetime import datetime
        
        breadcrumbs = [
            Breadcrumb(name=workspace_data.get("name", ""), entity_id=workspace_data["id"]),
            Breadcrumb(name=space_data.get("name", ""), entity_id=space_data["id"])
        ]
        
        if folder_data:
            breadcrumbs.append(
                Breadcrumb(name=folder_data.get("name", ""), entity_id=folder_data["id"])
            )
            
        breadcrumbs.extend([
            Breadcrumb(name=list_data.get("name", ""), entity_id=list_data["id"]),
            Breadcrumb(name=task_data.get("name", ""), entity_id=task_data["id"])
        ])

        # Handle datetime fields
        date_created = None
        if task_data.get("date_created"):
            try:
                date_created = datetime.fromtimestamp(int(task_data["date_created"]) / 1000)
            except (ValueError, TypeError):
                pass

        date_updated = None
        if task_data.get("date_updated"):
            try:
                date_updated = datetime.fromtimestamp(int(task_data["date_updated"]) / 1000)
            except (ValueError, TypeError):
                pass

        date_closed = None
        if task_data.get("date_closed"):
            try:
                date_closed = datetime.fromtimestamp(int(task_data["date_closed"]) / 1000)
            except (ValueError, TypeError):
                pass

        return ClickUpTaskEntity(
            breadcrumbs=breadcrumbs,
            clickup_id=task_data["id"],
            custom_id=task_data.get("custom_id"),
            list_id=list_data["id"],
            list_name=list_data.get("name", ""),
            folder_id=folder_data["id"] if folder_data else None,
            folder_name=folder_data.get("name") if folder_data else None,
            space_id=space_data["id"],
            space_name=space_data.get("name", ""),
            workspace_id=workspace_data["id"],
            name=task_data.get("name", ""),
            description=task_data.get("description"),
            text_content=task_data.get("text_content"),
            status=task_data.get("status"),
            priority=task_data.get("priority"),
            assignees=task_data.get("assignees", []),
            watchers=task_data.get("watchers", []),
            creator=task_data.get("creator"),
            date_created=date_created,
            date_updated=date_updated,
            date_closed=date_closed,
            due_date=task_data.get("due_date"),
            start_date=task_data.get("start_date"),
            time_estimate=task_data.get("time_estimate"),
            time_spent=task_data.get("time_spent"),
            orderindex=task_data.get("orderindex", ""),
            archived=task_data.get("archived", False),
            custom_fields=task_data.get("custom_fields", []),
            tags=task_data.get("tags", []),
            parent=task_data.get("parent"),
            dependencies=task_data.get("dependencies", []),
            linked_tasks=task_data.get("linked_tasks", []),
            url=task_data.get("url")
        )

    def _create_comment_entity(
        self,
        comment_data: Dict[str, Any],
        task_data: Dict[str, Any],
        list_data: Dict[str, Any],
        space_data: Dict[str, Any],
        workspace_data: Dict[str, Any]
    ) -> ClickUpCommentEntity:
        """Create a ClickUpCommentEntity from ClickUp API data.

        Args:
            comment_data: Raw comment data from ClickUp API
            task_data: Parent task data
            list_data: Parent list data
            space_data: Parent space data
            workspace_data: Parent workspace data

        Returns:
            Configured ClickUpCommentEntity
        """
        from datetime import datetime
        
        breadcrumbs = [
            Breadcrumb(name=workspace_data.get("name", ""), entity_id=workspace_data["id"]),
            Breadcrumb(name=space_data.get("name", ""), entity_id=space_data["id"]),
            Breadcrumb(name=list_data.get("name", ""), entity_id=list_data["id"]),
            Breadcrumb(name=task_data.get("name", ""), entity_id=task_data["id"]),
            Breadcrumb(name=f"Comment {comment_data['id']}", entity_id=comment_data["id"])
        ]

        # Handle datetime
        date = None
        if comment_data.get("date"):
            try:
                date = datetime.fromtimestamp(int(comment_data["date"]) / 1000)
            except (ValueError, TypeError):
                pass

        return ClickUpCommentEntity(
            breadcrumbs=breadcrumbs,
            clickup_id=comment_data["id"],
            task_id=task_data["id"],
            task_name=task_data.get("name", ""),
            list_id=list_data["id"],
            list_name=list_data.get("name", ""),
            space_id=space_data["id"],
            space_name=space_data.get("name", ""),
            workspace_id=workspace_data["id"],
            comment_text=comment_data.get("comment_text", ""),
            user=comment_data.get("user"),
            date=date,
            comment_type=comment_data.get("type"),
            resolved=comment_data.get("resolved", False),
            parent_comment_id=comment_data.get("parent"),
            replies=comment_data.get("replies", [])
        )