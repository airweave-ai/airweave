"""ClickUp source implementation for syncing workspaces, spaces, folders, lists, tasks, comments."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
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
    _parse_clickup_ts,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup


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

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: ClickUpConfig,
    ) -> ClickUpSource:
        """Create a new ClickUp source."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """Make authenticated GET request to ClickUp API with token refresh support."""
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}

        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers = {"Authorization": f"Bearer {new_token}"}
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _generate_workspace_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate workspace entities."""
        teams_data = await self._get(f"{self.BASE_URL}/team")

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
        self, workspace: Dict[str, Any], workspace_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate space entities for a workspace."""
        spaces_data = await self._get(f"{self.BASE_URL}/team/{workspace['id']}/space")

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
        self, space: Dict[str, Any], space_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate folder entities for a space."""
        folders_data = await self._get(f"{self.BASE_URL}/space/{space['id']}/folder")

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
        folder: Optional[Dict[str, Any]],
        parent_breadcrumbs: List[Breadcrumb],
        space: Dict[str, Any],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate list entities for a folder or space."""
        if folder:
            lists_data = await self._get(f"{self.BASE_URL}/folder/{folder['id']}/list")
            space_id = folder.get("space_id", space["id"])
        else:
            space_id = space["id"]
            if not space_id:
                return
            lists_data = await self._get(f"{self.BASE_URL}/space/{space_id}/list")
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
        list_meta: Dict[str, Any],
        list_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate task entities for a list."""
        tasks_data = await self._get(
            f"{self.BASE_URL}/list/{list_meta['id']}/task",
            params={"include_subtasks": "true", "subtasks": "true"},
        )

        all_tasks = tasks_data.get("tasks", [])
        task_map = {task["id"]: task for task in all_tasks}

        def build_subtask_breadcrumbs(
            task_id: str, base_breadcrumbs: List[Breadcrumb]
        ) -> tuple[List[Breadcrumb], int]:
            """Build breadcrumbs for nested subtasks by walking up the parent chain."""
            breadcrumbs = list(base_breadcrumbs)
            current_task_id = task_id
            parent_chain = []

            while current_task_id in task_map:
                current_task = task_map[current_task_id]
                parent_id = current_task.get("parent")
                if parent_id and parent_id in task_map:
                    parent_chain.append(task_map[parent_id])
                    current_task_id = parent_id
                else:
                    break

            for parent_task in reversed(parent_chain):
                breadcrumbs.append(
                    Breadcrumb(
                        entity_id=parent_task["id"],
                        name=parent_task.get("name", ""),
                        entity_type="ClickUpTaskEntity",
                    )
                )

            return breadcrumbs, len(parent_chain)

        for task in all_tasks:
            if task.get("parent"):
                subtask_breadcrumbs, nesting_level = build_subtask_breadcrumbs(
                    task["id"], list_breadcrumbs
                )
                yield ClickUpSubtaskEntity.from_api(
                    task, breadcrumbs=subtask_breadcrumbs, nesting_level=nesting_level
                )
            else:
                yield ClickUpTaskEntity.from_api(
                    task, list_meta=list_meta, breadcrumbs=list_breadcrumbs
                )

    async def _generate_comment_entities(
        self,
        task_id: str,
        task_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate comment entities for a task."""
        try:
            comments_data = await self._get(f"{self.BASE_URL}/task/{task_id}/comment")

            for comment in comments_data.get("comments", []):
                yield ClickUpCommentEntity.from_api(
                    comment, task_id=task_id, breadcrumbs=task_breadcrumbs
                )

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error fetching comments for task {task_id}: {e}")
            raise

    async def _generate_file_entities(  # noqa: C901
        self,
        task_id: str,
        task_name: str,
        task_breadcrumbs: List[Breadcrumb],
        files: FileService | None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate file attachment entities for a task."""
        try:
            task_details = await self._get(f"{self.BASE_URL}/task/{task_id}")
            attachments = task_details.get("attachments", [])

            for attachment in attachments:
                attachment_id = attachment.get("id")
                attachment_title = attachment.get("title")
                attachment_url = attachment.get("url")

                if attachment.get("is_folder", False):
                    continue

                if not attachment_url:
                    self.logger.warning(
                        f"No download URL for attachment {attachment_id}: {attachment_title}"
                    )
                    continue

                file_name = (
                    attachment_title or attachment.get("name") or f"attachment_{attachment_id}"
                )

                attachment_date = _parse_clickup_ts(attachment.get("date"))

                mime_type = attachment.get("mimetype") or "application/octet-stream"
                extension = attachment.get("extension", "")
                if mime_type and "/" in mime_type:
                    file_type = mime_type.split("/")[0]
                elif extension:
                    file_type = extension
                else:
                    file_type = "file"

                file_entity = ClickUpFileEntity(
                    attachment_id=attachment["id"],
                    breadcrumbs=task_breadcrumbs,
                    name=file_name,
                    created_at=attachment_date,
                    updated_at=None,
                    url=attachment_url,
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

                if files:
                    try:
                        await files.download_from_url(
                            entity=file_entity,
                            client=self.http_client,
                            auth=self.auth,
                            logger=self.logger,
                        )

                        if not file_entity.local_path:
                            raise ValueError(
                                f"Download failed - no local path set for {file_entity.name}"
                            )

                        self.logger.debug(f"Successfully downloaded attachment: {file_entity.name}")
                        yield file_entity

                    except FileSkippedException as e:
                        self.logger.debug(f"Skipping attachment {file_name}: {e.reason}")
                        continue

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 401:
                            raise
                        self.logger.warning(f"Failed to download attachment {file_name}: {e}")
                        yield file_entity
                else:
                    yield file_entity

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error processing attachments for task {task_id}: {e}")

    # ------------------------------------------------------------------
    # Orchestration
    # ------------------------------------------------------------------

    async def generate_entities(  # noqa: C901
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from ClickUp."""
        async for workspace_entity in self._generate_workspace_entities():
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
                workspace_context, workspace_breadcrumb
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

                async for folder_entity in self._generate_folder_entities(
                    space_context, space_breadcrumb
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

                    async for list_entity in self._generate_list_entities(
                        folder_context, folder_breadcrumbs, space_context
                    ):
                        yield list_entity
                        async for child in self._yield_tasks_and_children(
                            list_entity, folder_breadcrumbs, files
                        ):
                            yield child

                async for list_entity in self._generate_list_entities(
                    None, space_breadcrumbs, space_context
                ):
                    yield list_entity
                    async for child in self._yield_tasks_and_children(
                        list_entity, space_breadcrumbs, files
                    ):
                        yield child

    async def _yield_tasks_and_children(
        self,
        list_entity: ClickUpListEntity,
        parent_breadcrumbs: List[Breadcrumb],
        files: FileService | None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate tasks, comments, and file entities for a list."""
        list_breadcrumb = Breadcrumb(
            entity_id=list_entity.list_id,
            name=list_entity.name,
            entity_type="ClickUpListEntity",
        )
        list_breadcrumbs = [*parent_breadcrumbs, list_breadcrumb]
        list_context = {
            "id": list_entity.list_id,
            "name": list_entity.name,
            "workspace_id": list_entity.workspace_id,
            "space_id": list_entity.space_id,
            "folder_id": list_entity.folder_id,
        }

        async for task_entity in self._generate_task_entities(list_context, list_breadcrumbs):
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

            async for comment_entity in self._generate_comment_entities(task_id, task_breadcrumbs):
                yield comment_entity

            async for file_entity in self._generate_file_entities(
                task_id, task_name, task_breadcrumbs, files
            ):
                yield file_entity

    async def validate(self) -> None:
        """Validate credentials by pinging ClickUp's /user endpoint."""
        await self._get(f"{self.BASE_URL}/user")
