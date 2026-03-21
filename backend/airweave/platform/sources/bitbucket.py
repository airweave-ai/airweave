"""Bitbucket source implementation for syncing repositories, workspaces, and code files."""

import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import SourceAuthError
from airweave.domains.sources.token_providers.protocol import SourceAuthProvider
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
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
        cls,
        *,
        auth: SourceAuthProvider,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: BitbucketConfig,
    ) -> "BitbucketSource":
        """Create a new source instance with authentication.

        Supports two auth modes:
        - Direct (API token): Basic Auth with email:token. Workspace/repo from creds.
        - OAuth (auth provider): Bearer token. Workspace/repo from config.
        """
        instance = cls(auth=auth, logger=logger, http_client=http_client)
        creds: BitbucketAuthConfig = auth.credentials
        instance._access_token = creds.access_token
        instance._email = getattr(creds, "email", None) or None

        instance._workspace = config.workspace or getattr(creds, "workspace", None) or ""
        instance._repo_slug = config.repo_slug or getattr(creds, "repo_slug", None) or ""
        instance._branch = config.branch
        instance._file_extensions = config.file_extensions
        return instance

    def _auth_kwargs(self, accept: str = "application/json") -> Dict[str, Any]:
        """Build auth kwargs for httpx requests.

        Uses Basic Auth when email is available (direct API token),
        Bearer token otherwise (OAuth).
        """
        headers: Dict[str, str] = {"Accept": accept}
        kwargs: Dict[str, Any] = {"headers": headers}
        if self._email:
            kwargs["auth"] = httpx.BasicAuth(username=self._email, password=self._access_token)
        else:
            headers["Authorization"] = f"Bearer {self._access_token}"
        return kwargs

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Make authenticated API request.

        Retries on 429 rate limits and timeout errors.
        """
        response = await self.http_client.get(url, params=params, **self._auth_kwargs())
        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )
        return response.json()

    async def _get_paginated_results(
        self, url: str, params: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Get all pages of results from a paginated Bitbucket API endpoint."""
        if params is None:
            params = {}

        all_results = []
        next_url = url
        auth_kwargs = self._auth_kwargs()

        while next_url:
            response = await self.http_client.get(
                next_url, params=params if next_url == url else None, **auth_kwargs
            )
            raise_for_status(
                response,
                source_short_name=self.short_name,
                token_provider_kind=self.auth.provider_kind,
            )

            data = response.json()
            results = data.get("values", [])
            all_results.extend(results)

            next_url = data.get("next")

        return all_results

    def _detect_language_from_extension(self, file_path: str) -> str:
        """Detect programming language from file extension."""
        ext = Path(file_path).suffix.lower()
        return get_language_for_extension(ext)

    def _should_include_file(self, file_path: str) -> bool:
        """Check if a file should be included based on configured extensions."""
        if not self._file_extensions:
            return True

        if ".*" in self._file_extensions:
            return True

        file_ext = Path(file_path).suffix.lower()
        return any(file_ext == ext.lower() for ext in self._file_extensions)

    async def _get_workspace_info(self, workspace_slug: str) -> BitbucketWorkspaceEntity:
        """Get workspace information."""
        url = f"{self.BASE_URL}/workspaces/{workspace_slug}"
        workspace_data = await self._get(url)

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
        self, workspace_slug: str, repo_slug: str
    ) -> BitbucketRepositoryEntity:
        """Get repository information."""
        url = f"{self.BASE_URL}/repositories/{workspace_slug}/{repo_slug}"
        repo_data = await self._get(url)

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

    async def _get_repositories(self, workspace_slug: str) -> List[Dict[str, Any]]:
        """Get all repositories in a workspace."""
        url = f"{self.BASE_URL}/repositories/{workspace_slug}"
        return await self._get_paginated_results(url)

    async def _traverse_repository(
        self,
        workspace_slug: str,
        repo_slug: str,
        branch: str,
        parent_breadcrumbs: List[Breadcrumb],
        files: FileService | None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Traverse repository contents using DFS."""
        repo_entity = await self._get_repository_info(workspace_slug, repo_slug)
        repo_entity.breadcrumbs = parent_breadcrumbs.copy()
        yield repo_entity

        repo_breadcrumb = Breadcrumb(
            entity_id=repo_entity.uuid,
            name=repo_entity.repo_name,
            entity_type="BitbucketRepositoryEntity",
        )

        processed_paths: set = set()
        initial_breadcrumbs = parent_breadcrumbs + [repo_breadcrumb]

        async for entity in self._traverse_directory(
            workspace_slug,
            repo_slug,
            "",
            initial_breadcrumbs,
            branch,
            processed_paths,
            files,
        ):
            yield entity

    async def _traverse_directory(
        self,
        workspace_slug: str,
        repo_slug: str,
        path: str,
        breadcrumbs: List[Breadcrumb],
        branch: str,
        processed_paths: set,
        files: FileService | None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Recursively traverse a directory using DFS."""
        if path in processed_paths:
            return

        processed_paths.add(path)

        url = f"{self.BASE_URL}/repositories/{workspace_slug}/{repo_slug}/src/{branch}/{path}"

        try:
            contents = await self._get_paginated_results(url)

            for item in contents:
                item_path = item["path"]
                item_type = item.get("type", "file")

                if item_type == "commit_directory":
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

                    yield dir_entity

                    dir_breadcrumbs = breadcrumbs.copy() + [dir_breadcrumb]

                    async for child_entity in self._traverse_directory(
                        workspace_slug,
                        repo_slug,
                        item_path,
                        dir_breadcrumbs,
                        branch,
                        processed_paths,
                        files,
                    ):
                        yield child_entity

                elif item_type == "commit_file":
                    if self._should_include_file(item_path):
                        async for file_entity in self._process_file(
                            workspace_slug,
                            repo_slug,
                            item_path,
                            item,
                            breadcrumbs,
                            branch,
                            files,
                        ):
                            yield file_entity

        except SourceAuthError:
            raise
        except Exception as e:
            self.logger.warning(f"Error traversing path {path}: {str(e)}")

    async def _process_file(
        self,
        workspace_slug: str,
        repo_slug: str,
        item_path: str,
        item: Dict[str, Any],
        breadcrumbs: List[Breadcrumb],
        branch: str,
        files: FileService | None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Process a file item and create file entities."""
        try:
            file_url = (
                f"{self.BASE_URL}/repositories/{workspace_slug}/{repo_slug}"
                f"/src/{branch}/{item_path}"
            )

            file_response = await self.http_client.get(
                file_url,
                params={"format": "raw"},
                **self._auth_kwargs(accept="text/plain"),
            )
            raise_for_status(
                file_response,
                source_short_name=self.short_name,
                token_provider_kind=self.auth.provider_kind,
            )

            content_text = file_response.text
            file_size = len(content_text.encode("utf-8"))

            content_sample = content_text.encode("utf-8")[:1024] if content_text else None
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
                commit_hash = item.get("commit", {}).get("hash", "")

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

                if files:
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

    async def generate_entities(
        self,
        *,
        cursor: SyncCursor | None = None,
        files: FileService | None = None,
        node_selections: list[NodeSelectionData] | None = None,
    ) -> AsyncGenerator[BaseEntity, None]:
        """Generate entities from Bitbucket.

        Yields:
            Workspace, repository, directory, and file entities
        """
        if not self._workspace:
            raise ValueError("Workspace must be specified")

        workspace_entity = await self._get_workspace_info(self._workspace)
        yield workspace_entity

        workspace_breadcrumb = Breadcrumb(
            entity_id=workspace_entity.uuid,
            name=workspace_entity.display_name,
            entity_type="BitbucketWorkspaceEntity",
        )

        if self._repo_slug:
            repo_data = await self._get_repository_info(self._workspace, self._repo_slug)

            branch = self._branch or repo_data.mainbranch or "master"
            self.logger.debug(f"Using branch: {branch} for repo {self._repo_slug}")

            async for entity in self._traverse_repository(
                self._workspace, self._repo_slug, branch, [workspace_breadcrumb], files
            ):
                if isinstance(entity, BitbucketRepositoryEntity):
                    entity.breadcrumbs = [workspace_breadcrumb]
                yield entity
        else:
            repositories = await self._get_repositories(self._workspace)

            for repo_data in repositories:
                repo_slug = repo_data["slug"]

                repo_entity = await self._get_repository_info(self._workspace, repo_slug)

                branch = self._branch or repo_entity.mainbranch or "master"
                self.logger.debug(f"Using branch: {branch} for repo {repo_slug}")

                async for entity in self._traverse_repository(
                    self._workspace, repo_slug, branch, [workspace_breadcrumb], files
                ):
                    if isinstance(entity, BitbucketRepositoryEntity):
                        entity.breadcrumbs = [workspace_breadcrumb]
                    yield entity

    async def validate(self) -> None:
        """Verify Bitbucket Basic Auth and (if provided) workspace access."""
        await self._get(f"{self.BASE_URL}/user")
