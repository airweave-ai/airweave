"""ClickUp source implementation for syncing workspaces, spaces, folders, lists, tasks, comments."""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional, Union

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import ClickUpAuthConfig
from airweave.platform.configs.config import ClickUpConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
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
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="ClickUp",
    short_name="clickup",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=ClickUpAuthConfig,
    config_class=ClickUpConfig,
    labels=["Project Management"],
    supports_continuous=False,
    supports_temporal_relevance=False,
    rate_limit_level=RateLimitLevel.ORG,
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
        cls, access_token: Union[str, ClickUpAuthConfig], config: Optional[Dict[str, Any]] = None
    ) -> "ClickUpSource":
        """Create a new ClickUp source."""
        instance = cls()

        token_value: Optional[str] = None
        if isinstance(access_token, ClickUpAuthConfig):
            token_value = access_token.access_token
        elif isinstance(access_token, str):
            token_value = access_token

        if not token_value or not token_value.strip():
            raise ValueError("ClickUp access token is required")

        instance.access_token = token_value.strip()

        # Store config values as instance attributes
        if config:
            instance.exclude_path = config.get("exclude_path", "")
        else:
            instance.exclude_path = ""

        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
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
                        self.logger.debug(f"Retrying request with refreshed token: {url}")
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
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate workspace entities."""
        # Get teams (workspaces) from ClickUp API
        teams_data = await self._get_with_auth(client, f"{self.BASE_URL}/team")

        for team in teams_data.get("teams", []):
            yield ClickUpWorkspaceEntity(
                workspace_id=team["id"],
                breadcrumbs=[],
                name=team["name"],
                color=team.get("color"),
                avatar=team.get("avatar"),
                members=team.get("members", []),
            )

    async def _generate_space_entities(
        self, client: httpx.AsyncClient, workspace: Dict[str, Any], workspace_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate space entities for a workspace."""
        spaces_data = await self._get_with_auth(
            client, f"{self.BASE_URL}/team/{workspace['id']}/space"
        )

        for space in spaces_data.get("spaces", []):
            yield ClickUpSpaceEntity(
                space_id=space["id"],
                workspace_id=workspace["id"],
                breadcrumbs=[workspace_breadcrumb],
                name=space["name"],
                private=space.get("private", False),
                status=space.get("status", {}),
                multiple_assignees=space.get("multiple_assignees", False),
                features=space.get("features", {}),
            )

    async def _generate_folder_entities(
        self, client: httpx.AsyncClient, space: Dict[str, Any], space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate folder entities for a space."""
        folders_data = await self._get_with_auth(
            client, f"{self.BASE_URL}/space/{space['id']}/folder"
        )

        for folder in folders_data.get("folders", []):
            yield ClickUpFolderEntity(
                folder_id=folder["id"],
                workspace_id=space["workspace_id"],
                space_id=space["id"],
                breadcrumbs=[space_breadcrumb],
                name=folder["name"],
                hidden=folder.get("hidden", False),
                task_count=folder.get("task_count"),
            )

    async def _generate_list_entities(
        self,
        client: httpx.AsyncClient,
        folder: Optional[Dict[str, Any]],
        parent_breadcrumbs: List[Breadcrumb],
        space: Dict[str, Any],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate list entities for a folder or space."""
        if folder:
            # Lists within a folder
            lists_data = await self._get_with_auth(
                client, f"{self.BASE_URL}/folder/{folder['id']}/list"
            )
            space_id = folder.get("space_id", space["id"])
        else:
            # Lists directly in a space (when no folder is used)
            space_id = space["id"]
            if not space_id:
                return
            lists_data = await self._get_with_auth(client, f"{self.BASE_URL}/space/{space_id}/list")
        workspace_id = space["workspace_id"]
        space_name = space.get("name", "")
        folder_name = folder["name"] if folder else None

        for list_item in lists_data.get("lists", []):
            yield ClickUpListEntity(
                list_id=list_item["id"],
                workspace_id=workspace_id,
                space_id=space_id,
                folder_id=folder["id"] if folder else None,
                breadcrumbs=parent_breadcrumbs,
                name=list_item["name"],
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
        self,
        client: httpx.AsyncClient,
        list_meta: Dict[str, Any],
        list_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate task entities for a list."""
        # Include subtasks in the task request
        tasks_data = await self._get_with_auth(
            client,
            f"{self.BASE_URL}/list/{list_meta['id']}/task",
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
                        name=parent_task.get("name", ""),
                        entity_type="ClickUpTaskEntity",
                    )
                )

            # Nesting level is the length of the parent chain
            nesting_level = len(parent_chain)

            return breadcrumbs, nesting_level

        # Second pass: yield entities with proper breadcrumbs
        for task in all_tasks:
            task_created = self._parse_clickup_timestamp(task.get("date_created"))
            task_updated = self._parse_clickup_timestamp(task.get("date_updated"))
            task_url = task.get("url") or f"https://app.clickup.com/t/{task['id']}"

            if task.get("parent"):
                # This is a subtask (could be nested) - build proper breadcrumbs and nesting level
                subtask_breadcrumbs, nesting_level = build_subtask_breadcrumbs(
                    task["id"], list_breadcrumbs
                )

                yield ClickUpSubtaskEntity(
                    subtask_id=task["id"],
                    breadcrumbs=subtask_breadcrumbs,
                    name=task["name"],
                    created_at=task_created,
                    updated_at=task_updated,
                    parent_task_id=task.get("parent", ""),
                    status=task.get("status", {}),
                    assignees=task.get("assignees", []),
                    due_date=task.get("due_date"),
                    description=task.get("description", ""),
                    nesting_level=nesting_level,
                    url=task_url,
                )
            else:
                # This is a regular task (top-level)
                yield ClickUpTaskEntity(
                    task_id=task["id"],
                    breadcrumbs=list_breadcrumbs,
                    name=task["name"],
                    created_at=task_created,
                    updated_at=task_updated,
                    status=task.get("status", {}),
                    priority=task.get("priority"),
                    assignees=task.get("assignees", []),
                    tags=task.get("tags", []),
                    due_date=task.get("due_date"),
                    start_date=task.get("start_date"),
                    time_estimate=task.get("time_estimate"),
                    time_spent=task.get("time_spent"),
                    custom_fields=task.get("custom_fields", []),
                    list_id=list_meta["id"],
                    folder_id=list_meta.get("folder_id"),
                    space_id=list_meta.get("space_id"),
                    workspace_id=list_meta.get("workspace_id"),
                    url=task_url,
                    description=task.get("description", ""),
                    parent=task.get("parent"),
                )

    async def _generate_comment_entities(
        self,
        client: httpx.AsyncClient,
        task_id: str,
        task_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate comment entities for a task."""
        comments_data = await self._get_with_auth(client, f"{self.BASE_URL}/task/{task_id}/comment")

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

            # Create comment name from text preview
            comment_name = comment_text[:50] + "..." if len(comment_text) > 50 else comment_text
            if not comment_name:
                comment_name = f"Comment {comment['id']}"

            # Parse the date for created_at
            date = self._parse_clickup_timestamp(comment.get("date") or comment.get("date_created"))

            yield ClickUpCommentEntity(
                comment_id=comment["id"],
                breadcrumbs=task_breadcrumbs,
                name=comment_name,
                created_at=date,
                task_id=task_id,
                user=comment.get("user", {}),
                text_content=comment_text,
                resolved=comment.get("resolved", False),
                assignee=comment.get("assignee"),
                assigned_by=comment.get("assigned_by"),
                reactions=comment.get("reactions", []),
            )

    async def _generate_file_entities(  # noqa: C901
        self,
        client: httpx.AsyncClient,
        task_id: str,
        task_name: str,
        task_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate file attachment entities for a task."""
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

                # Determine file type from mime_type or extension
                mime_type = attachment.get("mimetype") or "application/octet-stream"
                extension = attachment.get("extension", "")
                if mime_type and "/" in mime_type:
                    file_type = mime_type.split("/")[0]
                elif extension:
                    file_type = extension
                else:
                    file_type = "file"

                # Create file entity with all available fields
                file_entity = ClickUpFileEntity(
                    attachment_id=attachment["id"],
                    breadcrumbs=task_breadcrumbs,
                    name=file_name,
                    created_at=attachment_date,
                    updated_at=None,
                    url=download_url,
                    size=attachment.get("size", 0),
                    file_type=file_type,
                    mime_type=mime_type,
                    local_path=None,
                    task_id=task_id,
                    task_name=task_name,
                    version=attachment.get("version"),
                    title=attachment.get("title"),
                    extension=extension,
                    hidden=attachment.get("hidden", False),
                    parent=attachment.get("parent"),
                    thumbnail_small=attachment.get("thumbnail_small"),
                    thumbnail_medium=attachment.get("thumbnail_medium"),
                    thumbnail_large=attachment.get("thumbnail_large"),
                    is_folder=attachment.get("is_folder"),
                    total_comments=attachment.get("total_comments"),
                    url_w_query=attachment.get("url_w_query"),
                    url_w_host=attachment.get("url_w_host"),
                    email_data=attachment.get("email_data"),
                    user=attachment.get("user"),
                    resolved=attachment.get("resolved"),
                    resolved_comments=attachment.get("resolved_comments"),
                    source=attachment.get("source"),
                    attachment_type=attachment.get("type"),
                    orientation=attachment.get("orientation"),
                    parent_id=attachment.get("parent_id"),
                    deleted=attachment.get("deleted"),
                    workspace_id=attachment.get("workspace_id"),
                )

                # Download the file using file downloader
                try:
                    await self.file_downloader.download_from_url(
                        entity=file_entity,
                        http_client_factory=self.http_client,
                        access_token_provider=self.get_access_token,
                        logger=self.logger,
                    )

                    # Verify download succeeded
                    if not file_entity.local_path:
                        raise ValueError(
                            f"Download failed - no local path set for {file_entity.name}"
                        )

                    # DEBUG: Log file content preview to verify tokens are preserved
                    try:
                        with open(file_entity.local_path, "r", encoding="utf-8") as f:
                            content_preview = f.read(500)  # First 500 chars
                            self.logger.debug(
                                f"Downloaded file {file_entity.name} - "
                                f"Content preview (first 500 chars): {content_preview}"
                            )
                    except Exception as e:
                        self.logger.warning(f"Could not read file preview: {e}")

                    self.logger.debug(f"Successfully downloaded attachment: {file_entity.name}")
                    yield file_entity

                except FileSkippedException as e:
                    # Attachment intentionally skipped (unsupported type, too large, etc.)
                    self.logger.debug(f"Skipping attachment {file_name}: {e.reason}")
                    # Continue with other attachments
                    continue

                except Exception as e:
                    self.logger.warning(f"Failed to download attachment {file_name}: {e}")
                    # Still yield the file entity without processed content
                    yield file_entity

        except Exception as e:
            self.logger.error(f"Error processing attachments for task {task_id}: {str(e)}")

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:  # noqa: C901
        """Generate all entities from ClickUp."""
        async with httpx.AsyncClient() as client:
            async for workspace_entity in self._generate_workspace_entities(client):
                yield workspace_entity

                workspace_breadcrumb = Breadcrumb(
                    entity_id=workspace_entity.workspace_id,
                    name=workspace_entity.name,
                    entity_type="ClickUpWorkspaceEntity",
                )
                workspace_context = {
                    "id": workspace_entity.workspace_id,
                    "name": workspace_entity.name,
                }

                async for space_entity in self._generate_space_entities(
                    client,
                    workspace_context,
                    workspace_breadcrumb,
                ):
                    yield space_entity

                    space_breadcrumb = Breadcrumb(
                        entity_id=space_entity.space_id,
                        name=space_entity.name,
                        entity_type="ClickUpSpaceEntity",
                    )
                    space_breadcrumbs = [workspace_breadcrumb, space_breadcrumb]
                    space_context = {
                        "id": space_entity.space_id,
                        "name": space_entity.name,
                        "workspace_id": workspace_entity.workspace_id,
                    }

                    # Generate folders (optional) and their lists
                    async for folder_entity in self._generate_folder_entities(
                        client,
                        space_context,
                        space_breadcrumb,
                    ):
                        yield folder_entity

                        folder_breadcrumb = Breadcrumb(
                            entity_id=folder_entity.folder_id,
                            name=folder_entity.name,
                            entity_type="ClickUpFolderEntity",
                        )
                        folder_breadcrumbs = [*space_breadcrumbs, folder_breadcrumb]
                        folder_context = {
                            "id": folder_entity.folder_id,
                            "name": folder_entity.name,
                            "space_id": space_context["id"],
                            "workspace_id": space_context["workspace_id"],
                        }

                        # Generate lists within folders
                        async for list_entity in self._generate_list_entities(
                            client,
                            folder_context,
                            folder_breadcrumbs,
                            space_context,
                        ):
                            yield list_entity

                            list_breadcrumb = Breadcrumb(
                                entity_id=list_entity.list_id,
                                name=list_entity.name,
                                entity_type="ClickUpListEntity",
                            )
                            list_breadcrumbs = [*folder_breadcrumbs, list_breadcrumb]
                            list_context = {
                                "id": list_entity.list_id,
                                "name": list_entity.name,
                                "workspace_id": list_entity.workspace_id,
                                "space_id": list_entity.space_id,
                                "folder_id": list_entity.folder_id,
                            }

                            # Generate tasks and subtasks for this list
                            async for task_entity in self._generate_task_entities(
                                client, list_context, list_breadcrumbs
                            ):
                                yield task_entity

                                task_id = (
                                    task_entity.task_id
                                    if isinstance(task_entity, ClickUpTaskEntity)
                                    else task_entity.subtask_id
                                )
                                task_name = task_entity.name
                                task_breadcrumb = Breadcrumb(
                                    entity_id=task_id,
                                    name=task_name,
                                    entity_type=task_entity.__class__.__name__,
                                )
                                task_breadcrumbs = [*list_breadcrumbs, task_breadcrumb]

                                async for comment_entity in self._generate_comment_entities(
                                    client, task_id, task_breadcrumbs
                                ):
                                    yield comment_entity

                                async for file_entity in self._generate_file_entities(
                                    client,
                                    task_id,
                                    task_name,
                                    task_breadcrumbs,
                                ):
                                    yield file_entity

                    # Generate lists directly in spaces (no folder)
                    async for list_entity in self._generate_list_entities(
                        client,
                        None,  # No folder
                        space_breadcrumbs,
                        space_context,
                    ):
                        yield list_entity

                        list_breadcrumb = Breadcrumb(
                            entity_id=list_entity.list_id,
                            name=list_entity.name,
                            entity_type="ClickUpListEntity",
                        )
                        list_breadcrumbs = [*space_breadcrumbs, list_breadcrumb]
                        list_context = {
                            "id": list_entity.list_id,
                            "name": list_entity.name,
                            "workspace_id": list_entity.workspace_id,
                            "space_id": list_entity.space_id,
                            "folder_id": list_entity.folder_id,
                        }

                        # Generate tasks and subtasks for this list
                        async for task_entity in self._generate_task_entities(
                            client, list_context, list_breadcrumbs
                        ):
                            yield task_entity

                            task_id = (
                                task_entity.task_id
                                if isinstance(task_entity, ClickUpTaskEntity)
                                else task_entity.subtask_id
                            )
                            task_name = task_entity.name
                            task_breadcrumb = Breadcrumb(
                                entity_id=task_id,
                                name=task_name,
                                entity_type=task_entity.__class__.__name__,
                            )
                            task_breadcrumbs = [*list_breadcrumbs, task_breadcrumb]

                            async for comment_entity in self._generate_comment_entities(
                                client, task_id, task_breadcrumbs
                            ):
                                yield comment_entity

                            async for file_entity in self._generate_file_entities(
                                client,
                                task_id,
                                task_name,
                                task_breadcrumbs,
                            ):
                                yield file_entity

    async def validate(self) -> bool:
        """Validate credentials by calling ClickUp's /user endpoint."""
        return await self._validate_oauth2(
            ping_url=f"{self.BASE_URL}/user",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
