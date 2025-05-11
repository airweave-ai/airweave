"""GitHub source implementation (read-only).

Retrieves data from a user's GitHub account, focusing on:
 - Repositories
 - Repository Contents (files, directories, etc.)

and yields them as entities using the corresponding GitHub entity schemas
(GithubRepoEntity and GithubContentEntity).

References:
  https://docs.github.com/en/rest/repos/repos
  https://docs.github.com/en/rest/repos/contents

Notes:
  - This connector uses a read-only scope.
  - For each repository, we gather basic repo metadata, then traverse the
    repository contents recursively (default branch only).
"""

import base64
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
import tenacity
from tenacity import retry_if_exception_type, stop_after_attempt, wait_exponential

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.configs.auth import GitHubAuthConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb, ChunkEntity
from airweave.platform.entities.github import (
    GitHubCodeFileEntity,
    GitHubDirectoryEntity,
    GitHubRepositoryEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.utils.file_extensions import (
    get_language_for_extension,
    is_text_file,
)


@source(
    "GitHub",
    "github",
    AuthType.config_class,
    "GitHubAuthConfig",
    labels=["Code"],
)
class GitHubSource(BaseSource):
    """GitHub source implementation."""

    BASE_URL = "https://api.github.com"

    @classmethod
    async def create(cls, config: GitHubAuthConfig) -> "GitHubSource":
        """Create a new source instance with authentication.

        Args:
            config: GitHubAuthConfig instance

        Returns:
            Configured GitHub source instance
        """
        instance = cls()

        instance.personal_access_token = config.personal_access_token
        instance.repo_name = config.repo_name
        return instance

    @tenacity.retry(
        retry=retry_if_exception_type(httpx.HTTPError),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
    )
    async def _get_with_auth(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make authenticated API request using Personal Access Token.

        Args:
            client: HTTP client
            url: API endpoint URL
            params: Optional query parameters

        Returns:
            JSON response
        """
        headers = {
            "Authorization": f"token {self.personal_access_token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        response = await client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    def _detect_language_from_extension(self, file_path: str) -> str:
        """Detect programming language from file extension.

        Args:
            file_path: Path to the file

        Returns:
            The detected language name
        """
        ext = Path(file_path).suffix.lower()
        return get_language_for_extension(ext)

    async def _get_repository_info(
        self, client: httpx.AsyncClient, repo_name: str
    ) -> GitHubRepositoryEntity:
        """Get repository information.

        Args:
            client: HTTP client
            repo_name: Repository name (format: "owner/repo")

        Returns:
            Repository entity
        """
        url = f"{self.BASE_URL}/repos/{repo_name}"
        repo_data = await self._get_with_auth(client, url)

        return GitHubRepositoryEntity(
            entity_id=str(repo_data["id"]),
            source_name="github",
            name=repo_data["name"],
            full_name=repo_data["full_name"],
            description=repo_data.get("description"),
            default_branch=repo_data["default_branch"],
            created_at=datetime.fromisoformat(repo_data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(repo_data["updated_at"].replace("Z", "+00:00")),
            language=repo_data.get("language"),
            fork=repo_data["fork"],
            size=repo_data["size"],
            stars_count=repo_data.get("stargazers_count"),
            watchers_count=repo_data.get("watchers_count"),
            forks_count=repo_data.get("forks_count"),
            open_issues_count=repo_data.get("open_issues_count"),
            url=repo_data["html_url"],
        )

    async def _traverse_repository(
        self, client: httpx.AsyncClient, repo_name: str, branch: str
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Traverse repository contents using DFS.

        Args:
            client: HTTP client
            repo_name: Repository name (format: "owner/repo")
            branch: Branch name

        Yields:
            Directory and file entities
        """
        # Get repository info first
        repo_entity = await self._get_repository_info(client, repo_name)
        yield repo_entity

        # Parse owner and repo
        owner, repo = repo_name.split("/")

        # Create breadcrumb for the repo
        repo_breadcrumb = Breadcrumb(
            entity_id=repo_entity.entity_id, name=repo_entity.name, type="repository"
        )

        # Track processed paths to avoid duplicates
        processed_paths = set()

        # Start DFS traversal from root
        async for entity in self._traverse_directory(
            client, repo_name, "", [repo_breadcrumb], owner, repo, branch, processed_paths
        ):
            yield entity

    async def _traverse_directory(
        self,
        client: httpx.AsyncClient,
        repo_name: str,
        path: str,
        breadcrumbs: List[Breadcrumb],
        owner: str,
        repo: str,
        branch: str,
        processed_paths: set,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Recursively traverse a directory using DFS.

        Args:
            client: HTTP client
            repo_name: Repository name
            path: Current path to traverse
            breadcrumbs: Current breadcrumb chain
            owner: Repository owner
            repo: Repository name
            branch: Branch name
            processed_paths: Set of already processed paths

        Yields:
            Directory and file entities
        """
        if path in processed_paths:
            return

        processed_paths.add(path)

        # Get contents of the current directory
        url = f"{self.BASE_URL}/repos/{repo_name}/contents/{path}"
        params = {"ref": branch}

        try:
            contents = await self._get_with_auth(client, url, params)

            # Handle pagination if needed (using GitHub's API)
            if isinstance(contents, List):
                items = contents
            else:
                items = [contents]

            # Process each item in the directory
            for item in items:
                item_path = item["path"]
                item_type = item["type"]

                if item_type == "dir":
                    # Create directory entity
                    dir_entity = GitHubDirectoryEntity(
                        entity_id=f"{repo_name}/{item_path}",
                        source_name="github",
                        path=item_path,
                        repo_name=repo,
                        repo_owner=owner,
                        content=f"Directory: {item_path}",
                        breadcrumbs=breadcrumbs.copy(),
                        url=item["html_url"],
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
                        repo_name,
                        item_path,
                        dir_breadcrumbs,
                        owner,
                        repo,
                        branch,
                        processed_paths,
                    ):
                        yield child_entity

                elif item_type == "file":
                    # Process the file and yield entities
                    async for file_entity in self._process_file(
                        client, repo_name, item_path, item, breadcrumbs, owner, repo, branch
                    ):
                        yield file_entity

        except Exception as e:
            logger.error(f"Error traversing path {path}: {str(e)}")

    async def _process_file(
        self,
        client: httpx.AsyncClient,
        repo_name: str,
        item_path: str,
        item: Dict[str, Any],
        breadcrumbs: List[Breadcrumb],
        owner: str,
        repo: str,
        branch: str,
    ) -> AsyncGenerator[ChunkEntity, None]:
        """Process a file item and create file entities.

        Args:
            client: HTTP client
            repo_name: Repository name
            item_path: Path to the file
            item: File item data
            breadcrumbs: Current breadcrumb chain
            owner: Repository owner
            repo: Repository name
            branch: Branch name

        Yields:
            File entities
        """
        try:
            # For files at root level, ensure we use the correct API path
            file_url = f"{self.BASE_URL}/repos/{repo_name}/contents/{item_path}"
            file_data = await self._get_with_auth(client, file_url, {"ref": branch})
            file_size = file_data.get("size", 0)

            # Get content sample for text file detection if the file is not too large
            content_sample = None
            content_text = None
            if file_data.get("encoding") == "base64" and file_data.get("content"):
                try:
                    content_sample = base64.b64decode(file_data["content"])
                    # Try to decode content as text for storage
                    content_text = content_sample.decode("utf-8", errors="replace")
                except Exception:
                    pass

            # Check if this is a text file based on extension, size, and possibly content
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
                        logger.error(f"Error counting lines for {item_path}: {str(e)}")

                # Create file entity with guaranteed valid paths and store content in memory
                file_entity = GitHubCodeFileEntity(
                    entity_id=f"{repo_name}/{item_path}",
                    source_name="github",
                    file_id=file_data["sha"],
                    name=file_name,
                    mime_type=mimetypes.guess_type(item_path)[0] or "text/plain",
                    size=file_size,
                    path=item_path or file_name,  # Fallback to file name if path is empty
                    repo_name=repo,
                    repo_owner=owner,
                    sha=file_data["sha"],
                    breadcrumbs=breadcrumbs.copy(),
                    url=file_data["html_url"],
                    language=language,
                    line_count=line_count,
                    path_in_repo=item_path,
                    content=content_text,  # Store the content directly in the entity
                    last_modified=None,  # GitHub API doesn't provide this directly
                )

                # Let the file handler manage actual file processing
                yield file_entity
        except Exception as e:
            logger.error(f"Error processing file {item_path}: {str(e)}")

    async def generate_entities(self) -> AsyncGenerator[ChunkEntity, None]:
        """Generate entities from GitHub repository.

        Yields:
            Repository, directory, and file entities
        """
        if not hasattr(self, "repo_name") or not self.repo_name:
            raise ValueError("Repository name must be specified")

        async with httpx.AsyncClient() as client:
            repo_url = f"{self.BASE_URL}/repos/{self.repo_name}"
            repo_data = await self._get_with_auth(client, repo_url)
            default_branch = repo_data["default_branch"]

            async for entity in self._traverse_repository(client, self.repo_name, default_branch):
                yield entity
