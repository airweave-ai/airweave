r"""GitHub source implementation for syncing repositories, directories, and code files."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import (
    AuthProviderKind,
    TokenProviderProtocol,
)
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.auth import GitHubAuthConfig
from airweave.platform.configs.config import GitHubConfig
from airweave.platform.cursors import GitHubCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.github import (
    GitHubCodeFileEntity,
    GitHubDirectoryEntity,
    GitHubFileDeletionEntity,
    GitHubPRCommentEntity,
    GitHubPullRequestEntity,
    GitHubRepositoryEntity,
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
from airweave.schemas.source_connection import AuthenticationMethod

if TYPE_CHECKING:
    from airweave.domains.sync_pipeline.source_hash_lookup import SourceHashLookup


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

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: GitHubConfig,
    ) -> GitHubSource:
        """Create a new source instance with authentication."""
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        if auth.provider_kind == AuthProviderKind.CREDENTIAL:
            instance._personal_access_token = auth.credentials.personal_access_token
        else:
            instance._personal_access_token = await auth.get_token()
        instance._repo_name = config.repo_name
        instance._branch = config.branch or None
        instance._sync_pull_requests = config.sync_pull_requests
        instance._max_file_size = 10 * 1024 * 1024
        return instance

    def get_default_cursor_field(self) -> Optional[str]:
        """Get the default cursor field for GitHub source."""
        return "last_repository_pushed_at"

    def validate_cursor_field(self, cursor_field: str) -> None:
        """Validate if the given cursor field is valid for GitHub.

        Args:
            cursor_field: The cursor field to validate

        Raises:
            ValueError: If the cursor field is invalid
        """
        valid_field = self.get_default_cursor_field()
        if cursor_field != valid_field:
            error_msg = (
                f"Invalid cursor field '{cursor_field}' for GitHub source. "
                f"GitHub requires '{valid_field}' as the cursor field. "
                f"GitHub tracks repository changes using push timestamps, not entity fields. "
                f"Please use the default cursor field or omit it entirely."
            )
            self.logger.warning(error_msg)
            raise ValueError(error_msg)

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make authenticated API request using Personal Access Token."""
        headers = {
            "Authorization": f"token {self._personal_access_token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        response = await self.http_client.get(url, headers=headers, params=params)

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers["Authorization"] = f"token {new_token}"
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
        """Get all pages of results from a paginated GitHub API endpoint."""
        if params is None:
            params = {}

        params["per_page"] = 100

        all_results = []
        page = 1

        while True:
            params["page"] = page
            headers = {
                "Authorization": f"token {self._personal_access_token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }

            response = await self.http_client.get(url, headers=headers, params=params)

            if response.status_code == 401 and self.auth.supports_refresh:
                new_token = await self.auth.force_refresh()
                headers["Authorization"] = f"token {new_token}"
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

            link_header = response.headers.get("Link", "")
            if 'rel="next"' not in link_header:
                break

            page += 1

        return all_results

    def _detect_language_from_extension(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        return get_language_for_extension(ext)

    def _check_repository_updates(
        self, repo_name: str, last_pushed_at: str, current_pushed_at: str
    ) -> bool:
        """Check if repository has been updated since last sync."""
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
        self, repo_name: str, cursor: SyncCursor | None = None
    ) -> GitHubRepositoryEntity:
        """Get repository information with cursor support."""
        url = f"{self.BASE_URL}/repos/{repo_name}"
        repo_data = await self._get(url)

        cursor_data = cursor.data if cursor else {}

        last_pushed_at = cursor_data.get("last_repository_pushed_at")
        current_pushed_at = repo_data["pushed_at"]

        self._check_repository_updates(repo_name, last_pushed_at, current_pushed_at)

        if cursor:
            cursor.update(
                last_repository_pushed_at=current_pushed_at,
                repo_name=repo_name,
                branch=self._branch,
            )

        return GitHubRepositoryEntity.from_api(repo_data)

    async def _traverse_repository(
        self,
        repo_name: str,
        branch: str,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Traverse repository contents using DFS."""
        repo_entity = await self._get_repository_info(repo_name, cursor=cursor)
        yield repo_entity

        owner, repo = repo_name.split("/")

        repo_breadcrumb = Breadcrumb(
            entity_id=str(repo_entity.repo_id),
            name=repo_entity.name,
            entity_type=GitHubRepositoryEntity.__name__,
        )

        processed_paths = set()
        processed_files = set()

        async for entity in self._traverse_directory(
            repo_name,
            "",
            [repo_breadcrumb],
            owner,
            repo,
            branch,
            processed_paths,
            processed_files,
            files=files,
        ):
            yield entity

    async def _traverse_repository_incremental(
        self,
        repo_name: str,
        branch: str,
        since_timestamp: str,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Traverse repository contents incrementally using commits since last sync."""
        repo_entity = await self._get_repository_info(repo_name, cursor=cursor)
        yield repo_entity

        owner, repo = repo_name.split("/")

        repo_breadcrumb = Breadcrumb(
            entity_id=str(repo_entity.repo_id),
            name=repo_entity.name,
            entity_type=GitHubRepositoryEntity.__name__,
        )

        commits = await self._get_commits_since(repo_name, since_timestamp, branch)

        if not commits:
            self.logger.debug(f"No new commits found since {since_timestamp}")
            return

        self.logger.debug(f"Found {len(commits)} new commits since {since_timestamp}")

        processed_files_set = set()

        for commit in commits:
            commit_sha = commit["sha"]
            commit_message = commit["commit"]["message"]

            self.logger.debug(f"Processing commit {commit_sha[:8]}: {commit_message}")

            changed_files = await self._get_commit_files(repo_name, commit_sha)

            for file_info in changed_files:
                file_path = file_info["filename"]

                if file_path in processed_files_set:
                    continue

                processed_files_set.add(file_path)

                if file_info["status"] == "removed":
                    self.logger.debug(f"Processing deleted file: {file_path}")
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

                try:
                    async for entity in self._process_changed_file(
                        repo_name, file_path, owner, repo, branch, repo_breadcrumb, files=files
                    ):
                        yield entity
                except SourceAuthError:
                    raise
                except Exception as e:
                    self.logger.warning(f"Error processing changed file {file_path}: {e}")

    async def _get_commits_since(
        self, repo_name: str, since_timestamp: str, branch: str
    ) -> List[Dict[str, Any]]:
        """Get commits since a specific timestamp."""
        url = f"{self.BASE_URL}/repos/{repo_name}/commits"
        params = {
            "since": since_timestamp,
            "sha": branch,
            "per_page": 100,
        }

        commits = await self._get_paginated_results(url, params)
        self.logger.debug(f"Retrieved {len(commits)} commits since {since_timestamp}")
        return commits

    async def _get_commit_files(self, repo_name: str, commit_sha: str) -> List[Dict[str, Any]]:
        """Get files changed in a specific commit."""
        url = f"{self.BASE_URL}/repos/{repo_name}/commits/{commit_sha}"

        try:
            commit_data = await self._get(url)
            files_list = commit_data.get("files", [])
            self.logger.debug(f"Commit {commit_sha[:8]} changed {len(files_list)} files")
            return files_list
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error getting files for commit {commit_sha}: {e}")
            return []

    async def _process_changed_file(
        self,
        repo_name: str,
        file_path: str,
        owner: str,
        repo: str,
        branch: str,
        repo_breadcrumb: Breadcrumb,
        *,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a single changed file."""
        path_parts = file_path.split("/")
        breadcrumbs = [repo_breadcrumb]

        current_path = ""
        for _i, part in enumerate(path_parts[:-1]):
            current_path = f"{current_path}/{part}" if current_path else part
            dir_breadcrumb = Breadcrumb(
                entity_id=f"{repo_name}/{current_path}",
                name=part,
                entity_type=GitHubDirectoryEntity.__name__,
            )
            breadcrumbs.append(dir_breadcrumb)

        try:
            file_url = f"{self.BASE_URL}/repos/{repo_name}/contents/{file_path}?ref={branch}"
            file_data = await self._get(file_url)

            file_size = file_data.get("size", 0)
            if file_size > self._max_file_size:
                self.logger.debug(f"Skipping large file: {file_path} ({file_size} bytes)")
                return

            content_url = file_data["download_url"]
            content_response = await self.http_client.get(content_url)
            content_response.raise_for_status()
            content_text = content_response.text

            if not self._is_text_content(content_text):
                self.logger.debug(f"Skipping binary file: {file_path}")
                return

            language = self._detect_language_from_extension(file_path)
            line_count = content_text.count("\n") + 1
            mime_type = mimetypes.guess_type(file_path)[0] or "text/plain"
            file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

            file_entity = GitHubCodeFileEntity(
                breadcrumbs=breadcrumbs,
                full_path=f"{repo_name}/{file_path}",
                name=path_parts[-1],
                branch=branch,
                url=file_data.get("download_url") or file_data.get("html_url", ""),
                size=file_size,
                file_type=file_type,
                mime_type=mime_type,
                local_path=None,
                repo_name=repo,
                path_in_repo=file_path,
                repo_owner=owner,
                language=language,
                commit_id=file_data["sha"],
                html_url=file_data.get("html_url"),
                sha=file_data["sha"],
                line_count=line_count,
                is_binary=False,
                source_hash=f"sha1:{file_data['sha']}" if file_data.get("sha") else None,
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
            self.logger.warning(f"Error processing changed file {file_path}: {e}")

    def _is_text_content(self, content: str) -> bool:
        """Check if content appears to be text."""
        if "\x00" in content:
            return False
        printable_ratio = sum(1 for c in content[:1000] if c.isprintable() or c.isspace()) / min(
            len(content), 1000
        )
        return printable_ratio > 0.7

    async def _traverse_directory(  # noqa: C901
        self,
        repo_name: str,
        path: str,
        breadcrumbs: List[Breadcrumb],
        owner: str,
        repo: str,
        branch: str,
        processed_paths: set,
        processed_files: set,
        *,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Recursively traverse a directory using DFS."""
        if path in processed_paths:
            return

        processed_paths.add(path)

        url = f"{self.BASE_URL}/repos/{repo_name}/contents/{path}"
        params = {"ref": branch}

        try:
            contents = await self._get(url, params)

            if isinstance(contents, List):
                items = contents
            else:
                items = [contents]

            for item in items:
                item_path = item["path"]
                item_type = item["type"]

                if item_type == "dir":
                    dir_entity = GitHubDirectoryEntity(
                        breadcrumbs=breadcrumbs.copy(),
                        full_path=f"{repo_name}/{item_path}",
                        name=Path(item_path).name,
                        path=item_path,
                        repo_name=repo,
                        repo_owner=owner,
                        branch=branch,
                    )

                    dir_breadcrumb = Breadcrumb(
                        entity_id=dir_entity.full_path,
                        name=dir_entity.name,
                        entity_type=GitHubDirectoryEntity.__name__,
                    )

                    yield dir_entity

                    dir_breadcrumbs = breadcrumbs.copy() + [dir_breadcrumb]

                    async for child_entity in self._traverse_directory(
                        repo_name,
                        item_path,
                        dir_breadcrumbs,
                        owner,
                        repo,
                        branch,
                        processed_paths,
                        processed_files,
                        files=files,
                    ):
                        yield child_entity

                elif item_type == "file":
                    if item_path in processed_files:
                        continue

                    processed_files.add(item_path)

                    async for file_entity in self._process_file(
                        repo_name, item_path, item, breadcrumbs, owner, repo, branch, files=files
                    ):
                        yield file_entity

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error traversing path {path}: {str(e)}")

    async def _process_file(  # noqa: C901
        self,
        repo_name: str,
        item_path: str,
        item: Dict[str, Any],
        breadcrumbs: List[Breadcrumb],
        owner: str,
        repo: str,
        branch: str,
        *,
        files: FileService | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a file item and create file entities."""
        try:
            file_url = f"{self.BASE_URL}/repos/{repo_name}/contents/{item_path}"
            file_data = await self._get(file_url, {"ref": branch})
            file_size = file_data.get("size", 0)

            content_sample = None
            content_text = None
            if file_data.get("encoding") == "base64" and file_data.get("content"):
                try:
                    content_sample = base64.b64decode(file_data["content"])
                    content_text = content_sample.decode("utf-8", errors="replace")
                except Exception:
                    pass

            if is_text_file(item_path, file_size, content_sample):
                language = self._detect_language_from_extension(item_path)
                file_name = Path(item_path).name

                line_count = 0
                if content_text:
                    try:
                        line_count = content_text.count("\n") + 1
                    except Exception as e:
                        self.logger.warning(f"Error counting lines for {item_path}: {str(e)}")

                mime_type = mimetypes.guess_type(item_path)[0] or "text/plain"
                file_type = mime_type.split("/")[0] if "/" in mime_type else "file"

                file_entity = GitHubCodeFileEntity(
                    breadcrumbs=breadcrumbs.copy(),
                    full_path=f"{repo_name}/{item_path}",
                    name=file_name,
                    branch=branch,
                    url=file_data.get("download_url") or file_data["html_url"],
                    size=file_size,
                    file_type=file_type,
                    mime_type=mime_type,
                    local_path=None,
                    repo_name=repo,
                    path_in_repo=item_path,
                    repo_owner=owner,
                    language=language,
                    commit_id=file_data["sha"],
                    html_url=file_data.get("html_url"),
                    sha=file_data["sha"],
                    line_count=line_count,
                    is_binary=False,
                    source_hash=f"sha1:{file_data['sha']}" if file_data.get("sha") else None,
                )

                if files and content_text:
                    await files.save_bytes(
                        entity=file_entity,
                        content=content_text.encode("utf-8"),
                        filename_with_extension=item_path,
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
            self.logger.warning(f"Error processing file {item_path}: {str(e)}")

    def _get_cursor_timestamp(self, cursor: SyncCursor | None) -> str:
        """Get last repository pushed timestamp from cursor."""
        cursor_data = cursor.data if cursor else {}
        last_pushed_at = cursor_data.get("last_repository_pushed_at")

        if last_pushed_at:
            self.logger.debug(f"Incremental sync from cursor: {last_pushed_at}")
        else:
            self.logger.debug("Full sync (no cursor)")

        return last_pushed_at

    async def _verify_branch(self, branch: str) -> None:
        """Verify that the specified branch exists in the repository."""
        if self._branch:
            branches_url = f"{self.BASE_URL}/repos/{self._repo_name}/branches"
            branches_data = await self._get_paginated_results(branches_url)
            branch_names = [b["name"] for b in branches_data]

            if branch not in branch_names:
                available_branches = ", ".join(branch_names)
                raise ValueError(
                    f"Branch '{branch}' not found in repository '{self._repo_name}'. "
                    f"Available branches: {available_branches}"
                )

    async def _fetch_merged_pull_requests(
        self,
        repo_name: str,
        repo_breadcrumb: Breadcrumb,
        since: Optional[str] = None,
        cursor: SyncCursor | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Fetch merged pull requests and their review comments."""
        owner, repo = repo_name.split("/")
        url = f"{self.BASE_URL}/repos/{repo_name}/pulls"
        params = {"state": "closed", "sort": "updated", "direction": "desc"}

        all_prs = await self._get_paginated_results(url, params)

        latest_updated_at = since or ""

        for pr_data in all_prs:
            if not pr_data.get("merged_at"):
                continue

            pr_updated = pr_data["updated_at"]

            if since and pr_updated <= since:
                continue

            if pr_updated > latest_updated_at:
                latest_updated_at = pr_updated

            pr_number = pr_data["number"]

            pr_breadcrumb = Breadcrumb(
                entity_id=f"{repo_name}#{pr_number}",
                name=f"PR #{pr_number}",
                entity_type=GitHubPullRequestEntity.__name__,
            )

            files_data = await self._get_paginated_results(
                f"{self.BASE_URL}/repos/{repo_name}/pulls/{pr_number}/files",
                {},
            )
            changed_paths = [f["filename"] for f in files_data if f.get("filename")]

            pr_entity = GitHubPullRequestEntity.from_api(
                pr_data,
                repo_name=repo,
                repo_owner=owner,
                changed_files_list=changed_paths or None,
                breadcrumbs=[repo_breadcrumb],
            )
            yield pr_entity

            async for comment_entity in self._fetch_pr_review_comments(
                repo_name, pr_number, owner, repo, [repo_breadcrumb, pr_breadcrumb]
            ):
                yield comment_entity

        if cursor and latest_updated_at and latest_updated_at != since:
            cursor.update(last_pr_updated_at=latest_updated_at)

    async def _fetch_pr_review_comments(
        self,
        repo_name: str,
        pr_number: int,
        owner: str,
        repo: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[BaseEntity, None]:
        """Fetch review comments (inline code comments) for a single PR."""
        url = f"{self.BASE_URL}/repos/{repo_name}/pulls/{pr_number}/comments"
        try:
            comments = await self._get_paginated_results(url)
        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error fetching review comments for PR #{pr_number}: {e}")
            return

        for comment in comments:
            yield GitHubPRCommentEntity.from_api(
                comment,
                repo_name=repo,
                repo_owner=owner,
                pr_number=pr_number,
                breadcrumbs=breadcrumbs.copy(),
            )

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
        source_hash_lookup: SourceHashLookup | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from GitHub repository with incremental support.

        Yields:
            Repository, directory, file, pull request, and PR comment entities
        """
        if not self._repo_name:
            raise ValueError("Repository name must be specified")

        last_pushed_at = self._get_cursor_timestamp(cursor)

        repo_url = f"{self.BASE_URL}/repos/{self._repo_name}"
        repo_data = await self._get(repo_url)
        current_pushed_at = repo_data["pushed_at"]

        branch = self._branch if self._branch else repo_data["default_branch"]

        await self._verify_branch(branch)

        should_sync = True
        if last_pushed_at and current_pushed_at <= last_pushed_at:
            self.logger.debug(
                f"Repository {self._repo_name} has no new commits since last sync, "
                "skipping file traversal"
            )
            should_sync = False

        if should_sync:
            self.logger.debug(f"Using branch: {branch} for repo {self._repo_name}")

            if last_pushed_at:
                self.logger.debug(f"Performing INCREMENTAL sync - changes since {last_pushed_at}")
                async for entity in self._traverse_repository_incremental(
                    self._repo_name, branch, last_pushed_at, cursor=cursor, files=files
                ):
                    yield entity
            else:
                self.logger.debug("Performing FULL sync - no previous cursor data")
                async for entity in self._traverse_repository(
                    self._repo_name, branch, cursor=cursor, files=files
                ):
                    yield entity
        else:
            repo_entity = await self._get_repository_info(self._repo_name, cursor=cursor)
            yield repo_entity

        if self._sync_pull_requests:
            cursor_data = cursor.data if cursor else {}
            last_pr_updated = cursor_data.get("last_pr_updated_at") or None

            repo_breadcrumb = Breadcrumb(
                entity_id=str(repo_data["id"]),
                name=repo_data["name"],
                entity_type=GitHubRepositoryEntity.__name__,
            )

            if last_pr_updated:
                self.logger.debug(f"Incremental PR sync - changes since {last_pr_updated}")
            else:
                self.logger.debug("Full PR sync - no previous cursor data")

            async for entity in self._fetch_merged_pull_requests(
                self._repo_name, repo_breadcrumb, since=last_pr_updated, cursor=cursor
            ):
                yield entity

    async def validate(self) -> None:
        """Verify GitHub PAT and optional repo/branch access via the same path as sync.

        Uses :meth:`_get` (Airweave client + ``raise_for_status``) so failures surface as
        the same domain errors as the rest of the connector. Relies on :meth:`create` for
        ``_personal_access_token``, ``_repo_name``, and ``_branch``.
        """
        if self._repo_name:
            await self._get(f"{self.BASE_URL}/repos/{self._repo_name}")
            if self._branch:
                await self._get(f"{self.BASE_URL}/repos/{self._repo_name}/branches/{self._branch}")
