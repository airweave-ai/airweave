"""Asana source implementation for syncing workspaces, projects, tasks, and comments."""

from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import AsanaAuthConfig
from airweave.platform.configs.config import AsanaConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.asana import (
    AsanaCommentEntity,
    AsanaFileEntity,
    AsanaProjectEntity,
    AsanaSectionEntity,
    AsanaTaskEntity,
    AsanaWorkspaceEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Asana",
    short_name="asana",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=AsanaAuthConfig,
    config_class=AsanaConfig,
    labels=["Project Management"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class AsanaSource(BaseSource):
    """Asana source connector integrates with the Asana API to extract and synchronize data.

    Connects to your Asana workspaces.

    It supports syncing workspaces, projects, tasks, sections, comments, and file attachments.
    """

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "AsanaSource":
        """Create a new Asana source.

        Args:
            access_token: OAuth access token for Asana API
            config: Optional configuration parameters, like exclude_path

        Returns:
            Configured AsanaSource instance
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
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict:
        """Make authenticated GET request to Asana API with retry logic.

        Retries on:
        - 429 rate limits (respects Retry-After header from both real API and AirweaveHttpClient)
        - Timeout errors (exponential backoff)

        Max 5 attempts with intelligent wait strategy.

        Args:
            client: HTTP client to use for the request
            url: API endpoint URL
            params: Optional query parameters including opt_fields
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
            self.logger.error(f"HTTP error from Asana API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing Asana API: {url}, {str(e)}")
            raise

    async def _generate_workspace_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[AsanaWorkspaceEntity, None]:
        """Generate workspace entities."""
        # Request all available fields for workspaces
        workspace_fields = ["gid", "name", "is_organization", "email_domains", "resource_type"]
        workspaces_data = await self._get_with_auth(
            client,
            "https://app.asana.com/api/1.0/workspaces",
            params={"opt_fields": ",".join(workspace_fields)},
        )

        for workspace in workspaces_data.get("data", []):
            yield AsanaWorkspaceEntity(
                gid=workspace["gid"],
                name=workspace["name"],
                breadcrumbs=[],  # Root entity
                is_organization=workspace.get("is_organization", False),
                email_domains=workspace.get("email_domains", []),
                permalink_url=f"https://app.asana.com/0/{workspace['gid']}",
            )

    async def _generate_project_entities(
        self, client: httpx.AsyncClient, workspace: Dict, workspace_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[AsanaProjectEntity, None]:
        """Generate project entities for a workspace."""
        # Request all available fields for projects, including timestamps
        project_fields = [
            "gid",
            "name",
            "color",
            "archived",
            "created_at",
            "modified_at",
            "current_status",
            "current_status.text",
            "current_status.color",
            "default_view",
            "due_on",
            "html_notes",
            "notes",
            "public",
            "start_on",
            "owner",
            "owner.name",
            "team",
            "team.name",
            "members",
            "members.name",
            "followers",
            "followers.name",
            "custom_fields",
            "custom_field_settings",
            "default_access_level",
            "icon",
            "permalink_url",
        ]
        projects_data = await self._get_with_auth(
            client,
            f"https://app.asana.com/api/1.0/workspaces/{workspace['gid']}/projects",
            params={"opt_fields": ",".join(project_fields)},
        )

        for project in projects_data.get("data", []):
            project_name = project["name"]

            # Skip projects matching exclude_path
            if self.exclude_path and self.exclude_path in project_name:
                self.logger.debug(f"Skipping excluded project: {project_name}")
                continue

            yield AsanaProjectEntity(
                gid=project["gid"],
                name=project["name"],
                created_at=project.get("created_at"),
                modified_at=project.get("modified_at"),
                breadcrumbs=[workspace_breadcrumb],
                workspace_gid=workspace["gid"],
                workspace_name=workspace["name"],
                color=project.get("color"),
                archived=project.get("archived", False),
                current_status=project.get("current_status"),
                default_view=project.get("default_view"),
                due_date=project.get("due_on"),
                due_on=project.get("due_on"),
                html_notes=project.get("html_notes"),
                notes=project.get("notes"),
                is_public=project.get("public", False),
                start_on=project.get("start_on"),
                owner=project.get("owner"),
                team=project.get("team"),
                members=project.get("members", []),
                followers=project.get("followers", []),
                custom_fields=project.get("custom_fields", []),
                custom_field_settings=project.get("custom_field_settings", []),
                default_access_level=project.get("default_access_level"),
                icon=project.get("icon"),
                permalink_url=project.get("permalink_url"),
            )

    async def _generate_section_entities(
        self, client: httpx.AsyncClient, project: Dict, project_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[AsanaSectionEntity, None]:
        """Generate section entities for a project."""
        # Request all available fields for sections
        section_fields = ["gid", "name", "created_at", "projects", "projects.name"]
        sections_data = await self._get_with_auth(
            client,
            f"https://app.asana.com/api/1.0/projects/{project['gid']}/sections",
            params={"opt_fields": ",".join(section_fields)},
        )

        for section in sections_data.get("data", []):
            yield AsanaSectionEntity(
                gid=section["gid"],
                name=section["name"],
                created_at=section.get("created_at"),
                breadcrumbs=project_breadcrumbs,
                project_gid=project["gid"],
                projects=section.get("projects", []),
            )

    async def _generate_task_entities(
        self,
        client: httpx.AsyncClient,
        project: Dict,
        section: Optional[Dict] = None,
        breadcrumbs: List[Breadcrumb] = None,
    ) -> AsyncGenerator[AsanaTaskEntity, None]:
        """Generate task entities for a project or section with pagination."""
        url = (
            f"https://app.asana.com/api/1.0/sections/{section['gid']}/tasks"
            if section
            else f"https://app.asana.com/api/1.0/projects/{project['gid']}/tasks"
        )

        # Request ALL available fields for tasks, especially timestamps
        task_fields = [
            "gid",
            "name",
            "actual_time_minutes",
            "approval_status",
            "assignee",
            "assignee.name",
            "assignee_status",
            "completed",
            "completed_at",
            "completed_by",
            "completed_by.name",
            "created_at",
            "modified_at",  # Important timestamps
            "dependencies",
            "dependents",
            "due_at",
            "due_on",
            "start_at",
            "start_on",  # All date/time fields
            "external",
            "html_notes",
            "notes",
            "is_rendered_as_separator",
            "liked",
            "memberships",
            "num_likes",
            "num_subtasks",
            "parent",
            "parent.name",
            "permalink_url",
            "resource_subtype",
            "tags",
            "tags.name",
            "custom_fields",
            "followers",
            "followers.name",
            "workspace",
            "workspace.name",
        ]

        # Use pagination to handle large result sets
        # Asana API default limit is 20, max is 100
        params = {"opt_fields": ",".join(task_fields), "limit": 100}
        offset = None

        try:
            while True:
                if offset:
                    params["offset"] = offset

                tasks_data = await self._get_with_auth(client, url, params=params)

                for task in tasks_data.get("data", []):
                    # If we have a section, add it to the breadcrumbs
                    task_breadcrumbs = breadcrumbs
                    if section:
                        section_breadcrumb = Breadcrumb(
                            entity_id=section["gid"],
                            name=section["name"],
                            entity_type="AsanaSectionEntity",
                        )
                        task_breadcrumbs = [*breadcrumbs, section_breadcrumb]

                    yield AsanaTaskEntity(
                        gid=task["gid"],
                        name=task["name"],
                        created_at=task.get("created_at"),
                        modified_at=task.get("modified_at"),
                        breadcrumbs=task_breadcrumbs,
                        project_gid=project["gid"],
                        section_gid=section["gid"] if section else None,
                        actual_time_minutes=task.get("actual_time_minutes"),
                        approval_status=task.get("approval_status"),
                        assignee=task.get("assignee"),
                        assignee_status=task.get("assignee_status"),
                        completed=task.get("completed", False),
                        completed_at=task.get("completed_at"),
                        completed_by=task.get("completed_by"),
                        dependencies=task.get("dependencies", []),
                        dependents=task.get("dependents", []),
                        due_at=task.get("due_at"),
                        due_on=task.get("due_on"),
                        external=task.get("external"),
                        html_notes=task.get("html_notes"),
                        notes=task.get("notes"),
                        is_rendered_as_separator=task.get("is_rendered_as_separator", False),
                        liked=task.get("liked", False),
                        memberships=task.get("memberships", []),
                        num_likes=task.get("num_likes", 0),
                        num_subtasks=task.get("num_subtasks", 0),
                        parent=task.get("parent"),
                        permalink_url=task.get("permalink_url"),
                        resource_subtype=task.get("resource_subtype", "default_task"),
                        start_at=task.get("start_at"),
                        start_on=task.get("start_on"),
                        tags=task.get("tags", []),
                        custom_fields=task.get("custom_fields", []),
                        followers=task.get("followers", []),
                        workspace=task.get("workspace"),
                    )

                # Check for next page
                next_page = tasks_data.get("next_page")
                if next_page and next_page.get("offset"):
                    offset = next_page["offset"]
                else:
                    break  # No more pages

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                # Handle "result too large" error - log warning and skip this section/project
                context = f"section {section['gid']}" if section else f"project {project['gid']}"
                self.logger.warning(
                    f"Skipping tasks for {context}: result too large even with pagination. "
                    f"Some tasks may be missing."
                )
                return
            raise

    async def _generate_comment_entities(
        self, client: httpx.AsyncClient, task: Dict, task_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[AsanaCommentEntity, None]:
        """Generate comment entities for a task."""
        # Request all available fields for stories/comments
        story_fields = [
            "gid",
            "created_at",
            "created_by",
            "created_by.name",
            "resource_subtype",
            "text",
            "html_text",
            "is_pinned",
            "is_edited",
            "sticker_name",
            "num_likes",
            "liked",
            "type",
            "previews",
        ]
        stories_data = await self._get_with_auth(
            client,
            f"https://app.asana.com/api/1.0/tasks/{task['gid']}/stories",
            params={"opt_fields": ",".join(story_fields)},
        )

        for story in stories_data.get("data", []):
            if story.get("resource_subtype") != "comment_added":
                continue

            yield AsanaCommentEntity(
                gid=story["gid"],
                created_at=story.get("created_at"),
                breadcrumbs=task_breadcrumbs,
                # API fields
                task_gid=task["gid"],
                author=story["created_by"],
                resource_subtype="comment_added",
                text=story.get("text"),
                html_text=story.get("html_text"),
                is_pinned=story.get("is_pinned", False),
                is_edited=story.get("is_edited", False),
                sticker_name=story.get("sticker_name"),
                num_likes=story.get("num_likes", 0),
                liked=story.get("liked", False),
                type=story.get("type", "comment"),
                previews=story.get("previews", []),
            )

    async def _generate_file_entities(
        self,
        client: httpx.AsyncClient,
        task: Dict,
        task_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[AsanaFileEntity, None]:
        """Generate file attachment entities for a task."""
        # Request basic attachment list first
        attachment_list_fields = ["gid", "name", "resource_type"]
        attachments_data = await self._get_with_auth(
            client,
            f"https://app.asana.com/api/1.0/tasks/{task['gid']}/attachments",
            params={"opt_fields": ",".join(attachment_list_fields)},
        )

        for attachment in attachments_data.get("data", []):
            # Request all available fields for individual attachment, including timestamps
            attachment_fields = [
                "gid",
                "name",
                "resource_type",
                "created_at",
                "modified_at",
                "download_url",
                "permanent",
                "host",
                "parent",
                "parent.name",
                "size",
                "view_url",
                "mime_type",
            ]
            attachment_response = await self._get_with_auth(
                client,
                f"https://app.asana.com/api/1.0/attachments/{attachment['gid']}",
                params={"opt_fields": ",".join(attachment_fields)},
            )

            attachment_detail = attachment_response.get("data")

            if (
                "download_url" not in attachment_detail
                or attachment_detail.get("download_url") is None
            ):
                self.logger.warning(
                    f"No download URL found for attachment {attachment['gid']} "
                    f"in task {task['gid']}"
                )
                continue

            # Determine file type from mime_type or filename
            mime_type = attachment_detail.get("mime_type", "application/octet-stream")
            file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

            # Extract project_gid safely from breadcrumbs
            # Breadcrumbs: workspace (0), project (1), [optional section], task (last)
            project_gid = None
            for bc in task_breadcrumbs:
                if bc.entity_type == "AsanaProjectEntity":
                    project_gid = bc.entity_id
                    break

            # Create the file entity with metadata
            file_entity = AsanaFileEntity(
                gid=attachment_detail["gid"],
                name=attachment_detail.get("name", "unknown"),
                created_at=attachment_detail.get("created_at"),
                breadcrumbs=task_breadcrumbs,
                # FileEntity fields
                url=attachment_detail.get("download_url"),  # Required by FileEntity
                size=attachment_detail.get("size", 0),
                file_type=file_type,
                mime_type=mime_type,
                local_path=None,
                # Asana-specific fields
                task_gid=task["gid"],
                task_name=task["name"],
                project_gid=project_gid,
                resource_type=attachment_detail.get("resource_type"),
                host=attachment_detail.get("host"),
                parent=attachment_detail.get("parent"),
                view_url=attachment_detail.get("view_url"),
                permanent=attachment_detail.get("permanent", False),
            )

            # Download file using downloader
            try:
                await self.file_downloader.download_from_url(
                    entity=file_entity,
                    http_client_factory=self.http_client,
                    access_token_provider=self.get_access_token,
                    logger=self.logger,
                )

                # Verify download succeeded
                if not file_entity.local_path:
                    raise ValueError(f"Download failed - no local path set for {file_entity.name}")

                yield file_entity

            except FileSkippedException as e:
                # File intentionally skipped (unsupported type, too large, etc.) - not an error
                self.logger.debug(f"Skipping attachment {attachment_detail['gid']}: {e.reason}")
                continue

            except Exception as e:
                self.logger.error(
                    f"Failed to download attachment {attachment_detail['gid']} "
                    f"for task {task['gid']}: {e}"
                )
                # Continue with next attachment, don't fail entire sync

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Asana."""
        async with self.http_client() as client:
            async for workspace_entity in self._generate_workspace_entities(client):
                yield workspace_entity

                workspace_breadcrumb = Breadcrumb(
                    entity_id=workspace_entity.gid,
                    name=workspace_entity.name,
                    entity_type="AsanaWorkspaceEntity",
                )

                async for project_entity in self._generate_project_entities(
                    client,
                    {"gid": workspace_entity.gid, "name": workspace_entity.name},
                    workspace_breadcrumb,
                ):
                    yield project_entity

                    project_breadcrumb = Breadcrumb(
                        entity_id=project_entity.gid,
                        name=project_entity.name,
                        entity_type="AsanaProjectEntity",
                    )
                    project_breadcrumbs = [workspace_breadcrumb, project_breadcrumb]

                    async for section_entity in self._generate_section_entities(
                        client,
                        {"gid": project_entity.gid},
                        project_breadcrumbs,
                    ):
                        yield section_entity

                        # Generate tasks within section with full breadcrumb path
                        async for task_entity in self._generate_task_entities(
                            client,
                            {"gid": project_entity.gid},
                            {"gid": section_entity.gid, "name": section_entity.name},
                            project_breadcrumbs,
                        ):
                            yield task_entity

                            # Generate file attachments for the task
                            task_breadcrumb = Breadcrumb(
                                entity_id=task_entity.gid,
                                name=task_entity.name,
                                entity_type="AsanaTaskEntity",
                            )
                            task_breadcrumbs = [*project_breadcrumbs, task_breadcrumb]

                            async for file_entity in self._generate_file_entities(
                                client,
                                {
                                    "gid": task_entity.gid,
                                    "name": task_entity.name,
                                },
                                task_breadcrumbs,
                            ):
                                yield file_entity

                    # Generate tasks not in any section
                    async for task_entity in self._generate_task_entities(
                        client,
                        {"gid": project_entity.gid},
                        breadcrumbs=project_breadcrumbs,
                    ):
                        yield task_entity

                        # Generate file attachments for the task
                        task_breadcrumb = Breadcrumb(
                            entity_id=task_entity.gid,
                            name=task_entity.name,
                            entity_type="AsanaTaskEntity",
                        )
                        task_breadcrumbs = [*project_breadcrumbs, task_breadcrumb]

                        async for file_entity in self._generate_file_entities(
                            client,
                            {
                                "gid": task_entity.gid,
                                "name": task_entity.name,
                            },
                            task_breadcrumbs,
                        ):
                            yield file_entity

    async def validate(self) -> bool:
        """Verify OAuth2 token by pinging Asana's /users/me endpoint."""
        return await self._validate_oauth2(
            ping_url="https://app.asana.com/api/1.0/users/me",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
