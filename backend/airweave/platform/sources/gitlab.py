"""GitLab source implementation for syncing projects, files, issues, and merge requests."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import GitLabAuthConfig
from airweave.platform.configs.config import GitLabConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.gitlab import (
    GitLabCodeFileEntity,
    GitLabDirectoryEntity,
    GitLabIssueEntity,
    GitLabMergeRequestEntity,
    GitLabProjectEntity,
    GitLabUserEntity,
    _require_gl_datetime,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.utils.file_extensions import (
    get_language_for_extension,
    is_text_file,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="GitLab",
    short_name="gitlab",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_REFRESH,
    auth_config_class=GitLabAuthConfig,
    config_class=GitLabConfig,
    labels=["Code"],
    supports_continuous=False,
    supports_temporal_relevance=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class GitLabSource(BaseSource):
    """GitLab source connector integrates with the GitLab REST API to extract data.

    Connects to your GitLab projects.

    It supports syncing projects, users, repository files, issues, and merge requests
    with configurable filtering options for branches and file types.
    """

    BASE_URL = "https://gitlab.com/api/v4"

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: GitLabConfig,
    ) -> GitLabSource:
        """Create a new source instance with authentication."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        instance.project_id = config.project_id or None
        instance.branch = config.branch or ""
        return instance

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _authed_headers(self) -> Dict[str, str]:
        """Build Authorization + Accept headers with a fresh token."""
        token = await self.auth.get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }

    async def _refresh_and_get_headers(self) -> Dict[str, str]:
        """Force-refresh the token and return updated headers."""
        new_token = await self.auth.force_refresh()
        return {
            "Authorization": f"Bearer {new_token}",
            "Accept": "application/json",
        }

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make authenticated API request using OAuth access token."""
        headers = await self._authed_headers()
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            self.logger.warning(f"Received 401 for {url}, refreshing token...")
            headers = await self._refresh_and_get_headers()
            response = await self.http_client.get(url, headers=headers, params=params)

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _get_paginated_results(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get all pages of results from a paginated GitLab API endpoint."""
        if params is None:
            params = {}

        params["per_page"] = 100

        all_results = []
        page = 1

        while True:
            params["page"] = page
            headers = await self._authed_headers()

            response = await self.http_client.get(url, headers=headers, params=params)

            if response.status_code == 401 and self.auth.supports_refresh:
                self.logger.warning(f"Received 401 for {url}, refreshing token...")
                headers = await self._refresh_and_get_headers()
                response = await self.http_client.get(url, headers=headers, params=params)

            raise_for_status(
                response,
                source_short_name=self.short_name,
                token_provider_kind=self.auth.provider_kind,
            )

            results = response.json()
            if not results:
                break

            all_results.extend(results)

            if "x-next-page" not in response.headers or not response.headers["x-next-page"]:
                break

            page += 1

        return all_results

    def _detect_language_from_extension(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        return get_language_for_extension(ext)

    async def _get_current_user(self) -> GitLabUserEntity:
        """Get current authenticated user information."""
        url = f"{self.BASE_URL}/user"
        user_data = await self._get(url)

        return GitLabUserEntity(
            breadcrumbs=[],
            user_id=user_data["id"],
            name=user_data["name"],
            created_at=_require_gl_datetime(user_data.get("created_at"), "user.created_at"),
            username=user_data["username"],
            state=user_data["state"],
            avatar_url=user_data.get("avatar_url"),
            profile_url=user_data.get("web_url"),
            bio=user_data.get("bio"),
            location=user_data.get("location"),
            public_email=user_data.get("public_email"),
            organization=user_data.get("organization"),
            job_title=user_data.get("job_title"),
            pronouns=user_data.get("pronouns"),
        )

    async def _get_project_info(self, project_id: str) -> GitLabProjectEntity:
        """Get project information."""
        url = f"{self.BASE_URL}/projects/{project_id}"
        project_data = await self._get(url)
        return GitLabProjectEntity.from_api(project_data)

    async def _get_project_issues(
        self, project_id: str, project_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Get issues for a project."""
        url = f"{self.BASE_URL}/projects/{project_id}/issues"
        issues = await self._get_paginated_results(url)

        for issue in issues:
            yield GitLabIssueEntity.from_api(
                issue, project_id=str(project_id), breadcrumbs=project_breadcrumbs
            )

    async def _get_project_merge_requests(
        self, project_id: str, project_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Get merge requests for a project."""
        url = f"{self.BASE_URL}/projects/{project_id}/merge_requests"
        merge_requests = await self._get_paginated_results(url)

        for mr in merge_requests:
            yield GitLabMergeRequestEntity.from_api(
                mr, project_id=str(project_id), breadcrumbs=project_breadcrumbs
            )

    async def _traverse_repository(
        self,
        project_id: str,
        project_path: str,
        branch: str,
        project_breadcrumbs: List[Breadcrumb],
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Traverse repository contents using DFS."""
        processed_paths: set = set()

        async for entity in self._traverse_directory(
            project_id, project_path, "", branch, project_breadcrumbs, processed_paths, files
        ):
            yield entity

    async def _traverse_directory(
        self,
        project_id: str,
        project_path: str,
        path: str,
        branch: str,
        breadcrumbs: List[Breadcrumb],
        processed_paths: set,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Recursively traverse a directory using DFS."""
        if path in processed_paths:
            return

        processed_paths.add(path)

        url = f"{self.BASE_URL}/projects/{project_id}/repository/tree"
        params = {"ref": branch, "path": path, "per_page": 100}

        try:
            contents = await self._get_paginated_results(url, params)

            for item in contents:
                item_path = item["path"]
                item_type = item["type"]

                if item_type == "tree":
                    dir_entity = GitLabDirectoryEntity(
                        breadcrumbs=breadcrumbs.copy(),
                        full_path=f"{project_id}/{item_path}",
                        name=Path(item_path).name or item_path,
                        path=item_path,
                        project_id=str(project_id),
                        project_path=project_path,
                        branch=branch,
                        web_url_value=f"https://gitlab.com/{project_path}/-/tree/{branch}/{item_path}",
                    )

                    dir_breadcrumb = Breadcrumb(
                        entity_id=dir_entity.full_path,
                        name=dir_entity.name,
                        entity_type=GitLabDirectoryEntity.__name__,
                    )

                    yield dir_entity

                    dir_breadcrumbs = breadcrumbs.copy() + [dir_breadcrumb]

                    async for child_entity in self._traverse_directory(
                        project_id,
                        project_path,
                        item_path,
                        branch,
                        dir_breadcrumbs,
                        processed_paths,
                        files,
                    ):
                        yield child_entity

                elif item_type == "blob":
                    async for file_entity in self._process_file(
                        project_id, project_path, item_path, branch, breadcrumbs, files
                    ):
                        yield file_entity

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error traversing path {path}: {str(e)}")

    async def _process_file(  # noqa: C901
        self,
        project_id: str,
        project_path: str,
        file_path: str,
        branch: str,
        breadcrumbs: List[Breadcrumb],
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a file item and create file entities."""
        try:
            encoded_path = file_path.replace("/", "%2F")
            url = f"{self.BASE_URL}/projects/{project_id}/repository/files/{encoded_path}"
            params = {"ref": branch}

            file_data = await self._get(url, params)
            file_size = file_data.get("size", 0)

            content_sample = None
            content_text = None

            if file_data.get("encoding") == "base64" and file_data.get("content"):
                try:
                    content_bytes = base64.b64decode(file_data["content"])
                    content_sample = content_bytes[:1024]
                    content_text = content_bytes.decode("utf-8", errors="replace")
                except Exception:
                    pass

            if is_text_file(file_path, file_size, content_sample):
                language = self._detect_language_from_extension(file_path)
                file_name = Path(file_path).name

                line_count = 0
                if content_text:
                    try:
                        line_count = content_text.count("\n") + 1
                    except Exception as e:
                        self.logger.warning(f"Error counting lines for {file_path}: {str(e)}")

                mime_type = mimetypes.guess_type(file_path)[0] or "text/plain"
                file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

                file_entity = GitLabCodeFileEntity(
                    breadcrumbs=breadcrumbs.copy(),
                    full_path=f"{project_id}/{file_path}",
                    name=file_name,
                    branch=branch,
                    url=f"https://gitlab.com/{project_path}/-/raw/{branch}/{file_path}",
                    size=file_size,
                    file_type=file_type,
                    mime_type=mime_type,
                    local_path=None,
                    repo_name=project_path.split("/")[-1],
                    path_in_repo=file_path,
                    repo_owner="/".join(project_path.split("/")[:-1]) or project_path,
                    language=language,
                    commit_id=file_data["blob_id"],
                    blob_id=file_data["blob_id"],
                    project_id=str(project_id),
                    project_path=project_path,
                    line_count=line_count,
                    web_url_value=f"https://gitlab.com/{project_path}/-/blob/{branch}/{file_path}",
                )

                if files:
                    await files.save_bytes(
                        entity=file_entity,
                        content=content_text.encode("utf-8"),
                        filename_with_extension=file_path,
                        logger=self.logger,
                    )

                    if not file_entity.local_path:
                        raise ValueError(f"Save failed - no local path set for {file_entity.name}")

                yield file_entity

        except FileSkippedException as e:
            self.logger.debug(f"Skipping file: {e.reason}")

        except SourceAuthError:
            raise

        except Exception as e:
            self.logger.warning(f"Error processing file {file_path}: {str(e)}")

    async def _get_projects(self) -> List[GitLabProjectEntity]:
        """Get accessible projects based on configuration."""
        if hasattr(self, "project_id") and self.project_id:
            return [await self._get_project_info(self.project_id)]

        url = f"{self.BASE_URL}/projects"
        params = {"membership": True, "simple": False}
        projects_data = await self._get_paginated_results(url, params)
        projects = []
        for proj_data in projects_data:
            try:
                project = await self._get_project_info(str(proj_data["id"]))
                projects.append(project)
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(f"Failed to get project {proj_data.get('id')}: {e}")
        return projects

    async def _process_project(  # noqa: C901
        self,
        project: GitLabProjectEntity,
        project_breadcrumbs: List[Breadcrumb],
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a single project and yield all its entities."""
        branch = (
            self.branch
            if hasattr(self, "branch") and self.branch
            else project.default_branch or "main"
        )

        self.logger.debug(f"Processing project {project.path_with_namespace} on branch {branch}")

        project_id = str(project.project_id)

        if not project.empty_repo:
            try:
                async for entity in self._traverse_repository(
                    project_id,
                    project.path_with_namespace,
                    branch,
                    project_breadcrumbs,
                    files,
                ):
                    yield entity
            except SourceAuthError:
                raise
            except Exception as e:
                self.logger.warning(
                    f"Failed to traverse repository for {project.path_with_namespace}: {e}"
                )

        try:
            async for issue in self._get_project_issues(project_id, project_breadcrumbs):
                yield issue
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Failed to get issues for {project.path_with_namespace}: {e}")

        try:
            async for mr in self._get_project_merge_requests(project_id, project_breadcrumbs):
                yield mr
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Failed to get MRs for {project.path_with_namespace}: {e}")

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from GitLab."""
        user_entity = await self._get_current_user()
        yield user_entity

        projects = await self._get_projects()

        for project in projects:
            yield project

            project_breadcrumb = Breadcrumb(
                entity_id=str(project.project_id),
                name=project.name,
                entity_type=GitLabProjectEntity.__name__,
            )
            project_breadcrumbs = [project_breadcrumb]

            async for entity in self._process_project(project, project_breadcrumbs, files):
                yield entity

    async def validate(self) -> None:
        """Validate credentials by pinging GitLab's /user endpoint."""
        await self._get(f"{self.BASE_URL}/user")
