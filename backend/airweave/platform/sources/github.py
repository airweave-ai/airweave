r"""GitHub source implementation for syncing repositories, directories, and code files."""

import base64
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import GitHubAuthConfig
from airweave.platform.configs.config import GitHubConfig
from airweave.platform.cursors import GitHubCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.github import (
    GitHubCodeFileEntity,
    GitHubDirectoryEntity,
    GitHubFileDeletionEntity,
    GitHubRepositoryEntity,
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
    name="GitHub",
    short_name="github",
    auth_methods=[AuthenticationMethod.DIRECT, AuthenticationMethod.AUTH_PROVIDER],
    oauth_type=None,
    auth_config_class=GitHubAuthConfig,
    config_class=GitHubConfig,
    labels=["Code"],
    supports_continuous=True,
    supports_temporal_relevance=False,
    cursor_class=GitHubCursor,
    rate_limit_level=RateLimitLevel.ORG,
)
class GitHubSource(BaseSource):
    """GitHub source connector integrates with the GitHub REST API to extract and synchronize data.

    Connects to your GitHub repositories.

    It supports syncing repository metadata, directory structures, and code files with
    configurable filtering options for branches and file types.
    """

    BASE_URL = "https://api.github.com"

    def get_default_cursor_field(self) -> Optional[str]:
        """Get the default cursor field for GitHub source.

        GitHub uses 'last_repository_pushed_at' to track repository changes.

        Returns:
            The default cursor field name
        """
        return "last_repository_pushed_at"

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate if the given cursor field is valid for GitHub.

        Args:
            cursor_field: The cursor field to validate

        Raises:
            ValueError: If the cursor field is invalid
        """
        # GitHub only supports its specific cursor field
        valid_field = self.get_default_cursor_field()

        if cursor_field != valid_field:
            error_msg = (
                f"Invalid cursor field '{cursor_field}' for GitHub source. "
                f"GitHub requires '{valid_field}' as the cursor field. "
                f"GitHub tracks repository changes using push timestamps, not entity fields. "
                f"Please use the default cursor field or omit it entirely."
            )
            self.logger.error(error_msg)
            raise ValueError(error_msg)

    @classmethod
    async def create(
        cls, credentials: GitHubAuthConfig, config: Optional[Dict[str, Any]] = None
    ) -> "GitHubSource":
        """Create a new source instance with authentication.

        Args:
            credentials: GitHubAuthConfig instance containing authentication details
            config: Optional source configuration parameters

        Returns:
            Configured GitHub source instance
        """
        instance = cls()

        instance.personal_access_token = credentials.personal_access_token

        # Repository name is always read from config (source configuration)
        if not config or "repo_name" not in config:
            raise ValueError("Repository name must be specified in source configuration")

        instance.repo_name = config["repo_name"]

        instance.branch = config.get("branch", None)

        instance.max_file_size = config.get("max_file_size", 10 * 1024 * 1024)

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

    async def _get_paginated_results(
        self, client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get all pages of results from a paginated GitHub API endpoint.

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
            headers = {
                "Authorization": f"token {self.personal_access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }

            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()

            results = response.json()
            if not results:  # Empty page means we're done
                break

            all_results.extend(results)

            # Check if there's a next page via Link header
            link_header = response.headers.get("Link", "")
            if 'rel="next"' not in link_header:
                break

            page += 1

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

    def _check_repository_updates(
        self, repo_name: str, last_pushed_at: str, current_pushed_at: str
    ) -> bool:
        """Check if repository has been updated since last sync.

        Args:
            repo_name: Repository name
            last_pushed_at: Last sync timestamp
            current_pushed_at: Current repository pushed_at

        Returns:
            True if repository has updates, False otherwise
        """
        if last_pushed_at:
            self.logger.debug(
                f"Repository {repo_name} pushed_at: {last_pushed_at} -> {current_pushed_at}"
            )
            has_updates = current_pushed_at > last_pushed_at
            if has_updates:
                self.logger.debug(f"Repository {repo_name} has new commits since last sync")
            else:
                self.logger.debug(f"Repository {repo_name} has no new commits since last sync")
            return has_updates
        else:
            self.logger.debug(f"First sync for repository {repo_name}")
            return True

    async def _get_repository_info(
        self, client: httpx.AsyncClient, repo_name: str
    ) -> GitHubRepositoryEntity:
        """Get repository information with cursor support.

        Args:
            client: HTTP client
            repo_name: Repository name (format: "owner/repo")

        Returns:
            Repository entity
        """
        url = f"{self.BASE_URL}/repos/{repo_name}"
        repo_data = await self._get_with_auth(client, url)

        # Check for cursor data and repository updates
        cursor_data = self.cursor.data if self.cursor else {}

        # Get the last sync timestamp from cursor data
        # If None, this is the first sync (full sync)
        # If present, this is an incremental sync
        last_pushed_at = cursor_data.get("last_repository_pushed_at")
        current_pushed_at = repo_data["pushed_at"]

        # Check for updates and log status
        self._check_repository_updates(repo_name, last_pushed_at, current_pushed_at)

        # Update cursor with current repository pushed_at
        if self.cursor:
            self.cursor.update(
                last_repository_pushed_at=current_pushed_at,
                repo_name=repo_name,
                branch=getattr(self, "branch", None),
            )

        return GitHubRepositoryEntity(
            breadcrumbs=[],
            repo_id=repo_data["id"],
            name=repo_data["name"],
            created_at=datetime.fromisoformat(repo_data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(repo_data["updated_at"].replace("Z", "+00:00")),
            full_name=repo_data["full_name"],
            description=repo_data.get("description"),
            default_branch=repo_data["default_branch"],
            language=repo_data.get("language"),
            fork=repo_data["fork"],
            size=repo_data["size"],
            stars_count=repo_data.get("stargazers_count"),
            watchers_count=repo_data.get("watchers_count"),
            forks_count=repo_data.get("forks_count"),
            open_issues_count=repo_data.get("open_issues_count"),
        )

    async def _traverse_repository(
        self, client: httpx.AsyncClient, repo_name: str, branch: str
    ) -> AsyncGenerator[BaseEntity, None]:
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
            entity_id=str(repo_entity.repo_id),
            name=repo_entity.name,
            entity_type=GitHubRepositoryEntity.__name__,
        )

        # Track processed paths to avoid duplicates
        processed_paths = set()
        processed_files = set()  # Track files separately to prevent duplicates

        # Start DFS traversal from root
        async for entity in self._traverse_directory(
            client,
            repo_name,
            "",
            [repo_breadcrumb],
            owner,
            repo,
            branch,
            processed_paths,
            processed_files,
        ):
            yield entity

    async def _traverse_repository_incremental(
        self, client: httpx.AsyncClient, repo_name: str, branch: str, since_timestamp: str
    ) -> AsyncGenerator[BaseEntity, None]:
        """Traverse repository contents incrementally using commits since last sync.

        Args:
            client: HTTP client
            repo_name: Repository name (format: "owner/repo")
            branch: Branch name
            since_timestamp: ISO 8601 timestamp to get commits since

        Yields:
            Repository and changed file entities
        """
        # Get repository info first
        repo_entity = await self._get_repository_info(client, repo_name)
        yield repo_entity

        # Parse owner and repo
        owner, repo = repo_name.split("/")

        repo_breadcrumb = Breadcrumb(
            entity_id=str(repo_entity.repo_id),
            name=repo_entity.name,
            entity_type=GitHubRepositoryEntity.__name__,
        )

        # Get commits since the last sync timestamp
        commits = await self._get_commits_since(client, repo_name, since_timestamp, branch)

        if not commits:
            self.logger.debug(f"No new commits found since {since_timestamp}")
            return

        self.logger.debug(f"Found {len(commits)} new commits since {since_timestamp}")

        # Track processed files to avoid duplicates
        processed_files = set()

        # Process each commit and extract changed files
        for commit in commits:
            commit_sha = commit["sha"]
            commit_message = commit["commit"]["message"]

            self.logger.debug(f"Processing commit {commit_sha[:8]}: {commit_message}")

            # Get files changed in this commit
            changed_files = await self._get_commit_files(client, repo_name, commit_sha)

            for file_info in changed_files:
                file_path = file_info["filename"]

                # Skip if we've already processed this file
                if file_path in processed_files:
                    continue

                processed_files.add(file_path)

                # Handle deleted files
                if file_info["status"] == "removed":
                    self.logger.debug(f"Processing deleted file: {file_path}")
                    # Create a special deletion entity
                    deletion_entity = GitHubFileDeletionEntity(
                        breadcrumbs=[],
                        full_path=f"{repo_name}/{file_path}",
                        deletion_label=f"Deleted file {file_path}",
                        file_path=file_path,
                        repo_name=repo,
                        repo_owner=owner,
                        branch=branch,
                        deletion_status="removed",
                    )
                    yield deletion_entity
                    continue

                # Process the changed file
                try:
                    async for entity in self._process_changed_file(
                        client, repo_name, file_path, owner, repo, branch, repo_breadcrumb
                    ):
                        yield entity
                except Exception as e:
                    self.logger.error(f"Error processing changed file {file_path}: {e}")

    async def _get_commits_since(
        self, client: httpx.AsyncClient, repo_name: str, since_timestamp: str, branch: str
    ) -> List[Dict[str, Any]]:
        """Get commits since a specific timestamp.

        Args:
            client: HTTP client
            repo_name: Repository name
            since_timestamp: ISO 8601 timestamp
            branch: Branch name

        Returns:
            List of commit objects
        """
        url = f"{self.BASE_URL}/repos/{repo_name}/commits"
        params = {
            "since": since_timestamp,
            "sha": branch,
            "per_page": 100,  # Max allowed
        }

        commits = await self._get_paginated_results(client, url, params)
        self.logger.debug(f"Retrieved {len(commits)} commits since {since_timestamp}")
        return commits

    async def _get_commit_files(
        self, client: httpx.AsyncClient, repo_name: str, commit_sha: str
    ) -> List[Dict[str, Any]]:
        """Get files changed in a specific commit.

        Args:
            client: HTTP client
            repo_name: Repository name
            commit_sha: Commit SHA

        Returns:
            List of file change objects
        """
        url = f"{self.BASE_URL}/repos/{repo_name}/commits/{commit_sha}"

        try:
            commit_data = await self._get_with_auth(client, url)
            files = commit_data.get("files", [])
            self.logger.debug(f"Commit {commit_sha[:8]} changed {len(files)} files")
            return files
        except Exception as e:
            self.logger.error(f"Error getting files for commit {commit_sha}: {e}")
            return []

    async def _process_changed_file(
        self,
        client: httpx.AsyncClient,
        repo_name: str,
        file_path: str,
        owner: str,
        repo: str,
        branch: str,
        repo_breadcrumb: Breadcrumb,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a single changed file.

        Args:
            client: HTTP client
            repo_name: Repository name
            file_path: Path to the file
            owner: Repository owner
            repo: Repository name
            branch: Branch name
            repo_breadcrumb: Breadcrumb representing the parent repository

        Yields:
            File entity if it's a text file
        """
        # Create breadcrumbs for the file
        path_parts = file_path.split("/")
        breadcrumbs = [repo_breadcrumb]

        # Add directory breadcrumbs
        current_path = ""
        for _i, part in enumerate(path_parts[:-1]):  # Exclude the filename
            current_path = f"{current_path}/{part}" if current_path else part
            dir_breadcrumb = Breadcrumb(
                entity_id=f"{repo_name}/{current_path}",
                name=part,
                entity_type=GitHubDirectoryEntity.__name__,
            )
            breadcrumbs.append(dir_breadcrumb)

        # Get file content
        try:
            file_url = f"{self.BASE_URL}/repos/{repo_name}/contents/{file_path}?ref={branch}"
            file_data = await self._get_with_auth(client, file_url)

            # Check if this is a text file
            file_size = file_data.get("size", 0)
            if file_size > self.max_file_size:
                self.logger.debug(f"Skipping large file: {file_path} ({file_size} bytes)")
                return

            # Get file content
            content_url = file_data["download_url"]
            content_response = await client.get(content_url)
            content_response.raise_for_status()
            content_text = content_response.text

            # Check if this is a text file based on content
            if not self._is_text_content(content_text):
                self.logger.debug(f"Skipping binary file: {file_path}")
                return

            # Detect language
            language = self._detect_language_from_extension(file_path)

            # Count lines
            line_count = content_text.count("\n") + 1

            # Determine file type from mime_type
            mime_type = mimetypes.guess_type(file_path)[0] or "text/plain"
            file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

            # Create file entity (without content field)
            file_entity = GitHubCodeFileEntity(
                breadcrumbs=breadcrumbs,
                full_path=f"{repo_name}/{file_path}",
                name=path_parts[-1],
                branch=branch,
                url=file_data.get("download_url") or file_data.get("html_url", ""),
                size=file_size,
                file_type=file_type,
                mime_type=mime_type,
                local_path=None,  # Will be set by file_downloader
                # Code file fields
                repo_name=repo,
                path_in_repo=file_path,
                repo_owner=owner,
                language=language,
                commit_id=file_data["sha"],
                # API fields
                html_url=file_data.get("html_url"),
                sha=file_data["sha"],
                line_count=line_count,
                is_binary=False,
            )

            # Write content to disk for uniform file handling
            await self.file_downloader.save_bytes(
                entity=file_entity,
                content=content_text.encode("utf-8"),
                filename_with_extension=file_path,  # GitHub file path (has extension)
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
            self.logger.error(f"Error processing changed file {file_path}: {e}")

    def _is_text_content(self, content: str) -> bool:
        """Check if content appears to be text.

        Args:
            content: File content

        Returns:
            True if content appears to be text
        """
        # Check for null bytes (common in binary files)
        if "\x00" in content:
            return False

        # Check if content is mostly printable characters
        printable_ratio = sum(1 for c in content[:1000] if c.isprintable() or c.isspace()) / min(
            len(content), 1000
        )
        return printable_ratio > 0.7

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
        processed_files: set,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Recursively traverse a directory using DFS.

        Args:
            client: HTTP client
            repo_name: Repository name
            path: Current path to traverse
            breadcrumbs: Current breadcrumb chain
            owner: Repository owner
            repo: Repository name
            branch: Branch name
            processed_paths: Set of already processed directory paths
            processed_files: Set of already processed file paths

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
                        breadcrumbs=breadcrumbs.copy(),
                        full_path=f"{repo_name}/{item_path}",
                        name=Path(item_path).name,
                        path=item_path,
                        repo_name=repo,
                        repo_owner=owner,
                        branch=branch,
                    )

                    # Create breadcrumb for this directory
                    dir_breadcrumb = Breadcrumb(
                        entity_id=dir_entity.full_path,
                        name=dir_entity.name,
                        entity_type=GitHubDirectoryEntity.__name__,
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
                        processed_files,
                    ):
                        yield child_entity

                elif item_type == "file":
                    # Skip if already processed
                    if item_path in processed_files:
                        continue

                    processed_files.add(item_path)

                    # Process the file and yield entities
                    async for file_entity in self._process_file(
                        client, repo_name, item_path, item, breadcrumbs, owner, repo, branch
                    ):
                        yield file_entity

        except Exception as e:
            self.logger.error(f"Error traversing path {path}: {str(e)}")

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
    ) -> AsyncGenerator[BaseEntity, None]:
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
                        self.logger.error(f"Error counting lines for {item_path}: {str(e)}")

                # Determine file type from mime_type
                mime_type = mimetypes.guess_type(item_path)[0] or "text/plain"
                file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

                # Create file entity (without content field)
                file_entity = GitHubCodeFileEntity(
                    breadcrumbs=breadcrumbs.copy(),
                    full_path=f"{repo_name}/{item_path}",
                    name=file_name,
                    branch=branch,
                    url=file_data.get("download_url") or file_data["html_url"],
                    size=file_size,
                    file_type=file_type,
                    mime_type=mime_type,
                    local_path=None,  # Will be set by file_downloader
                    # Code file fields
                    repo_name=repo,
                    path_in_repo=item_path,
                    repo_owner=owner,
                    language=language,
                    commit_id=file_data["sha"],
                    # API fields
                    html_url=file_data.get("html_url"),
                    sha=file_data["sha"],
                    line_count=line_count,
                    is_binary=False,
                )

                # Write content to disk for uniform file handling
                await self.file_downloader.save_bytes(
                    entity=file_entity,
                    content=content_text.encode("utf-8"),
                    filename_with_extension=item_path,  # GitHub file path (has extension)
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

    def _get_cursor_timestamp(self) -> str:
        """Get last repository pushed timestamp from cursor.

        Returns:
            Last repository pushed_at timestamp, or None if no cursor exists
        """
        cursor_data = self.cursor.data if self.cursor else {}
        last_pushed_at = cursor_data.get("last_repository_pushed_at")

        if last_pushed_at:
            self.logger.debug(f"📊 Incremental sync from cursor: {last_pushed_at}")
        else:
            self.logger.debug("🔄 Full sync (no cursor)")

        return last_pushed_at

    async def _verify_branch(self, client: httpx.AsyncClient, branch: str) -> None:
        """Verify that the specified branch exists in the repository.

        Args:
            client: HTTP client
            branch: Branch name to verify
        """
        if hasattr(self, "branch") and self.branch:
            # Get list of branches for the repository
            branches_url = f"{self.BASE_URL}/repos/{self.repo_name}/branches"
            branches_data = await self._get_paginated_results(client, branches_url)
            branch_names = [b["name"] for b in branches_data]

            if branch not in branch_names:
                available_branches = ", ".join(branch_names)
                raise ValueError(
                    f"Branch '{branch}' not found in repository '{self.repo_name}'. "
                    f"Available branches: {available_branches}"
                )

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from GitHub repository with incremental support.

        Yields:
            Repository, directory, and file entities
        """
        if not hasattr(self, "repo_name") or not self.repo_name:
            raise ValueError("Repository name must be specified")

        # Get cursor timestamp for incremental sync
        last_pushed_at = self._get_cursor_timestamp()

        async with self.http_client() as client:
            repo_url = f"{self.BASE_URL}/repos/{self.repo_name}"
            repo_data = await self._get_with_auth(client, repo_url)
            current_pushed_at = repo_data["pushed_at"]

            # Use specified branch if available, otherwise use default branch
            branch = (
                self.branch
                if hasattr(self, "branch") and self.branch
                else repo_data["default_branch"]
            )

            # Verify that the branch exists
            await self._verify_branch(client, branch)

            # Check if we should perform incremental sync
            should_sync = True
            if last_pushed_at and current_pushed_at <= last_pushed_at:
                self.logger.debug(
                    f"Repository {self.repo_name} has no new commits since last sync, "
                    "skipping file traversal"
                )
                should_sync = False

            if should_sync:
                self.logger.debug(f"Using branch: {branch} for repo {self.repo_name}")

                # Check if this is an incremental sync (we have a cursor value)
                if last_pushed_at:
                    self.logger.debug(
                        f"Performing INCREMENTAL sync - changes since {last_pushed_at}"
                    )
                    async for entity in self._traverse_repository_incremental(
                        client, self.repo_name, branch, last_pushed_at
                    ):
                        yield entity
                else:
                    self.logger.debug("Performing FULL sync - no previous cursor data")
                    async for entity in self._traverse_repository(client, self.repo_name, branch):
                        yield entity
            else:
                # Still yield repository entity for cursor update, but skip file traversal
                repo_entity = await self._get_repository_info(client, self.repo_name)
                yield repo_entity

    async def validate(self) -> bool:
        """Verify GitHub PAT and repo/branch access with lightweight pings."""
        if not getattr(self, "personal_access_token", None):
            self.logger.error("GitHub validation failed: missing personal_access_token.")
            return False

        headers = {
            "Authorization": f"token {self.personal_access_token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        try:
            async with self.http_client(timeout=10.0) as client:
                # 1) Token validity
                me = await client.get(f"{self.BASE_URL}/user", headers=headers)
                if not (200 <= me.status_code < 300):
                    self.logger.warning(
                        f"GitHub /user ping failed: {me.status_code} - {me.text[:200]}"
                    )
                    return False

                # 2) Repo reachability (optional but recommended for this connector)
                if getattr(self, "repo_name", None):
                    repo = await client.get(
                        f"{self.BASE_URL}/repos/{self.repo_name}", headers=headers
                    )
                    if not (200 <= repo.status_code < 300):
                        self.logger.warning(
                            f"GitHub repo '{self.repo_name}' check failed: "
                            f"{repo.status_code} - {repo.text[:200]}"
                        )
                        return False

                    # 3) Branch existence (only if user specified a branch)
                    if getattr(self, "branch", None):
                        br = await client.get(
                            f"{self.BASE_URL}/repos/{self.repo_name}/branches/{self.branch}",
                            headers=headers,
                        )
                        if not (200 <= br.status_code < 300):
                            self.logger.warning(
                                f"GitHub branch '{self.branch}' not found or inaccessible in "
                                f"'{self.repo_name}': {br.status_code} - {br.text[:200]}"
                            )
                            return False

            return True

        except httpx.RequestError as e:
            self.logger.error(f"GitHub validation request error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during GitHub validation: {e}")
            return False
