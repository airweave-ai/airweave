"""Todoist source implementation."""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.todoist import (
    TodoistCommentEntity,
    TodoistProjectEntity,
    TodoistSectionEntity,
    TodoistTaskEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


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
    config_class="TodoistConfig",
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
    async def create(cls, access_token, config: Optional[Dict[str, Any]] = None) -> "TodoistSource":
        """Create a new Todoist source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Any]:
        """Make an authenticated GET request to the Todoist API.

        Returns the JSON response (dict or list).
        If a 404 error is encountered, returns None instead of raising an exception.
        """
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()

            try:
                return response.json()
            except ValueError:
                return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def _get_all_paginated(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict]:
        """Fetch all pages from a paginated Todoist API v1 endpoint.

        The new Todoist API v1 returns paginated responses:
            {"results": [...], "next_cursor": "..." | null}

        This helper follows next_cursor until all pages are collected.
        """
        all_items: List[Dict] = []
        request_params = dict(params) if params else {}

        while True:
            data = await self._get_with_auth(client, url, params=request_params)
            if not data:
                break

            # Handle both paginated dict responses and legacy list responses
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

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse Todoist ISO8601 timestamp strings into datetime objects."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    async def _generate_project_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[TodoistProjectEntity, None]:
        """Retrieve and yield Project entities.

        GET https://api.todoist.com/api/v1/projects
        """
        url = "https://api.todoist.com/api/v1/projects"
        projects = await self._get_all_paginated(client, url)
        if not projects:
            return

        for project in projects:
            now = datetime.utcnow()
            project_url = project.get("url")
            yield TodoistProjectEntity(
                # Base fields
                entity_id=project["id"],
                breadcrumbs=[],
                name=project["name"],
                created_at=now,
                updated_at=now,
                # API fields
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
        client: httpx.AsyncClient,
        project_id: str,
        project_name: str,
        project_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[TodoistSectionEntity, None]:
        """Retrieve and yield Section entities for a given project.

        GET https://api.todoist.com/api/v1/sections?project_id={project_id}
        """
        url = "https://api.todoist.com/api/v1/sections"
        sections = await self._get_all_paginated(client, url, {"project_id": project_id})
        if not sections:
            return

        for section in sections:
            now = datetime.utcnow()
            yield TodoistSectionEntity(
                # Base fields
                entity_id=section["id"],
                breadcrumbs=[project_breadcrumb],
                name=section["name"],
                created_at=now,
                updated_at=now,
                # API fields
                section_id=section["id"],
                section_name=section["name"],
                project_id=section["project_id"],
                order=section.get("order", 0),
            )

    async def _fetch_all_tasks_for_project(
        self, client: httpx.AsyncClient, project_id: str
    ) -> List[Dict]:
        """Fetch all tasks for a given project.

        GET https://api.todoist.com/api/v1/tasks?project_id={project_id}

        Returns a list of task objects.
        """
        url = "https://api.todoist.com/api/v1/tasks"
        return await self._get_all_paginated(client, url, {"project_id": project_id})

    async def _generate_task_entities(
        self,
        client: httpx.AsyncClient,
        project_id: str,
        section_id: Optional[str],
        all_tasks: List[Dict],
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[TodoistTaskEntity, None]:
        """Retrieve and yield Task entities.

        Yield task entities for either
          - tasks that belong to a given section, if section_id is provided
          - tasks that have no section, if section_id is None

        We assume 'all_tasks' is the full list of tasks for the project.
        """
        for task in all_tasks:
            # Determine if this task matches the requested (section_id or None).
            if section_id is None:
                # We yield tasks that have no section (section_id=None).
                if task.get("section_id") is not None:
                    continue
            else:
                # We yield tasks that match the provided section_id.
                if task.get("section_id") != section_id:
                    continue

            # Extract duration information if present
            duration_amount = None
            duration_unit = None
            if task.get("duration"):
                duration_amount = task["duration"].get("amount")
                duration_unit = task["duration"].get("unit")

            # Extract deadline information if present
            deadline_date = None
            if task.get("deadline"):
                deadline_date = task["deadline"].get("date")

            task_id = task["id"]
            task_name = task.get("content") or f"Task {task_id}"
            created_time = self._parse_datetime(task.get("created_at")) or datetime.utcnow()
            updated_time = created_time
            task_url = task.get("url")

            yield TodoistTaskEntity(
                # Base fields
                entity_id=task_id,
                breadcrumbs=breadcrumbs,
                name=task_name,
                created_at=created_time,
                updated_at=updated_time,
                # API fields
                task_id=task_id,
                content=task_name,
                created_time=created_time,
                updated_time=updated_time,
                web_url_value=task_url,
                description=task.get("description"),
                is_completed=task.get("completed_at") is not None
                if "completed_at" in task
                else task.get("is_completed", False),
                completed_at=task.get("completed_at"),
                labels=task.get("labels", []),
                order=task.get("order", 0),
                priority=task.get("priority", 1),
                project_id=task.get("project_id"),
                section_id=task.get("section_id"),
                parent_id=task.get("parent_id"),
                creator_id=task.get("creator_id"),
                assignee_id=task.get("assignee_id"),
                assigner_id=task.get("assigner_id"),
                due_date=(task["due"]["date"] if task.get("due") else None),
                due_datetime=(
                    task["due"]["datetime"]
                    if (task.get("due") and task["due"].get("datetime"))
                    else None
                ),
                due_string=(task["due"]["string"] if task.get("due") else None),
                due_is_recurring=(task["due"]["is_recurring"] if task.get("due") else False),
                due_timezone=(
                    task["due"].get("timezone")
                    if (task.get("due") and "timezone" in task["due"])
                    else None
                ),
                deadline_date=deadline_date,
                duration_amount=duration_amount,
                duration_unit=duration_unit,
                url=task_url,
            )

    async def _generate_comment_entities(
        self,
        client: httpx.AsyncClient,
        task_entity: TodoistTaskEntity,
        task_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[TodoistCommentEntity, None]:
        """Retrieve and yield Comment entities for a given task.

        GET https://api.todoist.com/api/v1/comments?task_id={task_id}
        """
        task_id = task_entity.entity_id
        url = "https://api.todoist.com/api/v1/comments"
        comments = await self._get_all_paginated(client, url, {"task_id": task_id})
        if not comments:
            return

        for comment in comments:
            # Create comment name from content preview
            content = comment.get("content", "")
            comment_name = content[:50] + "..." if len(content) > 50 else content
            if not comment_name:
                comment_name = f"Comment {comment['id']}"

            posted_at_dt = self._parse_datetime(comment.get("posted_at")) or datetime.utcnow()

            yield TodoistCommentEntity(
                # Base fields
                entity_id=comment["id"],
                breadcrumbs=task_breadcrumbs,
                name=comment_name,
                created_at=posted_at_dt,
                updated_at=posted_at_dt,
                # API fields
                comment_id=comment["id"],
                task_id=str(comment.get("task_id") or ""),
                content=content,
                posted_at=posted_at_dt,
            )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Todoist: Projects, Sections, Tasks, and Comments.

        For each project:
          - yield a TodoistProjectEntity
          - yield TodoistSectionEntities
          - fetch all tasks for that project once
          - yield tasks that fall under each section
          - yield tasks not associated with any section
          - yield TodoistCommentEntities for each task
        """
        async with self.http_client() as client:
            # 1) Generate (and yield) all Projects
            async for project_entity in self._generate_project_entities(client):
                yield project_entity

                # Create a breadcrumb for this project
                project_breadcrumb = Breadcrumb(
                    entity_id=project_entity.entity_id,
                    name=project_entity.name,
                    entity_type=TodoistProjectEntity.__name__,
                )

                # 2) Generate (and yield) all Sections for this project
                async for section_entity in self._generate_section_entities(
                    client,
                    project_entity.entity_id,
                    project_entity.name,
                    project_breadcrumb,
                ):
                    yield section_entity

                # Prepare to retrieve tasks for this project,
                # so we only make one request per project.
                all_tasks = await self._fetch_all_tasks_for_project(
                    client, project_entity.entity_id
                )

                # Re-fetch sections in-memory to attach tasks to them
                sections = await self._get_all_paginated(
                    client,
                    "https://api.todoist.com/api/v1/sections",
                    {"project_id": project_entity.entity_id},
                )

                # 3) For each section, yield tasks that belong to it, plus comments
                for section_data in sections:
                    section_breadcrumb = Breadcrumb(
                        entity_id=section_data["id"],
                        name=section_data.get("name", "Section"),
                        entity_type=TodoistSectionEntity.__name__,
                    )
                    project_section_breadcrumbs = [project_breadcrumb, section_breadcrumb]

                    async for task_entity in self._generate_task_entities(
                        client,
                        project_entity.entity_id,
                        section_data["id"],
                        all_tasks,
                        project_section_breadcrumbs,
                    ):
                        yield task_entity
                        # generate comments for each task
                        task_breadcrumb = Breadcrumb(
                            entity_id=task_entity.entity_id,
                            name=task_entity.name,
                            entity_type=TodoistTaskEntity.__name__,
                        )
                        async for comment_entity in self._generate_comment_entities(
                            client,
                            task_entity,
                            project_section_breadcrumbs + [task_breadcrumb],
                        ):
                            yield comment_entity

                # 4) Generate tasks for this project that are NOT in any section
                async for task_entity in self._generate_task_entities(
                    client,
                    project_entity.entity_id,
                    section_id=None,
                    all_tasks=all_tasks,
                    breadcrumbs=[project_breadcrumb],
                ):
                    yield task_entity
                    # generate comments for each of these tasks as well
                    task_breadcrumb = Breadcrumb(
                        entity_id=task_entity.entity_id,
                        name=task_entity.name,
                        entity_type=TodoistTaskEntity.__name__,
                    )
                    async for comment_entity in self._generate_comment_entities(
                        client,
                        task_entity,
                        [project_breadcrumb, task_breadcrumb],
                    ):
                        yield comment_entity

    async def validate(self) -> bool:
        """Verify Todoist OAuth2 token by pinging a lightweight REST endpoint."""
        return await self._validate_oauth2(
            ping_url="https://api.todoist.com/api/v1/projects",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
