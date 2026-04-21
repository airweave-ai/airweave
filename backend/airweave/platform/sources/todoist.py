"""Todoist source implementation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceEntityNotFoundError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import TodoistConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.todoist import (
    TodoistCommentEntity,
    TodoistProjectEntity,
    TodoistSectionEntity,
    TodoistTaskEntity,
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
    name="Todoist",
    short_name="todoist",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=None,
    config_class=TodoistConfig,
    labels=["Productivity", "Task Management"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class TodoistSource(BaseSource):
    """Todoist source connector integrates with the Todoist REST API to extract task data.

    Connects to your Todoist workspace.

    It provides comprehensive access to projects, tasks, and
    collaboration features with proper hierarchical organization and productivity insights.
    """

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: TodoistConfig,
    ) -> TodoistSource:
        """Create a new Todoist source instance."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Optional[Any]:
        """Make an authenticated GET request to the Todoist API.

        Returns the JSON response, or None on 404.
        """
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.http_client.get(url, headers=headers, params=params)
        try:
            raise_for_status(
                response,
                source_short_name=self.short_name,
                token_provider_kind=self.auth.provider_kind,
            )
        except SourceEntityNotFoundError:
            return None
        return response.json()

    async def _get_all_paginated(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """Fetch all pages from a paginated Todoist API v1 endpoint.

        The Todoist API v1 returns paginated responses:
            {"results": [...], "next_cursor": "..." | null}

        This helper follows next_cursor until all pages are collected.
        """
        all_items: List[Dict] = []
        request_params = dict(params) if params else {}

        while True:
            data = await self._get(url, params=request_params)
            if not data:
                break

            if isinstance(data, list):
                all_items.extend(data)
                break

            results = data.get("results", [])
            if isinstance(results, list):
                all_items.extend(results)

            next_cursor = data.get("next_cursor")
            if not next_cursor:
                break

            request_params["cursor"] = next_cursor

        return all_items

    async def _generate_project_entities(
        self,
    ) -> AsyncGenerator[TodoistProjectEntity, None]:
        """Retrieve and yield Project entities.

        GET https://api.todoist.com/api/v1/projects
        """
        url = "https://api.todoist.com/api/v1/projects"
        projects = await self._get_all_paginated(url)
        if not projects:
            return

        for project in projects:
            now = datetime.utcnow()
            project_url = project.get("url")
            yield TodoistProjectEntity(
                entity_id=project["id"],
                breadcrumbs=[],
                name=project["name"],
                created_at=now,
                updated_at=now,
                project_id=project["id"],
                project_name=project["name"],
                created_time=now,
                updated_time=now,
                web_url_value=project_url,
                color=project.get("color"),
                order=project.get("order", 0),
                is_shared=project.get("is_shared", False),
                is_favorite=project.get("is_favorite", False),
                is_inbox_project=project.get("is_inbox_project", False),
                is_team_inbox=project.get("is_team_inbox", False),
                view_style=project.get("view_style"),
                url=project_url,
                parent_id=project.get("parent_id"),
            )

    async def _generate_section_entities(
        self,
        project_id: str,
        project_name: str,
        project_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[TodoistSectionEntity, None]:
        """Retrieve and yield Section entities for a given project.

        GET https://api.todoist.com/api/v1/sections?project_id={project_id}
        """
        url = "https://api.todoist.com/api/v1/sections"
        sections = await self._get_all_paginated(url, {"project_id": project_id})
        if not sections:
            return

        for section in sections:
            now = datetime.utcnow()
            yield TodoistSectionEntity(
                entity_id=section["id"],
                breadcrumbs=[project_breadcrumb],
                name=section["name"],
                created_at=now,
                updated_at=now,
                section_id=section["id"],
                section_name=section["name"],
                project_id=section["project_id"],
                order=section.get("order", 0),
            )

    async def _fetch_all_tasks_for_project(self, project_id: str) -> List[Dict]:
        """Fetch all tasks for a given project.

        GET https://api.todoist.com/api/v1/tasks?project_id={project_id}
        """
        url = "https://api.todoist.com/api/v1/tasks"
        return await self._get_all_paginated(url, {"project_id": project_id})

    async def _generate_task_entities(
        self,
        project_id: str,
        section_id: Optional[str],
        all_tasks: List[Dict],
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[TodoistTaskEntity, None]:
        """Yield task entities filtered by section_id (or None for unsectioned tasks)."""
        for task in all_tasks:
            if section_id is None:
                if task.get("section_id") is not None:
                    continue
            else:
                if task.get("section_id") != section_id:
                    continue

            yield TodoistTaskEntity.from_api(task, breadcrumbs=breadcrumbs)

    async def _generate_comment_entities(
        self,
        task_entity: TodoistTaskEntity,
        task_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[TodoistCommentEntity, None]:
        """Retrieve and yield Comment entities for a given task.

        GET https://api.todoist.com/api/v1/comments?task_id={task_id}
        """
        task_id = task_entity.entity_id
        url = "https://api.todoist.com/api/v1/comments"
        comments = await self._get_all_paginated(url, {"task_id": task_id})
        if not comments:
            return

        for comment in comments:
            yield TodoistCommentEntity.from_api(comment, breadcrumbs=task_breadcrumbs)

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Todoist: Projects, Sections, Tasks, and Comments."""
        async for project_entity in self._generate_project_entities():
            yield project_entity

            project_breadcrumb = Breadcrumb(
                entity_id=project_entity.entity_id,
                name=project_entity.name,
                entity_type=TodoistProjectEntity.__name__,
            )

            async for section_entity in self._generate_section_entities(
                project_entity.entity_id,
                project_entity.name,
                project_breadcrumb,
            ):
                yield section_entity

            all_tasks = await self._fetch_all_tasks_for_project(project_entity.entity_id)

            sections = await self._get_all_paginated(
                "https://api.todoist.com/api/v1/sections",
                {"project_id": project_entity.entity_id},
            )

            for section_data in sections:
                section_breadcrumb = Breadcrumb(
                    entity_id=section_data["id"],
                    name=section_data.get("name", "Section"),
                    entity_type=TodoistSectionEntity.__name__,
                )
                project_section_breadcrumbs = [project_breadcrumb, section_breadcrumb]

                async for task_entity in self._generate_task_entities(
                    project_entity.entity_id,
                    section_data["id"],
                    all_tasks,
                    project_section_breadcrumbs,
                ):
                    yield task_entity
                    task_breadcrumb = Breadcrumb(
                        entity_id=task_entity.entity_id,
                        name=task_entity.name,
                        entity_type=TodoistTaskEntity.__name__,
                    )
                    async for comment_entity in self._generate_comment_entities(
                        task_entity,
                        project_section_breadcrumbs + [task_breadcrumb],
                    ):
                        yield comment_entity

            async for task_entity in self._generate_task_entities(
                project_entity.entity_id,
                section_id=None,
                all_tasks=all_tasks,
                breadcrumbs=[project_breadcrumb],
            ):
                yield task_entity
                task_breadcrumb = Breadcrumb(
                    entity_id=task_entity.entity_id,
                    name=task_entity.name,
                    entity_type=TodoistTaskEntity.__name__,
                )
                async for comment_entity in self._generate_comment_entities(
                    task_entity,
                    [project_breadcrumb, task_breadcrumb],
                ):
                    yield comment_entity

    async def validate(self) -> None:
        """Validate credentials by pinging the Todoist projects endpoint."""
        await self._get("https://api.todoist.com/api/v1/projects")
