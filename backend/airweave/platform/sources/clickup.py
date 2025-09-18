"""ClickUp source implementation for syncing workspaces, spaces, folders, lists, tasks, comments."""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.exceptions import TokenRefreshError
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.clickup import (
    ClickUpCommentEntity,
    ClickUpFileEntity,
    ClickUpFolderEntity,
    ClickUpListEntity,
    ClickUpSpaceEntity,
    ClickUpSubtaskEntity,
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
    """ClickUp source connector integrates with the ClickUp API to extract and synchronize data.

    Connects to your ClickUp workspaces.

    It supports syncing workspaces, spaces, folders, lists, tasks, and comments.
    """

    BASE_URL = "https://api.clickup.com/api/v2"

    def _parse_clickup_timestamp(self, timestamp: Any) -> Optional[datetime]:
        """Parse ClickUp timestamp to datetime object."""
        if not timestamp:
            return None

        try:
            # ClickUp timestamps are usually in milliseconds
            if isinstance(timestamp, (int, str)):
                timestamp_int = int(timestamp)
                # Convert from milliseconds to seconds if needed
                if timestamp_int > 1e10:  # Likely milliseconds
                    return datetime.fromtimestamp(timestamp_int / 1000)
                else:  # Likely seconds
                    return datetime.fromtimestamp(timestamp_int)
        except (ValueError, TypeError):
            self.logger.debug(f"Could not parse timestamp: {timestamp}")
            return None

        return None

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "ClickUpSource":
        """Create a new ClickUp source.

        Args:
            access_token: OAuth access token for ClickUp API
            config: Optional configuration parameters

        Returns:
            Configured ClickUpSource instance
        """
        instance = cls()
        instance.access_token = access_token

        # Store config values as instance attributes
        if config:
            instance.exclude_path = config.get("exclude_path", "")
        else:
            instance.exclude_path = ""

        return instance

    @retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Make authenticated GET request to ClickUp API with token manager support.

        This method uses the token manager for authentication and handles
        401 errors by refreshing the token and retrying.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters
        """
        # Get a valid token (will refresh if needed)
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError("No access token available")

        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 Unauthorized - token might have expired
            if response.status_code == 401:
                self.logger.warning(f"Received 401 Unauthorized for {url}, refreshing token...")

                # If we have a token manager, try to refresh
                if self.token_manager:
                    try:
                        # Force refresh the token
                        new_token = await self.token_manager.refresh_on_unauthorized()
                        headers = {"Authorization": f"Bearer {new_token}"}

                        # Retry the request with the new token
                        self.logger.info(f"Retrying request with refreshed token: {url}")
                        response = await client.get(url, headers=headers, params=params)

                    except TokenRefreshError as e:
                        self.logger.error(f"Failed to refresh token: {str(e)}")
                        response.raise_for_status()
                else:
                    # No token manager, can't refresh
                    self.logger.error("No token manager available to refresh expired token")
                    response.raise_for_status()

            # Raise for other HTTP errors
            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from ClickUp API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing ClickUp API: {url}, {str(e)}")
            raise

    async def _generate_workspace_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate workspace entities."""
        # Get teams (workspaces) from ClickUp API
        teams_data = await self._get_with_auth(client, f"{self.BASE_URL}/team")

        for team in teams_data.get("teams", []):
            yield ClickUpWorkspaceEntity(
                entity_id=team["id"],
                breadcrumbs=[],
                workspace_id=team["id"],
                name=team["name"],
                color=team.get("color"),
                avatar=team.get("avatar"),
                members=team.get("members", []),
            )

    async def _generate_space_entities(
        self, client: httpx.AsyncClient, workspace: Dict, workspace_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate space entities for a workspace."""
        spaces_data = await self._get_with_auth(
            client, f"{self.BASE_URL}/team/{workspace['id']}/space"
        )

        for space in spaces_data.get("spaces", []):
            yield ClickUpSpaceEntity(
                entity_id=space["id"],
                breadcrumbs=[workspace_breadcrumb],
                space_id=space["id"],
                name=space["name"],
                private=space.get("private", False),
                status=space.get("status", {}),
                multiple_assignees=space.get("multiple_assignees", False),
                features=space.get("features", {}),
            )

    async def _generate_folder_entities(
        self, client: httpx.AsyncClient, space: Dict, space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate folder entities for a space."""
        folders_data = await self._get_with_auth(
            client, f"{self.BASE_URL}/space/{space['id']}/folder"
        )

        for folder in folders_data.get("folders", []):
            yield ClickUpFolderEntity(
                entity_id=folder["id"],
                breadcrumbs=[space_breadcrumb],
                folder_id=folder["id"],
                name=folder["name"],
                hidden=folder.get("hidden", False),
                space_id=space["id"],
                task_count=folder.get("task_count"),
            )

    async def _generate_list_entities(
        self,
        client: httpx.AsyncClient,
        folder: Optional[Dict],
        parent_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate list entities for a folder or space."""
        if folder:
            # Lists within a folder
            lists_data = await self._get_with_auth(
                client, f"{self.BASE_URL}/folder/{folder['id']}/list"
            )
            space_id = folder.get("space_id", "")
        else:
            # Lists directly in a space (when no folder is used)
            space_id = parent_breadcrumbs[-1].entity_id if parent_breadcrumbs else None
            if not space_id:
                return
            lists_data = await self._get_with_auth(client, f"{self.BASE_URL}/space/{space_id}/list")

        for list_item in lists_data.get("lists", []):
            # Determine parent names from breadcrumbs
            space_name = ""
            folder_name = None

            if len(parent_breadcrumbs) >= 2:  # workspace + space
                space_name = parent_breadcrumbs[1].name
            if len(parent_breadcrumbs) >= 3:  # workspace + space + folder
                folder_name = parent_breadcrumbs[2].name

            yield ClickUpListEntity(
                entity_id=list_item["id"],
                breadcrumbs=parent_breadcrumbs,
                list_id=list_item["id"],
                name=list_item["name"],
                folder_id=folder["id"] if folder else None,
                space_id=space_id,
                content=list_item.get("content"),
                status=list_item.get("status"),
                priority=list_item.get("priority"),
                assignee=list_item.get("assignee"),
                task_count=list_item.get("task_count"),
                due_date=list_item.get("due_date"),
                start_date=list_item.get("start_date"),
                folder_name=folder_name,
                space_name=space_name,
            )

    async def _generate_task_entities(
        self, client: httpx.AsyncClient, list_item: Dict, list_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate task entities for a list."""
        # Include subtasks in the task request
        tasks_data = await self._get_with_auth(
            client,
            f"{self.BASE_URL}/list/{list_item['id']}/task",
            params={"include_subtasks": "true", "subtasks": "true"},
        )

        # First pass: collect all tasks and build parent-child relationships
        all_tasks = tasks_data.get("tasks", [])
        task_map = {task["id"]: task for task in all_tasks}

        # Helper function to build nested breadcrumbs and calculate nesting level
        def build_subtask_breadcrumbs(
            task_id: str, base_breadcrumbs: List[Breadcrumb]
        ) -> tuple[List[Breadcrumb], int]:
            """Build breadcrumbs for nested subtasks by walking up the parent chain.

            Returns:
                tuple: (breadcrumbs, nesting_level)
            """
            breadcrumbs = list(base_breadcrumbs)  # Copy base breadcrumbs

            # Walk up the parent chain to build the hierarchy
            current_task_id = task_id
            parent_chain = []

            while current_task_id in task_map:
                current_task = task_map[current_task_id]
                parent_id = current_task.get("parent")

                if parent_id and parent_id in task_map:
                    parent_task = task_map[parent_id]
                    parent_chain.append(parent_task)
                    current_task_id = parent_id
                else:
                    break

            # Add parent tasks to breadcrumbs (in reverse order - top-level first)
            for parent_task in reversed(parent_chain):
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=parent_task["id"],
                        name=parent_task["name"],
                        type="task" if not parent_task.get("parent") else "subtask",
                    )
                )

            # Nesting level is the length of the parent chain
            nesting_level = len(parent_chain)

            return breadcrumbs, nesting_level

        # Second pass: yield entities with proper breadcrumbs
        for task in all_tasks:
            if task.get("parent"):
                # This is a subtask (could be nested) - build proper breadcrumbs and nesting level
                subtask_breadcrumbs, nesting_level = build_subtask_breadcrumbs(
                    task["id"], list_breadcrumbs
                )

                yield ClickUpSubtaskEntity(
                    entity_id=task["id"],
                    breadcrumbs=subtask_breadcrumbs,
                    subtask_id=task["id"],
                    name=task["name"],
                    parent_task_id=task["parent"],
                    status=task.get("status", {}),
                    assignees=task.get("assignees", []),
                    due_date=task.get("due_date"),
                    description=task.get("description", ""),
                    nesting_level=nesting_level,
                )
            else:
                # This is a regular task (top-level)
                yield ClickUpTaskEntity(
                    entity_id=task["id"],
                    breadcrumbs=list_breadcrumbs,
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
                    list_id=list_item["id"],
                    folder_id=list_item.get("folder_id", ""),
                    space_id=list_item.get("space_id", ""),
                    url=task.get("url", ""),
                    description=task.get("description", ""),
                    parent=task.get("parent"),
                )

    async def _generate_comment_entities(
        self, client: httpx.AsyncClient, task: Dict, task_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate comment entities for a task."""
        comments_data = await self._get_with_auth(
            client, f"{self.BASE_URL}/task/{task['id']}/comment"
        )

        for comment in comments_data.get("comments", []):
            # Extract text content from comment structure
            comment_text = ""
            comment_content = comment.get("comment", [])
            if isinstance(comment_content, list):
                # Join all text parts from the comment list
                text_parts = []
                for part in comment_content:
                    if isinstance(part, dict) and "text" in part:
                        text_parts.append(part["text"])
                    elif isinstance(part, str):
                        text_parts.append(part)
                comment_text = " ".join(text_parts)
            elif isinstance(comment_content, str):
                comment_text = comment_content

            yield ClickUpCommentEntity(
                entity_id=comment["id"],
                breadcrumbs=task_breadcrumbs,
                comment_id=comment["id"],
                task_id=task["id"],
                user=comment.get("user", {}),
                text_content=comment_text,
                resolved=comment.get("resolved", False),
                assignee=comment.get("assignee"),
                assigned_by=comment.get("assigned_by"),
                reactions=comment.get("reactions", []),
                date=comment.get("date") or comment.get("date_created"),
            )

    async def _generate_subtask_entities(
        self, client: httpx.AsyncClient, task: Dict, task_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate subtask entities for a task."""
        # Get subtasks from the task's subtasks field (if included in response)
        subtasks = task.get("subtasks", [])

        # Note: ClickUp API doesn't have a separate /subtask endpoint
        # Subtasks are returned as tasks with a 'parent' field in the main task list
        # Our main approach in _generate_task_entities handles this correctly

        # Generate subtask entities from any subtasks included in the task response
        for subtask in subtasks:
            # Handle both full subtask objects and simple references
            if isinstance(subtask, dict):
                subtask_id = subtask.get("id", "")
                subtask_name = subtask.get("name", "")

                # Skip if essential fields are missing
                if not subtask_id or not subtask_name:
                    continue

                yield ClickUpSubtaskEntity(
                    entity_id=subtask_id,
                    breadcrumbs=task_breadcrumbs,
                    subtask_id=subtask_id,
                    name=subtask_name,
                    parent_task_id=task["id"],
                    status=subtask.get("status", {}),
                    assignees=subtask.get("assignees", []),
                    due_date=subtask.get("due_date"),
                    description=subtask.get("description", ""),
                )

    async def _generate_file_entities(
        self, client: httpx.AsyncClient, task: Dict, task_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate file attachment entities for a task."""
        task_id = task["id"]

        # Process attachments for the task

        try:
            # Get full task details to access attachments
            # Try different approaches to get attachments
            api_url = f"{self.BASE_URL}/task/{task_id}"

            # Get task details with attachments
            task_details = await self._get_with_auth(client, api_url)

            # Get attachments from the response
            attachments = task_details.get("attachments", [])

            for attachment in attachments:
                attachment_id = attachment.get("id")
                attachment_title = attachment.get("title")
                attachment_url = attachment.get("url")

                # Skip folders
                if attachment.get("is_folder", False):
                    continue

                # Skip if no download URL
                if not attachment_url:
                    self.logger.warning(
                        f"No download URL for attachment {attachment_id}: {attachment_title}"
                    )
                    continue

                # Determine the best name for the file
                file_name = (
                    attachment_title or attachment.get("name") or f"attachment_{attachment_id}"
                )
                download_url = attachment_url

                # Parse the attachment date
                attachment_date = self._parse_clickup_timestamp(attachment.get("date"))

                # Create file entity with all available fields
                file_entity = ClickUpFileEntity(
                    entity_id=attachment["id"],
                    breadcrumbs=task_breadcrumbs,
                    file_id=attachment["id"],
                    name=file_name,
                    mime_type=attachment.get("mimetype"),
                    size=attachment.get("size"),
                    download_url=download_url,
                    metadata={
                        "clickup_attachment_id": attachment["id"],
                        "version": attachment.get("version"),
                        "extension": attachment.get("extension"),
                        "thumbnail_small": attachment.get("thumbnail_small"),
                        "thumbnail_medium": attachment.get("thumbnail_medium"),
                        "thumbnail_large": attachment.get("thumbnail_large"),
                        "total_comments": attachment.get("total_comments"),
                        "user": attachment.get("user"),
                        "source": attachment.get("source"),
                        "type": attachment.get("type"),
                        "orientation": attachment.get("orientation"),
                        "email_data": attachment.get("email_data"),
                        "resolved": attachment.get("resolved"),
                        "hidden": attachment.get("hidden"),
                        "is_folder": attachment.get("is_folder"),
                        "original_date": attachment.get("date"),  # Keep raw value for debugging
                        "url_w_query": attachment.get("url_w_query"),
                        "url_w_host": attachment.get("url_w_host"),
                        "parent_id": attachment.get("parent_id"),
                        "deleted": attachment.get("deleted"),
                        "workspace_id": attachment.get("workspace_id"),
                        "resolved_comments": attachment.get("resolved_comments"),
                    },
                    # ClickUp-specific fields
                    task_id=task["id"],
                    task_name=task.get("name", ""),
                    attachment_id=attachment["id"],
                    version=attachment.get("version"),
                    date=attachment_date,
                    title=attachment.get("title"),
                    extension=attachment.get("extension"),
                    hidden=attachment.get("hidden", False),
                    parent=attachment.get("parent"),
                    thumbnail_small=attachment.get("thumbnail_small"),
                    thumbnail_medium=attachment.get("thumbnail_medium"),
                    thumbnail_large=attachment.get("thumbnail_large"),
                    is_folder=attachment.get("is_folder"),  # Allow None
                    mimetype=attachment.get("mimetype"),
                    total_comments=attachment.get("total_comments"),
                    url=download_url,
                    url_w_query=attachment.get("url_w_query"),
                    url_w_host=attachment.get("url_w_host"),
                    email_data=attachment.get("email_data"),
                    user=attachment.get("user"),
                    resolved=attachment.get("resolved"),
                    resolved_comments=attachment.get("resolved_comments"),
                    source=attachment.get("source"),  # This is an integer
                    attachment_type=attachment.get("type"),  # This is an integer
                    orientation=attachment.get("orientation"),
                    parent_id=attachment.get("parent_id"),
                    deleted=attachment.get("deleted"),
                    workspace_id=attachment.get("workspace_id"),
                )

                # Process the file using the BaseSource helper method
                # ClickUp attachment URLs are pre-signed and don't require OAuth headers
                processed_entity = await self.process_file_entity(
                    file_entity=file_entity, headers={}
                )

                # Only yield if the entity was successfully processed
                if processed_entity:
                    yield processed_entity

        except Exception as e:
            self.logger.error(f"Error processing attachments for task {task_id}: {str(e)}")

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:  # noqa: C901
        """Generate all entities from ClickUp."""
        async with httpx.AsyncClient() as client:
            async for workspace_entity in self._generate_workspace_entities(client):
                yield workspace_entity

                workspace_breadcrumb = Breadcrumb(
                    entity_id=workspace_entity.workspace_id,
                    name=workspace_entity.name,
                    type="workspace",
                )

                async for space_entity in self._generate_space_entities(
                    client,
                    {"id": workspace_entity.workspace_id, "name": workspace_entity.name},
                    workspace_breadcrumb,
                ):
                    yield space_entity

                    space_breadcrumb = Breadcrumb(
                        entity_id=space_entity.entity_id, name=space_entity.name, type="space"
                    )
                    space_breadcrumbs = [workspace_breadcrumb, space_breadcrumb]

                    # Generate folders (optional) and their lists
                    async for folder_entity in self._generate_folder_entities(
                        client,
                        {"id": space_entity.entity_id},
                        space_breadcrumb,
                    ):
                        yield folder_entity

                        folder_breadcrumb = Breadcrumb(
                            entity_id=folder_entity.entity_id,
                            name=folder_entity.name,
                            type="folder",
                        )
                        folder_breadcrumbs = [*space_breadcrumbs, folder_breadcrumb]

                        # Generate lists within folders
                        async for list_entity in self._generate_list_entities(
                            client,
                            {
                                "id": folder_entity.entity_id,
                                "name": folder_entity.name,
                                "space_id": space_entity.entity_id,
                            },
                            folder_breadcrumbs,
                        ):
                            yield list_entity

                            list_breadcrumb = Breadcrumb(
                                entity_id=list_entity.entity_id,
                                name=list_entity.name,
                                type="list",
                            )
                            list_breadcrumbs = [*folder_breadcrumbs, list_breadcrumb]

                            # Generate tasks and subtasks for this list
                            async for task_entity in self._generate_task_entities(
                                client,
                                {"id": list_entity.entity_id},
                                list_breadcrumbs,
                            ):
                                yield task_entity

                                # Generate comments and attachments for both tasks and subtasks
                                task_breadcrumb = Breadcrumb(
                                    entity_id=task_entity.entity_id,
                                    name=task_entity.name,
                                    type="task"
                                    if isinstance(task_entity, ClickUpTaskEntity)
                                    else "subtask",
                                )
                                task_breadcrumbs = [*list_breadcrumbs, task_breadcrumb]

                                # Generate additional subtasks only for main tasks
                                if isinstance(task_entity, ClickUpTaskEntity):
                                    async for subtask_entity in self._generate_subtask_entities(
                                        client,
                                        {
                                            "id": task_entity.entity_id,
                                            "subtasks": [],
                                        },  # Will be populated from API
                                        task_breadcrumbs,
                                    ):
                                        yield subtask_entity

                                # Generate comments for both tasks and subtasks
                                async for comment_entity in self._generate_comment_entities(
                                    client,
                                    {"id": task_entity.entity_id},
                                    task_breadcrumbs,
                                ):
                                    yield comment_entity

                                # Generate file attachments for both tasks and subtasks
                                async for file_entity in self._generate_file_entities(
                                    client,
                                    {"id": task_entity.entity_id, "name": task_entity.name},
                                    task_breadcrumbs,
                                ):
                                    yield file_entity

                    # Generate lists directly in spaces (no folder)
                    async for list_entity in self._generate_list_entities(
                        client,
                        None,  # No folder
                        space_breadcrumbs,
                    ):
                        yield list_entity

                        list_breadcrumb = Breadcrumb(
                            entity_id=list_entity.entity_id,
                            name=list_entity.name,
                            type="list",
                        )
                        list_breadcrumbs = [*space_breadcrumbs, list_breadcrumb]

                        # Generate tasks and subtasks for this list
                        async for task_entity in self._generate_task_entities(
                            client,
                            {"id": list_entity.entity_id},
                            list_breadcrumbs,
                        ):
                            yield task_entity

                            # Generate comments and attachments for both tasks and subtasks
                            task_breadcrumb = Breadcrumb(
                                entity_id=task_entity.entity_id,
                                name=task_entity.name,
                                type="task"
                                if isinstance(task_entity, ClickUpTaskEntity)
                                else "subtask",
                            )
                            task_breadcrumbs = [*list_breadcrumbs, task_breadcrumb]

                            # Generate additional subtasks only for main tasks (not for subtasks)
                            if isinstance(task_entity, ClickUpTaskEntity):
                                async for subtask_entity in self._generate_subtask_entities(
                                    client,
                                    {
                                        "id": task_entity.entity_id,
                                        "subtasks": [],
                                    },  # Will be populated from API
                                    task_breadcrumbs,
                                ):
                                    yield subtask_entity

                            # Generate comments for both tasks and subtasks
                            async for comment_entity in self._generate_comment_entities(
                                client,
                                {"id": task_entity.entity_id},
                                task_breadcrumbs,
                            ):
                                yield comment_entity

                            # Generate file attachments for both tasks and subtasks
                            async for file_entity in self._generate_file_entities(
                                client,
                                {"id": task_entity.entity_id, "name": task_entity.name},
                                task_breadcrumbs,
                            ):
                                yield file_entity
