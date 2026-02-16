"""Bitbucket source implementation for syncing repositories, workspaces, and code files."""

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import BitbucketAuthConfig
from airweave.platform.configs.config import BitbucketConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.bitbucket import (
    BitbucketCodeFileEntity,
    BitbucketDirectoryEntity,
    BitbucketRepositoryEntity,
    BitbucketWorkspaceEntity,
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
from airweave.schemas.source_connection import AuthenticationMethod


@source(
    name="Bitbucket",
    short_name="bitbucket",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class=BitbucketAuthConfig,
    config_class=BitbucketConfig,
    labels=["Code"],
    supports_continuous=False,
    supports_temporal_relevance=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class BitbucketSource(BaseSource):
    """Bitbucket source connector integrates with the Bitbucket REST API to extract data.

    Connects to your Bitbucket workspaces and repositories.

    It supports syncing workspaces, repositories, directories,
    and code files with configurable filtering options for branches and file types.
    """

    BASE_URL = "https://api.bitbucket.org/2.0"

    @classmethod
    async def create(
        cls, credentials: BitbucketAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "BitbucketSource":
        """Create a new source instance with authentication.

        Args:
            credentials: BitbucketAuthConfig instance containing authentication details
            config: Optional source configuration parameters

        Returns:
            Configured Bitbucket source instance
        """
        instance = cls()

        instance.access_token = credentials.access_token
        instance.email = credentials.email
        instance.workspace = credentials.workspace
        instance.repo_slug = credentials.repo_slug

        instance.branch = config.get("branch", "") if config else ""
        instance.file_extensions = config.get("file_extensions", []) if config else []

        return instance

    def _get_auth(self) -> httpx.BasicAuth:
        """Get Basic authentication object for Bitbucket API requests.

        Bitbucket API uses Basic authentication with email and API token.

        Returns:
            httpx.BasicAuth object configured for the request

        Raises:
            ValueError: If authentication credentials are missing
        """
        access_token = getattr(self, "access_token", None)
        email = getattr(self, "email", None)

        if not access_token or not access_token.strip():
            raise ValueError("API token is required")
        if not email or not email.strip():
            raise ValueError("Atlassian email is required")

        self.logger.debug("Using API token authentication")
        return httpx.BasicAuth(username=email, password=access_token)

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated API request using Basic authentication.

        Retries on:
        - 429 rate limits (respects Retry-After header)
        - Timeout errors (exponential backoff)

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response
        """
        auth = self._get_auth()
        headers = {"Accept": "application/json"}
        response = await client.get(url, auth=auth, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def _get_paginated_results(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get all pages of results from a paginated Bitbucket API endpoint.

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            List of all results from all pages
        """
        if params is None:
            params = {}

        all_results = []
        next_url = url
        auth = self._get_auth()
        headers = {"Accept": "application/json"}

        while next_url:
            response = await client.get(
                next_url, auth=auth, headers=headers, params=params if next_url == url else None
            )
            response.raise_for_status()

            data = response.json()
            results = data.get("values", [])
            all_results.extend(results)

            # Get next page URL
            next_url = data.get("next")

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

    def _should_include_file(self, file_path: str) -> bool:
        """Check if a file should be included based on configured extensions.

        Args:
            file_path: Path to the file

        Returns:
            True if file should be included
        """
        if not self.file_extensions:
            # If no extensions specified, include all text files
            return True

        if ".*" in self.file_extensions:
            # Include all files
            return True

        file_ext = Path(file_path).suffix.lower()
        return any(file_ext == ext.lower() for ext in self.file_extensions)

    async def _get_workspace_info(
        self, client: httpx.AsyncClient, workspace_slug: str
    ) -> BitbucketWorkspaceEntity:
        """Get workspace information.

        Args:
            client: HTTP client
            workspace_slug: Workspace slug

        Returns:
            Workspace entity
        """
        url = f"{self.BASE_URL}/workspaces/{workspace_slug}"
        workspace_data = await self._get_with_auth(client, url)

        created_on = (
            datetime.fromisoformat(workspace_data["created_on"].replace("Z", "+00:00"))
            if workspace_data.get("created_on")
            else None
        )

        return BitbucketWorkspaceEntity(
            uuid=workspace_data["uuid"],
            display_name=workspace_data.get("name") or workspace_data["slug"],
            created_on=created_on,
            breadcrumbs=[],
            slug=workspace_data["slug"],
            is_private=workspace_data.get("is_private", True),
            html_url=workspace_data["links"]["html"]["href"],
        )

    async def _get_repository_info(
        self, client: httpx.AsyncClient, workspace_slug: str, repo_slug: str
    ) -> BitbucketRepositoryEntity:
        """Get repository information.

        Args:
            client: HTTP client
            workspace_slug: Workspace slug
            repo_slug: Repository slug

        Returns:
            Repository entity
        """
        url = f"{self.BASE_URL}/repositories/{workspace_slug}/{repo_slug}"
        repo_data = await self._get_with_auth(client, url)

        return BitbucketRepositoryEntity(
            uuid=repo_data["uuid"],
            repo_name=repo_data.get("name") or repo_data["slug"],
            created_on=datetime.fromisoformat(repo_data["created_on"].replace("Z", "+00:00")),
            updated_on=datetime.fromisoformat(repo_data["updated_on"].replace("Z", "+00:00")),
            breadcrumbs=[],
            slug=repo_data["slug"],
            full_name=repo_data["full_name"],
            description=repo_data.get("description"),
            is_private=repo_data.get("is_private", True),
            fork_policy=repo_data.get("fork_policy"),
            language=repo_data.get("language"),
            size=repo_data.get("size"),
            mainbranch=(
                repo_data.get("mainbranch", {}).get("name") if repo_data.get("mainbranch") else None
            ),
            workspace_slug=workspace_slug,
            html_url=repo_data["links"]["html"]["href"],
        )

    async def _get_repositories(
        self, client: httpx.AsyncClient, workspace_slug: str
    ) -> List[Dict[str, Any]]:
        """Get all repositories in a workspace.

        Args:
            client: HTTP client
            workspace_slug: Workspace slug

        Returns:
            List of repository data
        """
        url = f"{self.BASE_URL}/repositories/{workspace_slug}"
        return await self._get_paginated_results(client, url)

    async def _traverse_repository(
        self,
        client: httpx.AsyncClient,
        workspace_slug: str,
        repo_slug: str,
        branch: str,
        parent_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Traverse repository contents using DFS.

        Args:
            client: HTTP client
            workspace_slug: Workspace slug
            repo_slug: Repository slug
            branch: Branch name
            parent_breadcrumbs: Parent breadcrumbs for navigation

        Yields:
            Directory and file entities
        """
        # Get repository info first
        repo_entity = await self._get_repository_info(client, workspace_slug, repo_slug)
        repo_entity.breadcrumbs = parent_breadcrumbs.copy()
        yield repo_entity

        repo_breadcrumb = Breadcrumb(
            entity_id=repo_entity.uuid,
            name=repo_entity.repo_name,
            entity_type="BitbucketRepositoryEntity",
        )

        # Track processed paths to avoid duplicates
        processed_paths = set()

        # Start DFS traversal from root
        initial_breadcrumbs = parent_breadcrumbs + [repo_breadcrumb]

        async for entity in self._traverse_directory(
            client,
            workspace_slug,
            repo_slug,
            "",
            initial_breadcrumbs,
            branch,
            processed_paths,
        ):
            yield entity

    async def _traverse_directory(
        self,
        client: httpx.AsyncClient,
        workspace_slug: str,
        repo_slug: str,
        path: str,
        breadcrumbs: List[Breadcrumb],
        branch: str,
        processed_paths: set,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Recursively traverse a directory using DFS.

        Args:
            client: HTTP client
            workspace_slug: Workspace slug
            repo_slug: Repository slug
            path: Current path to traverse
            breadcrumbs: Current breadcrumb chain
            branch: Branch name
            processed_paths: Set of already processed paths

        Yields:
            Directory and file entities
        """
        if path in processed_paths:
            return

        processed_paths.add(path)

        # Get contents of the current directory
        url = f"{self.BASE_URL}/repositories/{workspace_slug}/{repo_slug}/src/{branch}/{path}"

        try:
            contents = await self._get_paginated_results(client, url)

            # Process each item in the directory
            for item in contents:
                item_path = item["path"]
                item_type = item.get("type", "file")

                if item_type == "commit_directory":
                    # Create directory entity
                    dir_name = Path(item_path).name or repo_slug
                    path_id = f"{workspace_slug}/{repo_slug}/{branch}/{item_path or '.'}"
                    dir_entity = BitbucketDirectoryEntity(
                        path_id=path_id,
                        directory_name=dir_name,
                        breadcrumbs=breadcrumbs.copy(),
                        path=item_path,
                        branch=branch,
                        repo_slug=repo_slug,
                        repo_full_name=f"{workspace_slug}/{repo_slug}",
                        workspace_slug=workspace_slug,
                        html_url=(
                            f"https://bitbucket.org/{workspace_slug}/{repo_slug}/src/"
                            f"{branch}/{item_path}"
                        ),
                    )

                    dir_breadcrumb = Breadcrumb(
                        entity_id=dir_entity.path_id,
                        name=dir_entity.directory_name,
                        entity_type="BitbucketDirectoryEntity",
                    )

                    # Yield the directory entity
                    yield dir_entity

                    # Create updated breadcrumb chain for children
                    dir_breadcrumbs = breadcrumbs.copy() + [dir_breadcrumb]

                    # Recursively traverse this directory (DFS)
                    async for child_entity in self._traverse_directory(
                        client,
                        workspace_slug,
                        repo_slug,
                        item_path,
                        dir_breadcrumbs,
                        branch,
                        processed_paths,
                    ):
                        yield child_entity

                elif item_type == "commit_file":
                    # Check if we should include this file
                    if self._should_include_file(item_path):
                        # Process the file and yield entities
                        async for file_entity in self._process_file(
                            client,
                            workspace_slug,
                            repo_slug,
                            item_path,
                            item,
                            breadcrumbs,
                            branch,
                        ):
                            yield file_entity

        except Exception as e:
            self.logger.error(f"Error traversing path {path}: {str(e)}")

    async def _process_file(
        self,
        client: httpx.AsyncClient,
        workspace_slug: str,
        repo_slug: str,
        item_path: str,
        item: Dict[str, Any],
        breadcrumbs: List[Breadcrumb],
        branch: str,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a file item and create file entities.

        Args:
            client: HTTP client
            workspace_slug: Workspace slug
            repo_slug: Repository slug
            item_path: Path to the file
            item: File item data
            breadcrumbs: Current breadcrumb chain
            branch: Branch name

        Yields:
            File entities
        """
        try:
            # Get file content - use raw format to get actual file content
            file_url = (
                f"{self.BASE_URL}/repositories/{workspace_slug}/{repo_slug}"
                f"/src/{branch}/{item_path}"
            )
            auth = self._get_auth()
            headers = {"Accept": "text/plain"}

            file_response = await client.get(
                file_url,
                auth=auth,
                headers=headers,
                params={"format": "raw"},
            )
            file_response.raise_for_status()

            # Get the raw file content
            content_text = file_response.text
            file_size = len(content_text.encode("utf-8"))

            # Check if this is a text file
            content_sample = content_text.encode("utf-8")[:1024] if content_text else None
            if is_text_file(item_path, file_size, content_sample):
                # Detect language
                language = self._detect_language_from_extension(item_path)

                # Ensure we have a valid path
                file_name = Path(item_path).name

                # Set line count if we have content
                line_count = 0
                if content_text:
                    try:
                        line_count = content_text.count("\n") + 1
                    except Exception as e:
                        self.logger.error(f"Error counting lines for {item_path}: {str(e)}")

                # Determine file type from mime_type
                mime_type = mimetypes.guess_type(item_path)[0] or "text/plain"
                file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

                # Get commit hash for commit_id
                commit_hash = item.get("commit", {}).get("hash", "")

                # Create file entity (without content field)
                file_entity = BitbucketCodeFileEntity(
                    file_id=f"{workspace_slug}/{repo_slug}/{branch}/{item_path}",
                    file_name=file_name,
                    branch=branch,
                    breadcrumbs=breadcrumbs.copy(),
                    url=f"https://bitbucket.org/{workspace_slug}/{repo_slug}/src/{branch}/{item_path}",
                    size=file_size,
                    file_type=file_type,
                    mime_type=mime_type,
                    local_path=None,
                    repo_name=repo_slug,
                    path_in_repo=item_path,
                    repo_owner=workspace_slug,
                    language=language,
                    commit_id=commit_hash,
                    commit_hash=commit_hash,
                    repo_slug=repo_slug,
                    repo_full_name=f"{workspace_slug}/{repo_slug}",
                    workspace_slug=workspace_slug,
                    line_count=line_count,
                )

                # Write content to disk for uniform file handling
                await self.file_downloader.save_bytes(
                    entity=file_entity,
                    content=content_text.encode("utf-8"),
                    filename_with_extension=item_path,  # Bitbucket file path (has extension)
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
            self.logger.error(f"Error processing file {item_path}: {str(e)}")

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from Bitbucket.

        Yields:
            Workspace, repository, directory, and file entities
        """
        if not hasattr(self, "workspace") or not self.workspace:
            raise ValueError("Workspace must be specified")

        async with self.http_client() as client:
            # First, yield the workspace entity
            workspace_entity = await self._get_workspace_info(client, self.workspace)
            yield workspace_entity

            workspace_breadcrumb = Breadcrumb(
                entity_id=workspace_entity.uuid,
                name=workspace_entity.display_name,
                entity_type="BitbucketWorkspaceEntity",
            )

            # If a specific repository is specified, only process that one
            if hasattr(self, "repo_slug") and self.repo_slug:
                repo_data = await self._get_repository_info(client, self.workspace, self.repo_slug)

                # Use specified branch or default branch
                branch = self.branch or repo_data.mainbranch or "master"
                self.logger.debug(f"Using branch: {branch} for repo {self.repo_slug}")

                async for entity in self._traverse_repository(
                    client, self.workspace, self.repo_slug, branch, [workspace_breadcrumb]
                ):
                    # Add workspace breadcrumb to repository entities
                    if isinstance(entity, BitbucketRepositoryEntity):
                        entity.breadcrumbs = [workspace_breadcrumb]
                    yield entity
            else:
                # Process all repositories in the workspace
                repositories = await self._get_repositories(client, self.workspace)

                for repo_data in repositories:
                    repo_slug = repo_data["slug"]

                    # Get detailed repo info to get default branch
                    repo_entity = await self._get_repository_info(client, self.workspace, repo_slug)

                    # Use specified branch or default branch
                    branch = self.branch or repo_entity.mainbranch or "master"
                    self.logger.debug(f"Using branch: {branch} for repo {repo_slug}")

                    async for entity in self._traverse_repository(
                        client, self.workspace, repo_slug, branch, [workspace_breadcrumb]
                    ):
                        # Add workspace breadcrumb to repository entities
                        if isinstance(entity, BitbucketRepositoryEntity):
                            entity.breadcrumbs = [workspace_breadcrumb]
                        yield entity

    async def validate(self) -> bool:
        """Verify Bitbucket Basic Auth and (if provided) workspace access."""
        # Ensure credentials are present
        try:
            async with self.http_client(timeout=10.0) as client:
                # 1) Auth check - _get_with_auth returns JSON data, not response object
                try:
                    user_data = await self._get_with_auth(client, f"{self.BASE_URL}/user")
                    # If we get here, auth is successful (would have raised on error)
                    if user_data and "uuid" in user_data:
                        self.logger.debug(
                            "Bitbucket auth validated for user: "
                            f" {user_data.get('username', 'Unknown')}"
                        )
                    else:
                        self.logger.warning("Bitbucket auth returned unexpected data format")
                        return False
                except httpx.HTTPStatusError as e:
                    self.logger.warning(f"Bitbucket /user auth failed: {e}")
                    return False

                # 2) Workspace reachability (optional but recommended for this connector)
                if getattr(self, "workspace", None):
                    try:
                        ws_data = await self._get_with_auth(
                            client, f"{self.BASE_URL}/workspaces/{self.workspace}"
                        )
                        if ws_data and "uuid" in ws_data:
                            self.logger.debug(f"Bitbucket workspace '{self.workspace}' verified")
                        else:
                            self.logger.warning(
                                f"Bitbucket workspace '{self.workspace}' returned unexpected data"
                            )
                            return False
                    except httpx.HTTPStatusError as e:
                        self.logger.warning(
                            f"Bitbucket workspace '{self.workspace}' check failed: {e}"
                        )
                        return False

            return True
        except httpx.RequestError as e:
            self.logger.error(f"Bitbucket validation request error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during Bitbucket validation: {e}")
            return False
