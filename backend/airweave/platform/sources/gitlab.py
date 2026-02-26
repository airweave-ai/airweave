"""GitLab source implementation for syncing projects, files, issues, and merge requests."""

import base64
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
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
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.platform.storage import FileSkippedException
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

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse GitLab ISO8601 timestamps into aware datetimes."""
        if not value:
            return None
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @classmethod
    def _require_datetime(cls, value: Optional[str], field_name: str) -> datetime:
        """Parse a required timestamp, raising if it's missing."""
        parsed = cls._parse_datetime(value)
        if parsed is None:
            raise ValueError(f"GitLab response missing required datetime '{field_name}'.")
        return parsed

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "GitLabSource":
        """Create a new source instance with authentication.

        Args:
            access_token: OAuth access token for GitLab API
            config: Optional source configuration parameters

        Returns:
            Configured GitLab source instance
        """
        instance = cls()
        instance.access_token = access_token

        # Parse config fields
        if config:
            instance.project_id = config.get("project_id")
            instance.branch = config.get("branch", "")
        else:
            instance.project_id = None
            instance.branch = ""

        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated API request using OAuth access token.

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response
        """
        # Get a valid token (will refresh if needed)
        access_token = await self.get_access_token()
        if not access_token:
            raise ValueError("No access token available")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }

        try:
            response = await client.get(url, headers=headers, params=params)

            # Handle 401 Unauthorized - token might have expired
            if response.status_code == 401:
                self.logger.warning(f"Received 401 Unauthorized for {url}, refreshing token...")

                if self.token_manager:
                    try:
                        # Force refresh the token
                        from airweave.core.exceptions import TokenRefreshError

                        new_token = await self.token_manager.refresh_on_unauthorized()
                        headers = {"Authorization": f"Bearer {new_token}"}

                        # Retry with new token
                        self.logger.debug(f"Retrying request with refreshed token: {url}")
                        response = await client.get(url, headers=headers, params=params)

                    except TokenRefreshError as e:
                        self.logger.error(f"Failed to refresh token: {str(e)}")
                        response.raise_for_status()
                else:
                    self.logger.error("No token manager available to refresh expired token")
                    response.raise_for_status()

            response.raise_for_status()
            return response.json()

        except httpx.HTTPStatusError as e:
            self.logger.error(f"HTTP error from GitLab API: {e.response.status_code} for {url}")
            raise
        except Exception as e:
            self.logger.error(f"Unexpected error accessing GitLab API: {url}, {str(e)}")
            raise

    async def _get_paginated_results(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get all pages of results from a paginated GitLab API endpoint.

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            List of all results from all pages
        """
        if params is None:
            params = {}

        # Set per_page to maximum to minimize requests
        params["per_page"] = 100

        all_results = []
        page = 1

        while True:
            params["page"] = page
            token = await self.get_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }

            try:
                response = await client.get(url, headers=headers, params=params)

                # Handle 401 Unauthorized - token might have expired
                if response.status_code == 401:
                    self.logger.warning(f"Received 401 Unauthorized for {url}, refreshing token...")

                    if self.token_manager:
                        try:
                            # Force refresh the token
                            from airweave.core.exceptions import TokenRefreshError

                            new_token = await self.token_manager.refresh_on_unauthorized()
                            headers = {
                                "Authorization": f"Bearer {new_token}",
                                "Accept": "application/json",
                            }

                            # Retry with new token
                            self.logger.debug(
                                f"Retrying paginated request with refreshed token: {url}"
                            )
                            response = await client.get(url, headers=headers, params=params)

                        except TokenRefreshError as e:
                            self.logger.error(f"Failed to refresh token: {str(e)}")
                            response.raise_for_status()
                    else:
                        self.logger.error("No token manager available to refresh expired token")
                        response.raise_for_status()

                response.raise_for_status()

                results = response.json()
                if not results:  # Empty page means we're done
                    break

                all_results.extend(results)

                # Check if there's a next page via header
                if "x-next-page" not in response.headers or not response.headers["x-next-page"]:
                    break

                page += 1

            except httpx.HTTPStatusError as e:
                self.logger.error(f"HTTP error from GitLab API: {e.response.status_code} for {url}")
                raise
            except Exception as e:
                self.logger.error(f"Unexpected error accessing GitLab API: {url}, {str(e)}")
                raise

        return all_results

    def _detect_language_from_extension(self, file_path: str) -> str:
        """Detect programming language from file extension.

        Args:
            file_path: Path to the file

        Returns:
            The detected language name
        """
        ext = Path(file_path).suffix.lower()
        return get_language_for_extension(ext)

    async def _get_current_user(self, client: httpx.AsyncClient) -> GitLabUserEntity:
        """Get current authenticated user information.

        Args:
            client: HTTP client

        Returns:
            User entity for the authenticated user
        """
        url = f"{self.BASE_URL}/user"
        user_data = await self._get_with_auth(client, url)

        return GitLabUserEntity(
            breadcrumbs=[],
            user_id=user_data["id"],
            name=user_data["name"],
            created_at=self._require_datetime(user_data.get("created_at"), "user.created_at"),
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

    async def _get_project_info(
        self, client: httpx.AsyncClient, project_id: str
    ) -> GitLabProjectEntity:
        """Get project information.

        Args:
            client: HTTP client
            project_id: Project ID

        Returns:
            Project entity
        """
        url = f"{self.BASE_URL}/projects/{project_id}"
        project_data = await self._get_with_auth(client, url)

        return GitLabProjectEntity(
            breadcrumbs=[],
            project_id=project_data["id"],
            name=project_data["name"],
            created_at=self._require_datetime(project_data.get("created_at"), "project.created_at"),
            last_activity_at=self._require_datetime(
                project_data.get("last_activity_at")
                or project_data.get("updated_at")
                or project_data.get("created_at"),
                "project.last_activity_at",
            ),
            path=project_data["path"],
            path_with_namespace=project_data["path_with_namespace"],
            description=project_data.get("description"),
            default_branch=project_data.get("default_branch"),
            visibility=project_data["visibility"],
            topics=project_data.get("topics", []),
            namespace=project_data.get("namespace", {}),
            star_count=project_data.get("star_count", 0),
            forks_count=project_data.get("forks_count", 0),
            open_issues_count=project_data.get("open_issues_count", 0),
            archived=project_data.get("archived", False),
            empty_repo=project_data.get("empty_repo", False),
            web_url_value=project_data.get("web_url"),
        )

    async def _get_project_issues(
        self, client: httpx.AsyncClient, project_id: str, project_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Get issues for a project.

        Args:
            client: HTTP client
            project_id: Project ID
            project_breadcrumbs: Breadcrumbs for the project

        Yields:
            Issue entities
        """
        url = f"{self.BASE_URL}/projects/{project_id}/issues"
        issues = await self._get_paginated_results(client, url)

        for issue in issues:
            yield GitLabIssueEntity(
                breadcrumbs=project_breadcrumbs,
                issue_id=issue["id"],
                title=issue["title"],
                created_at=self._require_datetime(issue.get("created_at"), "issue.created_at"),
                updated_at=self._require_datetime(
                    issue.get("updated_at") or issue.get("created_at"),
                    "issue.updated_at",
                ),
                description=issue.get("description"),
                state=issue["state"],
                closed_at=self._parse_datetime(issue.get("closed_at")),
                labels=issue.get("labels", []),
                author=issue.get("author", {}),
                assignees=issue.get("assignees", []),
                milestone=issue.get("milestone"),
                project_id=str(project_id),
                iid=issue["iid"],
                web_url_value=issue.get("web_url"),
                user_notes_count=issue.get("user_notes_count", 0),
                upvotes=issue.get("upvotes", 0),
                downvotes=issue.get("downvotes", 0),
            )

    async def _get_project_merge_requests(
        self, client: httpx.AsyncClient, project_id: str, project_breadcrumbs: List[Breadcrumb]
    ) -> AsyncGenerator[BaseEntity, None]:
        """Get merge requests for a project.

        Args:
            client: HTTP client
            project_id: Project ID
            project_breadcrumbs: Breadcrumbs for the project

        Yields:
            Merge request entities
        """
        url = f"{self.BASE_URL}/projects/{project_id}/merge_requests"
        merge_requests = await self._get_paginated_results(client, url)

        for mr in merge_requests:
            yield GitLabMergeRequestEntity(
                breadcrumbs=project_breadcrumbs,
                merge_request_id=mr["id"],
                title=mr["title"],
                created_at=self._require_datetime(mr.get("created_at"), "merge_request.created_at"),
                updated_at=self._require_datetime(
                    mr.get("updated_at") or mr.get("created_at"),
                    "merge_request.updated_at",
                ),
                description=mr.get("description"),
                state=mr["state"],
                merged_at=self._parse_datetime(mr.get("merged_at")),
                closed_at=self._parse_datetime(mr.get("closed_at")),
                labels=mr.get("labels", []),
                author=mr.get("author", {}),
                assignees=mr.get("assignees", []),
                reviewers=mr.get("reviewers", []),
                source_branch=mr["source_branch"],
                target_branch=mr["target_branch"],
                milestone=mr.get("milestone"),
                project_id=str(project_id),
                iid=mr["iid"],
                web_url_value=mr.get("web_url"),
                merge_status=mr.get("merge_status", "unchecked"),
                draft=mr.get("draft", False),
                work_in_progress=mr.get("work_in_progress", False),
                upvotes=mr.get("upvotes", 0),
                downvotes=mr.get("downvotes", 0),
                user_notes_count=mr.get("user_notes_count", 0),
            )

    async def _traverse_repository(
        self,
        client: httpx.AsyncClient,
        project_id: str,
        project_path: str,
        branch: str,
        project_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Traverse repository contents using DFS.

        Args:
            client: HTTP client
            project_id: Project ID
            project_path: Project path with namespace
            branch: Branch name
            project_breadcrumbs: Breadcrumbs for the project

        Yields:
            Directory and file entities
        """
        # Track processed paths to avoid duplicates
        processed_paths = set()

        # Start DFS traversal from root
        async for entity in self._traverse_directory(
            client, project_id, project_path, "", branch, project_breadcrumbs, processed_paths
        ):
            yield entity

    async def _traverse_directory(
        self,
        client: httpx.AsyncClient,
        project_id: str,
        project_path: str,
        path: str,
        branch: str,
        breadcrumbs: List[Breadcrumb],
        processed_paths: set,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Recursively traverse a directory using DFS.

        Args:
            client: HTTP client
            project_id: Project ID
            project_path: Project path with namespace
            path: Current path to traverse
            branch: Branch name
            breadcrumbs: Current breadcrumb chain
            processed_paths: Set of already processed paths

        Yields:
            Directory and file entities
        """
        if path in processed_paths:
            return

        processed_paths.add(path)

        # Get contents of the current directory
        url = f"{self.BASE_URL}/projects/{project_id}/repository/tree"
        params = {"ref": branch, "path": path, "per_page": 100}

        try:
            contents = await self._get_paginated_results(client, url, params)

            # Process each item in the directory
            for item in contents:
                item_path = item["path"]
                item_type = item["type"]

                if item_type == "tree":  # Directory
                    # Create directory entity
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

                    # Create breadcrumb for this directory
                    dir_breadcrumb = Breadcrumb(
                        entity_id=dir_entity.full_path,
                        name=dir_entity.name,
                        entity_type=GitLabDirectoryEntity.__name__,
                    )

                    # Yield the directory entity
                    yield dir_entity

                    # Create updated breadcrumb chain for children
                    dir_breadcrumbs = breadcrumbs.copy() + [dir_breadcrumb]

                    # Recursively traverse this directory (DFS)
                    async for child_entity in self._traverse_directory(
                        client,
                        project_id,
                        project_path,
                        item_path,
                        branch,
                        dir_breadcrumbs,
                        processed_paths,
                    ):
                        yield child_entity

                elif item_type == "blob":  # File
                    # Process the file and yield entities
                    async for file_entity in self._process_file(
                        client, project_id, project_path, item_path, branch, breadcrumbs
                    ):
                        yield file_entity

        except Exception as e:
            self.logger.error(f"Error traversing path {path}: {str(e)}")

    async def _process_file(
        self,
        client: httpx.AsyncClient,
        project_id: str,
        project_path: str,
        file_path: str,
        branch: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a file item and create file entities.

        Args:
            client: HTTP client
            project_id: Project ID
            project_path: Project path with namespace
            file_path: Path to the file
            branch: Branch name
            breadcrumbs: Current breadcrumb chain

        Yields:
            File entities
        """
        try:
            # Get file metadata first
            encoded_path = file_path.replace("/", "%2F")
            url = f"{self.BASE_URL}/projects/{project_id}/repository/files/{encoded_path}"
            params = {"ref": branch}

            file_data = await self._get_with_auth(client, url, params)
            file_size = file_data.get("size", 0)

            # Get content sample for text file detection
            content_sample = None
            content_text = None

            if file_data.get("encoding") == "base64" and file_data.get("content"):
                try:
                    content_bytes = base64.b64decode(file_data["content"])
                    content_sample = content_bytes[:1024]
                    # Try to decode content as text for storage
                    content_text = content_bytes.decode("utf-8", errors="replace")
                except Exception:
                    pass

            # Check if this is a text file
            if is_text_file(file_path, file_size, content_sample):
                # Detect language
                language = self._detect_language_from_extension(file_path)

                # Ensure we have a valid path
                file_name = Path(file_path).name

                # Set line count if we have content
                line_count = 0
                if content_text:
                    try:
                        line_count = content_text.count("\n") + 1
                    except Exception as e:
                        self.logger.error(f"Error counting lines for {file_path}: {str(e)}")

                # Determine file type from mime_type
                mime_type = mimetypes.guess_type(file_path)[0] or "text/plain"
                file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

                # Create file entity (without content field)
                file_entity = GitLabCodeFileEntity(
                    breadcrumbs=breadcrumbs.copy(),
                    full_path=f"{project_id}/{file_path}",
                    name=file_name,
                    branch=branch,
                    url=f"https://gitlab.com/{project_path}/-/raw/{branch}/{file_path}",
                    size=file_size,
                    file_type=file_type,
                    mime_type=mime_type,
                    local_path=None,  # Will be set by file_downloader
                    # Code file fields
                    repo_name=project_path.split("/")[-1],
                    path_in_repo=file_path,
                    repo_owner="/".join(project_path.split("/")[:-1]) or project_path,
                    language=language,
                    commit_id=file_data["blob_id"],
                    # API fields (GitLab-specific)
                    blob_id=file_data["blob_id"],
                    project_id=str(project_id),
                    project_path=project_path,
                    line_count=line_count,
                    web_url_value=f"https://gitlab.com/{project_path}/-/blob/{branch}/{file_path}",
                )

                # Write content to disk for uniform file handling
                await self.file_downloader.save_bytes(
                    entity=file_entity,
                    content=content_text.encode("utf-8"),
                    filename_with_extension=file_path,  # GitLab file path (has extension)
                    logger=self.logger,
                )

                # Verify save succeeded
                if not file_entity.local_path:
                    raise ValueError(f"Save failed - no local path set for {file_entity.name}")

                yield file_entity

        except FileSkippedException as e:
            # File intentionally skipped (unsupported type, too large, etc.) - not an error
            self.logger.debug(f"Skipping file: {e.reason}")

        except Exception as e:
            self.logger.error(f"Error processing file {file_path}: {str(e)}")

    async def _get_projects(self, client: httpx.AsyncClient) -> List[GitLabProjectEntity]:
        """Get accessible projects based on configuration.

        Args:
            client: HTTP client

        Returns:
            List of project entities
        """
        if hasattr(self, "project_id") and self.project_id:
            return [await self._get_project_info(client, self.project_id)]

        # All accessible projects
        url = f"{self.BASE_URL}/projects"
        params = {"membership": True, "simple": False}
        projects_data = await self._get_paginated_results(client, url, params)
        projects = []
        for proj_data in projects_data:
            try:
                project = await self._get_project_info(client, str(proj_data["id"]))
                projects.append(project)
            except Exception as e:
                self.logger.warning(f"Failed to get project {proj_data.get('id')}: {e}")
        return projects

    async def _process_project(
        self,
        client: httpx.AsyncClient,
        project: GitLabProjectEntity,
        project_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a single project and yield all its entities.

        Args:
            client: HTTP client
            project: Project entity
            project_breadcrumbs: Breadcrumbs for the project

        Yields:
            Directory, file, issue, and merge request entities
        """
        branch = (
            self.branch
            if hasattr(self, "branch") and self.branch
            else project.default_branch or "main"
        )

        self.logger.debug(f"Processing project {project.path_with_namespace} on branch {branch}")

        project_id = str(project.project_id)

        # Traverse repository files if not empty
        if not project.empty_repo:
            try:
                async for entity in self._traverse_repository(
                    client,
                    project_id,
                    project.path_with_namespace,
                    branch,
                    project_breadcrumbs,
                ):
                    yield entity
            except Exception as e:
                self.logger.warning(
                    f"Failed to traverse repository for {project.path_with_namespace}: {e}"
                )

        # Get issues
        try:
            async for issue in self._get_project_issues(client, project_id, project_breadcrumbs):
                yield issue
        except Exception as e:
            self.logger.warning(f"Failed to get issues for {project.path_with_namespace}: {e}")

        # Get merge requests
        try:
            async for mr in self._get_project_merge_requests(
                client, project_id, project_breadcrumbs
            ):
                yield mr
        except Exception as e:
            self.logger.warning(f"Failed to get MRs for {project.path_with_namespace}: {e}")

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from GitLab.

        Yields:
            User, project, directory, file, issue, and merge request entities
        """
        async with self.http_client() as client:
            # First, yield the current user entity
            user_entity = await self._get_current_user(client)
            yield user_entity

            # Get accessible projects
            projects = await self._get_projects(client)

            # Process each project
            for project in projects:
                yield project

                project_breadcrumb = Breadcrumb(
                    entity_id=str(project.project_id),
                    name=project.name,
                    entity_type=GitLabProjectEntity.__name__,
                )
                project_breadcrumbs = [project_breadcrumb]

                # Process all entities within the project
                async for entity in self._process_project(client, project, project_breadcrumbs):
                    yield entity

    async def validate(self) -> bool:
        """Verify GitLab OAuth token by pinging the /user endpoint."""
        return await self._validate_oauth2(
            ping_url=f"{self.BASE_URL}/user",
            headers={"Accept": "application/json"},
            timeout=10.0,
        )
