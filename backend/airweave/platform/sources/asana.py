"""Asana source implementation for syncing workspaces, projects, tasks, and comments."""

from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceEntityForbiddenError,
    SourceEntityNotFoundError,
    SourceError,
)
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
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
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

_API = "https://app.asana.com/api/1.0"


class _ResultTooLarge(Exception):
    """Asana returned 400 indicating the response payload exceeds internal limits."""


_WORKSPACE_FIELDS = "gid,name,is_organization,email_domains,resource_type"

_PROJECT_FIELDS = (
    "gid,name,color,archived,created_at,modified_at,"
    "current_status,current_status.text,current_status.color,"
    "default_view,due_on,html_notes,notes,public,start_on,"
    "owner,owner.name,team,team.name,members,members.name,"
    "followers,followers.name,custom_fields,custom_field_settings,"
    "default_access_level,icon,permalink_url"
)

_SECTION_FIELDS = "gid,name,created_at,projects,projects.name"

_TASK_FIELDS = (
    "gid,name,actual_time_minutes,approval_status,"
    "assignee,assignee.name,assignee_status,completed,"
    "completed_at,completed_by,completed_by.name,"
    "created_at,modified_at,dependencies,dependents,"
    "due_at,due_on,start_at,start_on,external,"
    "html_notes,notes,is_rendered_as_separator,liked,"
    "memberships,num_likes,num_subtasks,parent,parent.name,"
    "permalink_url,resource_subtype,tags,tags.name,"
    "custom_fields,followers,followers.name,workspace,workspace.name"
)

_STORY_FIELDS = (
    "gid,created_at,created_by,created_by.name,"
    "resource_subtype,text,html_text,is_pinned,"
    "is_edited,sticker_name,num_likes,liked,type,previews"
)

_ATTACHMENT_LIST_FIELDS = "gid,name,resource_type"

_ATTACHMENT_DETAIL_FIELDS = (
    "gid,name,resource_type,created_at,modified_at,"
    "download_url,permanent,host,parent,parent.name,"
    "size,view_url,mime_type"
)


