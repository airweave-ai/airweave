"""Bitbucket source implementation for syncing repositories, workspaces, and code files."""

import base64
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import tenacity
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs.auth import BitbucketAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.bitbucket import (
    BitbucketCodeFileEntity,
    BitbucketDirectoryEntity,
    BitbucketRepositoryEntity,
    BitbucketWorkspaceEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.utils.file_extensions import (
    get_language_for_extension,
    is_text_file,
)


@source(
    name="Bitbucket",
    short_name="bitbucket",
    auth_type=AuthType.config_class,
    auth_config_class="BitbucketAuthConfig",
    config_class="BitbucketConfig",
    labels=["Code"],
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

        instance.access_token = getattr(credentials, "access_token", None)
        instance.username = getattr(credentials, "username", None)
        instance.app_password = getattr(credentials, "app_password", None)
        instance.workspace = credentials.workspace
        instance.repo_slug = credentials.repo_slug

        instance.branch = config.get("branch", "") if config else ""
        instance.file_extensions = config.get("file_extensions", []) if config else []

        return instance

    @tenacity.retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated API request using Bearer or Basic authentication.

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response
        """
        if getattr(self, "access_token", None):
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Accept": "application/json",
            }
        else:
            # Create Basic auth credentials
            credentials = f"{self.username}:{self.app_password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Accept": "application/json",
            }
        response = await client.get(url, headers=headers, params=params)
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

        while next_url:
            if getattr(self, "access_token", None):
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                }
            else:
                # Create Basic auth credentials
                credentials = f"{self.username}:{self.app_password}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                headers = {
                    "Authorization": f"Basic {encoded_credentials}",
                    "Accept": "application/json",
                }

            response = await client.get(
                next_url, headers=headers, params=params if next_url == url else None
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

        return BitbucketWorkspaceEntity(
            entity_id=workspace_data["uuid"],
            source_name="bitbucket",
            slug=workspace_data["slug"],
            name=workspace_data["name"],
            uuid=workspace_data["uuid"],
            is_private=workspace_data.get("is_private", True),
            created_on=datetime.fromisoformat(workspace_data["created_on"].replace("Z", "+00:00"))
            if workspace_data.get("created_on")
            else None,
            url=workspace_data["links"]["html"]["href"],
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
            entity_id=repo_data["uuid"],
            source_name="bitbucket",
            name=repo_data["name"],
            slug=repo_data["slug"],
            full_name=repo_data["full_name"],
            description=repo_data.get("description"),
            is_private=repo_data.get("is_private", True),
            fork_policy=repo_data.get("fork_policy"),
            language=repo_data.get("language"),
            created_on=datetime.fromisoformat(repo_data["created_on"].replace("Z", "+00:00")),
            updated_on=datetime.fromisoformat(repo_data["updated_on"].replace("Z", "+00:00")),
            size=repo_data.get("size"),
            mainbranch=repo_data.get("mainbranch", {}).get("name")
            if repo_data.get("mainbranch")
            else None,
            workspace_slug=workspace_slug,
            url=repo_data["links"]["html"]["href"],
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
        self, client: httpx.AsyncClient, workspace_slug: str, repo_slug: str, branch: str
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Traverse repository contents using DFS.

        Args:
            client: HTTP client
            workspace_slug: Workspace slug
            repo_slug: Repository slug
            branch: Branch name

        Yields:
            Directory and file entities
        """
        # Get repository info first
        repo_entity = await self._get_repository_info(client, workspace_slug, repo_slug)
        yield repo_entity

        # Create breadcrumb for the repo
        repo_breadcrumb = Breadcrumb(
            entity_id=repo_entity.entity_id, name=repo_entity.name, type="repository"
        )

        # Track processed paths to avoid duplicates
        processed_paths = set()

        # Start DFS traversal from root
        async for entity in self._traverse_directory(
            client, workspace_slug, repo_slug, "", [repo_breadcrumb], branch, processed_paths
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
    ) -> AsyncGenerator[ChunkEntity, None]:
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
                    dir_entity = BitbucketDirectoryEntity(
                        entity_id=f"{workspace_slug}/{repo_slug}/{item_path}",
                        source_name="bitbucket",
                        path=item_path,
                        repo_slug=repo_slug,
                        repo_full_name=f"{workspace_slug}/{repo_slug}",
                        workspace_slug=workspace_slug,
                        content=f"Directory: {item_path}",
                        breadcrumbs=breadcrumbs.copy(),
                        url=f"https://bitbucket.org/{workspace_slug}/{repo_slug}/src/{branch}/{item_path}",
                    )

                    # Create breadcrumb for this directory
                    dir_breadcrumb = Breadcrumb(
                        entity_id=dir_entity.entity_id,
                        name=Path(item_path).name,
                        type="directory",
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
                            client, workspace_slug, repo_slug, item_path, item, breadcrumbs, branch
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
    ) -> AsyncGenerator[ChunkEntity, None]:
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
            if getattr(self, "access_token", None):
                headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "text/plain",
                }
            else:
                # Create Basic auth credentials
                credentials = f"{self.username}:{self.app_password}"
                encoded_credentials = base64.b64encode(credentials.encode()).decode()
                headers = {
                    "Authorization": f"Basic {encoded_credentials}",
                    "Accept": "text/plain",
                }

            file_response = await client.get(
                file_url,
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

                # Create file entity with content stored in memory
                file_entity = BitbucketCodeFileEntity(
                    entity_id=f"{workspace_slug}/{repo_slug}/{item_path}",
                    source_name="bitbucket",
                    file_id=item.get("commit", {}).get("hash", ""),
                    name=file_name,
                    mime_type=mimetypes.guess_type(item_path)[0] or "text/plain",
                    size=file_size,
                    path=item_path,
                    repo_slug=repo_slug,
                    repo_full_name=f"{workspace_slug}/{repo_slug}",
                    workspace_slug=workspace_slug,
                    commit_hash=item.get("commit", {}).get("hash"),
                    breadcrumbs=breadcrumbs.copy(),
                    url=f"https://bitbucket.org/{workspace_slug}/{repo_slug}/src/{branch}/{item_path}",
                    language=language,
                    line_count=line_count,
                    path_in_repo=item_path,
                    content=content_text,  # Store the content directly in the entity
                    # Required fields from CodeFileEntity base class
                    repo_name=repo_slug,  # Repository name
                    repo_owner=workspace_slug,  # Repository owner (workspace)
                    last_modified=datetime.fromisoformat(
                        item.get("commit", {}).get("date", "").replace("Z", "+00:00")
                    )
                    if item.get("commit", {}).get("date")
                    else None,
                )

                yield file_entity
        except Exception as e:
            self.logger.error(f"Error processing file {item_path}: {str(e)}")

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate entities from Bitbucket.

        Yields:
            Workspace, repository, directory, and file entities
        """
        if not hasattr(self, "workspace") or not self.workspace:
            raise ValueError("Workspace must be specified")

        async with httpx.AsyncClient() as client:
            # First, yield the workspace entity
            workspace_entity = await self._get_workspace_info(client, self.workspace)
            yield workspace_entity

            workspace_breadcrumb = Breadcrumb(
                entity_id=workspace_entity.entity_id,
                name=workspace_entity.name,
                type="workspace",
            )

            # If a specific repository is specified, only process that one
            if hasattr(self, "repo_slug") and self.repo_slug:
                repo_data = await self._get_repository_info(client, self.workspace, self.repo_slug)

                # Use specified branch or default branch
                branch = self.branch or repo_data.mainbranch or "master"
                self.logger.info(f"Using branch: {branch} for repo {self.repo_slug}")

                async for entity in self._traverse_repository(
                    client, self.workspace, self.repo_slug, branch
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
                    self.logger.info(f"Using branch: {branch} for repo {repo_slug}")

                    async for entity in self._traverse_repository(
                        client, self.workspace, repo_slug, branch
                    ):
                        # Add workspace breadcrumb to repository entities
                        if isinstance(entity, BitbucketRepositoryEntity):
                            entity.breadcrumbs = [workspace_breadcrumb]
                        yield entity
