"""Asana source implementation."""

from typing import AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.asana import (
    AsanaCommentEntity,
    AsanaFileEntity,
    AsanaProjectEntity,
    AsanaSectionEntity,
    AsanaTaskEntity,
    AsanaWorkspaceEntity,
)
from airweave.platform.file_handling.file_manager import file_manager
from airweave.platform.permissions.asana import AsanaPermissionMetadata, AsanaUserPermission
from airweave.platform.sources._base import BaseSource


@source("Asana", "asana", AuthType.oauth2_with_refresh, labels=["Project Management"])
class AsanaSource(BaseSource):
    """Asana source implementation."""

    # Base URL for Asana API
    BASE_URL = "https://app.asana.com/api/1.0"

    @classmethod
    async def create(cls, access_token: str) -> "AsanaSource":
        """Create a new Asana source."""
        instance = cls()
        instance.access_token = access_token
        return instance

    @classmethod
    async def get_user_permissions(cls, email: str) -> AsanaUserPermission:
        """Get permissions for a user in Asana.

        Args:
            email: The email of the user

        Returns:
            AsanaUserPermission object with the user's permissions
        """
        return await AsanaUserPermission.from_email(email)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get_with_auth(self, client: httpx.AsyncClient, endpoint: str) -> Dict:
        """Make authenticated GET request to Asana API.

        Args:
            client: The HTTP client to use
            endpoint: The API endpoint (without base URL)

        Returns:
            JSON response from the API
        """
        url = f"{self.BASE_URL}/{endpoint}"
        response = await client.get(
            url,
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e}")
            return None
        return response.json()

    async def _generate_workspace_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate workspace entities."""
        workspaces_data = await self._get_with_auth(client, "workspaces")

        for workspace in workspaces_data.get("data", []):
            entity = AsanaWorkspaceEntity(
                entity_id=workspace["gid"],
                breadcrumbs=[],
                name=workspace["name"],
                asana_gid=workspace["gid"],
                is_organization=workspace.get("is_organization", False),
                email_domains=workspace.get("email_domains", []),
                permalink_url=f"{self.BASE_URL.replace('/api/1.0', '')}/0/{workspace['gid']}",
            )

            # Add permission metadata using Pydantic model
            permission_metadata = AsanaPermissionMetadata(
                workspace_gid=workspace["gid"],
                is_public=True,  # Workspaces are typically viewable by all members
            )

            # Add permission metadata to entity
            entity.sync_metadata = entity.sync_metadata or {}
            entity.sync_metadata["permissions"] = permission_metadata.model_dump()

            yield entity

    async def _generate_project_entities(
        self, client: httpx.AsyncClient, workspace: Dict, workspace_breadcrumb: Breadcrumb
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate project entities for a workspace."""
        projects_data = await self._get_with_auth(client, f"workspaces/{workspace['gid']}/projects")

        if projects_data is None:
            return

        for project in projects_data.get("data", []):
            # Fetch additional project details to get members and other metadata
            project_detail = await self._get_with_auth(client, f"projects/{project['gid']}")
            project_data = project_detail.get("data", {})

            entity = AsanaProjectEntity(
                entity_id=project["gid"],
                breadcrumbs=[workspace_breadcrumb],
                name=project["name"],
                workspace_gid=workspace["gid"],
                workspace_name=workspace["name"],
                color=project_data.get("color"),
                archived=project_data.get("archived", False),
                created_at=project_data.get("created_at"),
                current_status=project_data.get("current_status"),
                default_view=project_data.get("default_view"),
                due_date=project_data.get("due_on"),
                due_on=project_data.get("due_on"),
                html_notes=project_data.get("html_notes"),
                notes=project_data.get("notes"),
                is_public=project_data.get("public", False),
                start_on=project_data.get("start_on"),
                modified_at=project_data.get("modified_at"),
                owner=project_data.get("owner"),
                team=project_data.get("team"),
                members=project_data.get("members", []),
                followers=project_data.get("followers", []),
                custom_fields=project_data.get("custom_fields", []),
                custom_field_settings=project_data.get("custom_field_settings", []),
                default_access_level=project_data.get("default_access_level"),
                icon=project_data.get("icon"),
                permalink_url=project_data.get("permalink_url"),
            )

            # Add permission metadata using Pydantic model
            permission_metadata = AsanaPermissionMetadata(
                workspace_gid=workspace["gid"],
                is_public=project_data.get("public", False),
                members=project_data.get("members", []),
                team_gid=(
                    project_data.get("team", {}).get("gid") if project_data.get("team") else None
                ),
                created_by_gid=(
                    project_data.get("owner", {}).get("gid") if project_data.get("owner") else None
                ),
                followers=project_data.get("followers", []),
            )

            # Add permission metadata to entity
            entity.sync_metadata = entity.sync_metadata or {}
            entity.sync_metadata["permissions"] = permission_metadata.model_dump()

            yield entity

    async def _generate_section_entities(
        self, client: httpx.AsyncClient, project: Dict, project_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate section entities for a project."""
        sections_data = await self._get_with_auth(client, f"projects/{project['gid']}/sections")

        if sections_data is None:
            return

        # Get project details for permission inheritance
        project_detail = await self._get_with_auth(client, f"projects/{project['gid']}")
        project_data = project_detail.get("data", {})

        for section in sections_data.get("data", []):
            entity = AsanaSectionEntity(
                entity_id=section["gid"],
                breadcrumbs=project_breadcrumbs,
                name=section["name"],
                project_gid=project["gid"],
                created_at=section.get("created_at"),
                projects=section.get("projects", []),
            )

            # Add permission metadata using Pydantic model (inherit from project)
            permission_metadata = AsanaPermissionMetadata(
                workspace_gid=(
                    project_data.get("workspace", {}).get("gid")
                    if project_data.get("workspace")
                    else None
                ),
                is_public=project_data.get("public", False),
                members=project_data.get("members", []),
                team_gid=(
                    project_data.get("team", {}).get("gid") if project_data.get("team") else None
                ),
                created_by_gid=(
                    project_data.get("owner", {}).get("gid") if project_data.get("owner") else None
                ),
                followers=project_data.get("followers", []),
            )

            # Add permission metadata to entity
            entity.sync_metadata = entity.sync_metadata or {}
            entity.sync_metadata["permissions"] = permission_metadata.model_dump()

            yield entity

    async def _generate_task_entities(
        self,
        client: httpx.AsyncClient,
        project: Dict,
        section: Optional[Dict] = None,
        breadcrumbs: List[Breadcrumb] = None,
    ) -> AsyncGenerator[AsanaTaskEntity, None]:
        """Generate task entities for a project or section."""
        url_path = (
            f"sections/{section['gid']}/tasks" if section else f"projects/{project['gid']}/tasks"
        )

        tasks_data = await self._get_with_auth(client, url_path)

        if tasks_data is None:
            return

        for task in tasks_data.get("data", []):
            # If we have a section, add it to the breadcrumbs
            task_breadcrumbs = breadcrumbs
            if section:
                section_breadcrumb = Breadcrumb(
                    entity_id=section["gid"], name=section["name"], type="section"
                )
                task_breadcrumbs = [*breadcrumbs, section_breadcrumb]

            # Fetch full task details to get proper permissions
            task_detail = await self._get_with_auth(client, f"tasks/{task['gid']}")
            task_data = task_detail.get("data", {})

            entity = AsanaTaskEntity(
                entity_id=task["gid"],
                breadcrumbs=task_breadcrumbs,
                name=task["name"],
                gid=task["gid"],
                project_gid=project["gid"],
                section_gid=section["gid"] if section else None,
                actual_time_minutes=task_data.get("actual_time_minutes"),
                approval_status=task_data.get("approval_status"),
                assignee=task_data.get("assignee"),
                assignee_status=task_data.get("assignee_status"),
                completed=task_data.get("completed", False),
                completed_at=task_data.get("completed_at"),
                completed_by=task_data.get("completed_by"),
                created_at=task_data.get("created_at"),
                dependencies=task_data.get("dependencies", []),
                dependents=task_data.get("dependents", []),
                due_at=task_data.get("due_at"),
                due_on=task_data.get("due_on"),
                external=task_data.get("external"),
                html_notes=task_data.get("html_notes"),
                notes=task_data.get("notes"),
                is_rendered_as_separator=task_data.get("is_rendered_as_separator", False),
                liked=task_data.get("liked", False),
                memberships=task_data.get("memberships", []),
                modified_at=task_data.get("modified_at"),
                num_likes=task_data.get("num_likes", 0),
                num_subtasks=task_data.get("num_subtasks", 0),
                parent=task_data.get("parent"),
                permalink_url=task_data.get("permalink_url"),
                privacy_setting=task_data.get("privacy_setting"),
                resource_subtype=task_data.get("resource_subtype", "default_task"),
                start_at=task_data.get("start_at"),
                start_on=task_data.get("start_on"),
                tags=task_data.get("tags", []),
                custom_fields=task_data.get("custom_fields", []),
                followers=task_data.get("followers", []),
                workspace=task_data.get("workspace"),
            )

            # Add permission metadata using Pydantic model
            permission_metadata = AsanaPermissionMetadata(
                workspace_gid=(
                    task_data.get("workspace", {}).get("gid")
                    if task_data.get("workspace")
                    else None
                ),
                created_by_gid=(
                    task_data.get("created_by", {}).get("gid")
                    if task_data.get("created_by")
                    else None
                ),
                assigned_to_gid=(
                    task_data.get("assignee", {}).get("gid") if task_data.get("assignee") else None
                ),
                followers=[
                    {"gid": f["gid"], "name": f["name"]} for f in task_data.get("followers", [])
                ],
                memberships=task_data.get("memberships", []),
                is_public=False,  # Tasks are not public by default
            )

            # Add permission metadata to entity
            entity.sync_metadata = entity.sync_metadata or {}
            entity.sync_metadata["permissions"] = permission_metadata.model_dump()

            yield entity

    async def _generate_comment_entities(
        self, client: httpx.AsyncClient, task: Dict, task_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate comment entities for a task."""
        stories_data = await self._get_with_auth(client, f"tasks/{task['gid']}/stories")

        if stories_data is None:
            return

        for story in stories_data.get("data", []):
            if story.get("resource_subtype") != "comment_added":
                continue

            entity = AsanaCommentEntity(
                entity_id=story["gid"],
                breadcrumbs=task_breadcrumbs,
                task_gid=task["gid"],
                name=f"Comment on {task['name']}",
                author=story["created_by"],
                created_at=story["created_at"],
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

            # Add permission metadata using Pydantic model (inherit from task)
            permission_metadata = AsanaPermissionMetadata(
                workspace_gid=(
                    task.get("workspace", {}).get("gid") if task.get("workspace") else None
                ),
                created_by_gid=(
                    story.get("created_by", {}).get("gid") if story.get("created_by") else None
                ),
                assigned_to_gid=(
                    task.get("assignee", {}).get("gid") if task.get("assignee") else None
                ),
                followers=[{"gid": f["gid"], "name": f["name"]} for f in task.get("followers", [])],
                memberships=task.get("memberships", []),
                is_public=False,
            )

            # Add permission metadata to entity
            entity.sync_metadata = entity.sync_metadata or {}
            entity.sync_metadata["permissions"] = permission_metadata.model_dump()

            yield entity

    async def _generate_file_entities(
        self,
        client: httpx.AsyncClient,
        task: Dict,
        task_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Generate file attachment entities for a task."""
        attachments_data = await self._get_with_auth(client, f"tasks/{task['gid']}/attachments")

        if attachments_data is None:
            return

        for attachment in attachments_data.get("data", []):
            attachment_response = await self._get_with_auth(
                client, f"attachments/{attachment['gid']}"
            )

            attachment_detail = attachment_response.get("data")

            if (
                "download_url" not in attachment_detail
                or attachment_detail.get("download_url") is None
            ):
                logger.warning(
                    f"No download URL found for attachment {attachment['gid']} "
                    f"in task {task['gid']}"
                )
                continue

            # Create the file entity with metadata
            file_entity = AsanaFileEntity(
                entity_id=attachment_detail["gid"],
                breadcrumbs=task_breadcrumbs,
                file_id=attachment["gid"],
                name=attachment_detail.get("name"),
                mime_type=attachment_detail.get("mime_type"),
                size=attachment_detail.get("size"),
                total_size=attachment_detail.get("size"),  # Set total_size from API response
                download_url=attachment_detail.get("download_url"),
                created_at=attachment_detail.get("created_at"),
                modified_at=attachment_detail.get("modified_at"),
                task_gid=task["gid"],
                task_name=task["name"],
                resource_type=attachment_detail.get("resource_type"),
                host=attachment_detail.get("host"),
                parent=attachment_detail.get("parent"),
                view_url=attachment_detail.get("view_url"),
                permanent=attachment_detail.get("permanent", False),
            )

            # Add permission metadata using Pydantic model (inherit from task)
            permission_metadata = AsanaPermissionMetadata(
                workspace_gid=(
                    task.get("workspace", {}).get("gid") if task.get("workspace") else None
                ),
                created_by_gid=(
                    attachment_detail.get("created_by", {}).get("gid")
                    if attachment_detail.get("created_by")
                    else None
                ),
                assigned_to_gid=(
                    task.get("assignee", {}).get("gid") if task.get("assignee") else None
                ),
                followers=[{"gid": f["gid"], "name": f["name"]} for f in task.get("followers", [])],
                memberships=task.get("memberships", []),
                is_public=task.get("public", False),
            )

            # Add permission metadata to entity
            file_entity.sync_metadata = file_entity.sync_metadata or {}
            file_entity.sync_metadata["permissions"] = permission_metadata.model_dump()

            # Different headers based on URL type
            headers = None
            if file_entity.download_url.startswith(self.BASE_URL.replace("/api/1.0", "")):
                headers = {"Authorization": f"Bearer {self.access_token}"}

            # Use the new method with retry for robustness
            file_stream = file_manager.stream_file_from_url(
                file_entity.download_url, headers=headers
            )
            yield await file_manager.handle_file_entity(stream=file_stream, entity=file_entity)

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate all entities from Asana."""
        async with httpx.AsyncClient() as client:
            async for workspace_entity in self._generate_workspace_entities(client):
                yield workspace_entity

                workspace_breadcrumb = Breadcrumb(
                    entity_id=workspace_entity.asana_gid,
                    name=workspace_entity.name,
                    type="workspace",
                )

                async for project_entity in self._generate_project_entities(
                    client,
                    {"gid": workspace_entity.asana_gid, "name": workspace_entity.name},
                    workspace_breadcrumb,
                ):
                    yield project_entity

                    project_breadcrumb = Breadcrumb(
                        entity_id=project_entity.entity_id, name=project_entity.name, type="project"
                    )
                    project_breadcrumbs = [workspace_breadcrumb, project_breadcrumb]

                    async for section_entity in self._generate_section_entities(
                        client,
                        {"gid": project_entity.entity_id},
                        project_breadcrumbs,
                    ):
                        yield section_entity

                        # Generate tasks within section with full breadcrumb path
                        async for task_entity in self._generate_task_entities(
                            client,
                            {"gid": project_entity.entity_id},
                            {"gid": section_entity.entity_id, "name": section_entity.name},
                            project_breadcrumbs,
                        ):
                            yield task_entity

                            # Generate file attachments for the task
                            task_breadcrumb = Breadcrumb(
                                entity_id=task_entity.entity_id,
                                name=task_entity.name,
                                type="task",
                            )
                            task_breadcrumbs = [*project_breadcrumbs, task_breadcrumb]

                            async for file_entity in self._generate_file_entities(
                                client,
                                task=task_entity.model_dump(),
                                task_breadcrumbs=task_breadcrumbs,
                            ):
                                yield file_entity

                    # Generate tasks not in any section
                    async for task_entity in self._generate_task_entities(
                        client,
                        {"gid": project_entity.entity_id},
                        breadcrumbs=project_breadcrumbs,
                    ):
                        yield task_entity

                        # Generate file attachments for the task
                        task_breadcrumb = Breadcrumb(
                            entity_id=task_entity.entity_id,
                            name=task_entity.name,
                            type="task",
                        )
                        task_breadcrumbs = [*project_breadcrumbs, task_breadcrumb]

                        async for file_entity in self._generate_file_entities(
                            client,
                            task=task_entity.model_dump(),
                            task_breadcrumbs=task_breadcrumbs,
                        ):
                            yield file_entity