@source(
    name="Asana",
    short_name="asana",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=None,
    config_class=AsanaConfig,
    labels=["Project Management"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class AsanaSource(BaseSource):
    """Asana source connector — syncs workspaces, projects, tasks, sections, comments, files."""

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: AsanaConfig,
    ) -> AsanaSource:
        """Create a new Asana source instance."""
        return cls(auth=auth, logger=logger, http_client=http_client)

    # ------------------------------------------------------------------
    # HTTP
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict:
        """Authenticated GET with retry on 429/5xx/timeout and 401 refresh."""
        token = await self.auth.get_token()
        headers = {"Authorization": f"Bearer {token}"}
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers = {"Authorization": f"Bearer {new_token}"}
            response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 400 and "too large" in response.text.lower():
            raise _ResultTooLarge()

        try:
            raise_for_status(
                response,
                source_short_name=self.short_name,
                token_provider_kind=self.auth.provider_kind,
            )
        except SourceAuthError as e:
            self.logger.warning(f"Failed to fetch data from {url}: {e}")
            raise
        return response.json()

    async def _paginate(
        self,
        url: str,
        opt_fields: str,
        limit: int = 100,
        _min_limit: int = 10,
        _offset: str | None = None,
    ) -> AsyncGenerator[Dict, None]:
        """Paginate through Asana list endpoints, yielding each item.

        If Asana returns 400 "result too large" (payload exceeds internal
        limits despite pagination), halves the page size and retries
        recursively down to ``_min_limit``.
        """
        offset: str | None = _offset

        while True:
            params: Dict[str, Any] = {"opt_fields": opt_fields, "limit": limit}
            if offset:
                params["offset"] = offset

            try:
                data = await self._get(url, params=params)
            except _ResultTooLarge:
                if limit > _min_limit:
                    smaller = max(limit // 2, _min_limit)
                    self.logger.warning(
                        f"Result too large at limit={limit}, retrying at limit={smaller}"
                    )
                    async for item in self._paginate(
                        url, opt_fields, limit=smaller, _min_limit=_min_limit, _offset=offset
                    ):
                        yield item
                    return
                raise

            for item in data.get("data", []):
                yield item

            next_page = data.get("next_page")
            if next_page and next_page.get("offset"):
                offset = next_page["offset"]
            else:
                return

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _generate_workspaces(self) -> AsyncGenerator[AsanaWorkspaceEntity, None]:
        """Generate workspace entities."""
        data = await self._get(f"{_API}/workspaces", params={"opt_fields": _WORKSPACE_FIELDS})
        for ws in data.get("data", []):
            yield AsanaWorkspaceEntity.from_api(ws)

    async def _generate_projects(
        self, workspace: Dict, breadcrumb: Breadcrumb
    ) -> AsyncGenerator[AsanaProjectEntity, None]:
        """Generate project entities for a workspace."""
        data = await self._get(
            f"{_API}/workspaces/{workspace['gid']}/projects",
            params={"opt_fields": _PROJECT_FIELDS},
        )
        for project in data.get("data", []):
            yield AsanaProjectEntity.from_api(
                project, workspace=workspace, breadcrumbs=[breadcrumb]
            )

    async def _generate_sections(
        self, project_gid: str, breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[AsanaSectionEntity, None]:
        """Generate section entities for a project."""
        data = await self._get(
            f"{_API}/projects/{project_gid}/sections",
            params={"opt_fields": _SECTION_FIELDS},
        )
        for section in data.get("data", []):
            yield AsanaSectionEntity.from_api(
                section, project_gid=project_gid, breadcrumbs=breadcrumbs
            )

    async def _generate_tasks(
        self,
        project_gid: str,
        breadcrumbs: List[Breadcrumb],
        section: Optional[Dict] = None,
    ) -> AsyncGenerator[AsanaTaskEntity, None]:
        """Generate task entities with pagination."""
        url = (
            f"{_API}/sections/{section['gid']}/tasks"
            if section
            else f"{_API}/projects/{project_gid}/tasks"
        )
        section_gid = section["gid"] if section else None

        task_breadcrumbs = breadcrumbs
        if section:
            task_breadcrumbs = [
                *breadcrumbs,
                Breadcrumb(
                    entity_id=section["gid"],
                    name=section["name"],
                    entity_type="AsanaSectionEntity",
                ),
            ]

        async for task in self._paginate(url, _TASK_FIELDS):
            yield AsanaTaskEntity.from_api(
                task,
                project_gid=project_gid,
                breadcrumbs=task_breadcrumbs,
                section_gid=section_gid,
            )

    async def _generate_comments(
        self, task_gid: str, breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[AsanaCommentEntity, None]:
        """Generate comment entities for a task."""
        data = await self._get(
            f"{_API}/tasks/{task_gid}/stories",
            params={"opt_fields": _STORY_FIELDS},
        )
        for story in data.get("data", []):
            if story.get("resource_subtype") != "comment_added":
                continue
            yield AsanaCommentEntity.from_api(story, task_gid=task_gid, breadcrumbs=breadcrumbs)

    # ------------------------------------------------------------------
    # Attachments
    # ------------------------------------------------------------------

    async def _generate_attachments(
        self,
        task: Dict,
        breadcrumbs: List[Breadcrumb],
        files: FileService,
    ) -> AsyncGenerator[AsanaFileEntity, None]:
        """List and download file attachments for a task."""
        data = await self._get(
            f"{_API}/tasks/{task['gid']}/attachments",
            params={"opt_fields": _ATTACHMENT_LIST_FIELDS},
        )
        for stub in data.get("data", []):
            entity = await self._fetch_and_download_attachment(
                stub["gid"], task, breadcrumbs, files
            )
            if entity:
                yield entity

    async def _fetch_attachment_detail(self, gid: str) -> Optional[Dict]:
        """Fetch full attachment metadata. Returns None on 403/404."""
        try:
            resp = await self._get(
                f"{_API}/attachments/{gid}",
                params={"opt_fields": _ATTACHMENT_DETAIL_FIELDS},
            )
            return resp.get("data")
        except (SourceEntityForbiddenError, SourceEntityNotFoundError) as exc:
            self.logger.warning(f"Skipping attachment {gid}: {exc}")
            return None

    def _build_file_entity(
        self, detail: Dict, task: Dict, breadcrumbs: List[Breadcrumb]
    ) -> AsanaFileEntity:
        """Construct AsanaFileEntity from attachment detail dict."""
        mime_type = detail.get("mime_type", "application/octet-stream")
        project_gid = next(
            (bc.entity_id for bc in breadcrumbs if bc.entity_type == "AsanaProjectEntity"),
            None,
        )
        return AsanaFileEntity(
            **detail,
            breadcrumbs=breadcrumbs,
            url=detail.get("download_url"),
            file_type=mime_type.split("/")[0] if "/" in mime_type else "file",
            mime_type=mime_type,
            local_path=None,
            task_gid=task["gid"],
            task_name=task["name"],
            project_gid=project_gid,
        )

    async def _download_attachment(
        self, entity: AsanaFileEntity, files: FileService
    ) -> AsanaFileEntity | None:
        """Download an attachment via FileService. Returns None on expected skips.

        401 after refresh propagates (token is dead → abort sync).
        Infrastructure failures (IOError, OSError) propagate.
        Other HTTP errors (429 exhausted, 5xx, 403, 404) skip the file.
        """
        try:
            await files.download_from_url(
                entity=entity,
                client=self.http_client,
                auth=self.auth,
                logger=self.logger,
            )
            if not entity.local_path:
                self.logger.warning(f"Download produced no local path for {entity.name}")
                return None
            return entity
        except FileSkippedException as e:
            self.logger.debug(f"Skipping attachment {entity.gid}: {e.reason}")
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise
            self.logger.warning(
                f"HTTP {e.response.status_code} downloading attachment {entity.gid}: {e}"
            )
            return None

    async def _fetch_and_download_attachment(
        self,
        gid: str,
        task: Dict,
        breadcrumbs: List[Breadcrumb],
        files: FileService,
    ) -> AsanaFileEntity | None:
        """Fetch detail → build entity → download. Returns None on any skip."""
        detail = await self._fetch_attachment_detail(gid)
        if not detail or not detail.get("download_url"):
            if detail:
                self.logger.warning(f"No download URL for attachment {gid}")
            return None

        entity = self._build_file_entity(detail, task, breadcrumbs)
        return await self._download_attachment(entity, files)

    # ------------------------------------------------------------------
    # Orchestration helpers
    # ------------------------------------------------------------------

    async def _yield_task_tree(
        self,
        task_entity: AsanaTaskEntity,
        project_breadcrumbs: List[Breadcrumb],
        files: FileService | None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Yield a task entity plus its comments and attachments."""
        yield task_entity

        task_breadcrumbs = [
            *project_breadcrumbs,
            Breadcrumb(
                entity_id=task_entity.gid,
                name=task_entity.name,
                entity_type="AsanaTaskEntity",
            ),
        ]
        task_dict = {"gid": task_entity.gid, "name": task_entity.name}

        try:
            async for comment in self._generate_comments(task_entity.gid, task_breadcrumbs):
                yield comment
        except SourceAuthError:
            raise
        except SourceEntityForbiddenError:
            self.logger.warning(f"No access to comments for task {task_entity.gid}, skipping")
        except SourceError as exc:
            self.logger.warning(f"Failed to fetch comments for task {task_entity.gid}: {exc}")

        if files:
            async for file_entity in self._generate_attachments(task_dict, task_breadcrumbs, files):
                yield file_entity

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Asana."""
        async for ws in self._generate_workspaces():
            yield ws
            ws_bc = Breadcrumb(entity_id=ws.gid, name=ws.name, entity_type="AsanaWorkspaceEntity")
            ws_dict = {"gid": ws.gid, "name": ws.name}

            async for proj in self._generate_projects(ws_dict, ws_bc):
                yield proj
                proj_bc = Breadcrumb(
                    entity_id=proj.gid, name=proj.name, entity_type="AsanaProjectEntity"
                )
                proj_bcs = [ws_bc, proj_bc]

                async for section in self._generate_sections(proj.gid, proj_bcs):
                    yield section
                    sec_dict = {"gid": section.gid, "name": section.name}

                    async for task in self._generate_tasks(proj.gid, proj_bcs, section=sec_dict):
                        async for entity in self._yield_task_tree(task, proj_bcs, files):
                            yield entity

                async for task in self._generate_tasks(proj.gid, proj_bcs):
                    async for entity in self._yield_task_tree(task, proj_bcs, files):
                        yield entity

    async def validate(self) -> None:
        """Validate credentials by pinging Asana's /users/me endpoint."""
        await self._get(f"{_API}/users/me")
