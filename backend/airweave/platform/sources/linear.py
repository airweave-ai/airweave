"""Linear source implementation for Airweave platform."""

from __future__ import annotations

import mimetypes
import os
import re
import time
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, List, Optional, Union
from uuid import uuid4

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.logging import ContextualLogger
from airweave.core.shared_models import RateLimitLevel
from airweave.domains.browse_tree.types import NodeSelectionData
from airweave.domains.sources.exceptions import (
    SourceAuthError,
    SourceError,
    SourceRateLimitError,
)
from airweave.domains.sources.token_providers.protocol import TokenProviderProtocol
from airweave.domains.storage import FileSkippedException
from airweave.domains.storage.file_service import FileService
from airweave.domains.syncs.cursors.cursor import SyncCursor
from airweave.platform.configs.config import LinearConfig
from airweave.platform.cursors.linear import LinearCursor
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.linear import (
    LinearAttachmentEntity,
    LinearCommentEntity,
    LinearIssueEntity,
    LinearProjectEntity,
    LinearTeamEntity,
    LinearUserEntity,
)
from airweave.platform.http_client.airweave_client import AirweaveHttpClient
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.http_helpers import raise_for_status
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

_GRAPHQL_URL = "https://api.linear.app/graphql"


def _is_graphql_rate_limited(body: Dict) -> bool:
    """Check if a Linear GraphQL response contains a RATELIMITED error."""
    for err in body.get("errors", []):
        if err.get("extensions", {}).get("code") == "RATELIMITED":
            return True
    return False


def _parse_reset_header(response: httpx.Response, default: float = 60.0) -> float:
    """Compute seconds-until-reset from ``X-RateLimit-Requests-Reset`` (epoch ms)."""
    raw = response.headers.get("X-RateLimit-Requests-Reset")
    if raw:
        try:
            reset_epoch_s = int(raw) / 1000.0
            return max(1.0, reset_epoch_s - time.time())
        except (ValueError, TypeError):
            pass
    return default


@source(
    name="Linear",
    short_name="linear",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.ACCESS_ONLY,
    auth_config_class=None,
    config_class=LinearConfig,
    labels=["Project Management"],
    supports_continuous=True,
    cursor_class=LinearCursor,
    rate_limit_level=RateLimitLevel.ORG,
)
class LinearSource(BaseSource):
    """Linear source connector — syncs teams, projects, users, issues, comments, attachments."""

    @classmethod
    async def create(
        cls,
        *,
        auth: TokenProviderProtocol,
        logger: ContextualLogger,
        http_client: AirweaveHttpClient,
        config: LinearConfig,
    ) -> LinearSource:
        """Create a new Linear source instance."""
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
    async def _post(self, query: str) -> Dict:
        """Authenticated GraphQL POST with 401 refresh and raise_for_status.

        Linear returns rate-limit errors as HTTP 400 with a GraphQL
        ``RATELIMITED`` error code (not HTTP 429). We detect this before
        ``raise_for_status`` so the tenacity retry fires correctly.
        """
        token = await self.auth.get_token()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        response = await self.http_client.post(_GRAPHQL_URL, headers=headers, json={"query": query})

        if response.status_code == 401 and self.auth.supports_refresh:
            new_token = await self.auth.force_refresh()
            headers["Authorization"] = f"Bearer {new_token}"
            response = await self.http_client.post(
                _GRAPHQL_URL, headers=headers, json={"query": query}
            )

        body = response.json()

        if response.status_code == 400 and _is_graphql_rate_limited(body):
            retry_after = _parse_reset_header(response)
            raise SourceRateLimitError(
                retry_after=retry_after,
                source_short_name=self.short_name,
                message=f"Linear RATELIMITED (400). Retry after {retry_after:.0f}s",
            )

        raise_for_status(
            response,
            source_short_name=self.short_name,
            token_provider_kind=self.auth.provider_kind,
        )

        return body

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    async def _paginated_query(
        self,
        query_template: str,
        process_node_func,
        page_size: int = 50,
        entity_type: str = "items",
    ) -> AsyncGenerator:
        """Paginate through Linear GraphQL, yielding entities from process_node_func.

        SourceAuthError propagates immediately (abort sync).
        Other errors propagate to the caller (typically _generate_entities_safe).
        """
        has_next_page = True
        after_cursor = None
        items_processed = 0

        while has_next_page:
            pagination = f"first: {page_size}"
            if after_cursor:
                pagination += f', after: "{after_cursor}"'

            query = query_template.format(pagination=pagination)
            response = await self._post(query)

            data = response.get("data", {})
            collection_key = next(iter(data.keys()), None)

            if not collection_key:
                self.logger.warning(
                    "Unexpected response structure: missing expected collection key"
                )
                break

            collection_data = data[collection_key]
            nodes = collection_data.get("nodes", [])

            batch_count = len(nodes)
            items_processed += batch_count
            self.logger.debug(
                f"Processing batch of {batch_count} {entity_type} (total: {items_processed})"
            )

            for node in nodes:
                async for entity in process_node_func(node):
                    if entity:
                        yield entity

            page_info = collection_data.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            after_cursor = page_info.get("endCursor")

            if not nodes or not has_next_page:
                break

    # ------------------------------------------------------------------
    # Entity generators
    # ------------------------------------------------------------------

    async def _generate_team_entities(
        self, since: Optional[str] = None
    ) -> AsyncGenerator[LinearTeamEntity, None]:
        """Generate entities for all teams in the workspace."""
        filter_clause = f'filter: {{{{ updatedAt: {{{{ gte: "{since}" }}}} }}}}, ' if since else ""
        query_template = (
            """
        {{
          teams("""
            + filter_clause
            + """{pagination}) {{
            nodes {{
              id
              name
              key
              description
              color
              icon
              private
              timezone
              createdAt
              updatedAt
              parent {{
                id
                name
              }}
              issueCount
            }}
            pageInfo {{
              hasNextPage
              endCursor
            }}
          }}
        }}
        """
        )

        async def process_team(team):
            self.logger.debug(f"Processing team: {team.get('name')} ({team.get('key')})")
            yield LinearTeamEntity.from_api(team)

        async for entity in self._paginated_query(
            query_template, process_team, entity_type="teams"
        ):
            yield entity

    async def _generate_project_entities(
        self, since: Optional[str] = None
    ) -> AsyncGenerator[LinearProjectEntity, None]:
        """Generate entities for all projects in the workspace."""
        filter_clause = f'filter: {{{{ updatedAt: {{{{ gte: "{since}" }}}} }}}}, ' if since else ""
        query_template = (
            """
        {{
          projects("""
            + filter_clause
            + """{pagination}) {{
            nodes {{
              id
              name
              slugId
              description
              priority
              startDate
              targetDate
              state
              createdAt
              updatedAt
              completedAt
              startedAt
              progress
              teams {{
                nodes {{
                  id
                  name
                }}
              }}
              lead {{
                name
              }}
            }}
            pageInfo {{
              hasNextPage
              endCursor
            }}
          }}
        }}
        """
        )

        async def process_project(project):
            self.logger.debug(f"Processing project: {project.get('name')}")
            yield LinearProjectEntity.from_api(project)

        async for entity in self._paginated_query(
            query_template, process_project, entity_type="projects"
        ):
            yield entity

    async def _generate_user_entities(
        self, since: Optional[str] = None
    ) -> AsyncGenerator[LinearUserEntity, None]:
        """Generate entities for all users in the workspace."""
        filter_clause = f'filter: {{{{ updatedAt: {{{{ gte: "{since}" }}}} }}}}, ' if since else ""
        query_template = (
            """
        {{
          users("""
            + filter_clause
            + """{pagination}) {{
            nodes {{
              id
              name
              displayName
              email
              avatarUrl
              description
              timezone
              active
              admin
              guest
              lastSeen
              statusEmoji
              statusLabel
              statusUntilAt
              createdIssueCount
              createdAt
              updatedAt
              teams {{
                nodes {{
                  id
                  name
                  key
                }}
              }}
            }}
            pageInfo {{
              hasNextPage
              endCursor
            }}
          }}
        }}
        """
        )

        async def process_user(user):
            self.logger.debug(f"Processing user: {user.get('name')} ({user.get('displayName')})")
            yield LinearUserEntity.from_api(user)

        async for entity in self._paginated_query(
            query_template, process_user, entity_type="users"
        ):
            yield entity

    # ------------------------------------------------------------------
    # Issues, comments, and attachments
    # ------------------------------------------------------------------

    async def _process_issue_comments(
        self,
        comments: List[Dict],
        issue: LinearIssueEntity,
        issue_breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[LinearCommentEntity, None]:
        """Yield comment entities for an issue."""
        for comment in comments:
            if not comment.get("body", "").strip():
                continue
            yield LinearCommentEntity.from_api(
                comment,
                issue_id=issue.issue_id,
                issue_identifier=issue.identifier,
                breadcrumbs=issue_breadcrumbs,
                team_id=issue.team_id,
                team_name=issue.team_name,
                project_id=issue.project_id,
                project_name=issue.project_name,
            )

    async def _download_description_attachment(
        self,
        entity: LinearAttachmentEntity,
        files: FileService,
    ) -> LinearAttachmentEntity | None:
        """Download an inline attachment via FileService. Returns None on expected skips.

        401 after refresh propagates (token is dead → abort sync).
        Infrastructure failures (IOError, OSError) propagate.
        Other HTTP errors skip the file.
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
            self.logger.debug(f"Skipping attachment {entity.attachment_id}: {e.reason}")
            return None
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise
            self.logger.warning(
                f"HTTP {e.response.status_code} downloading attachment {entity.attachment_id}: {e}"
            )
            return None

    async def _generate_attachment_entities_from_description(
        self,
        issue_id: str,
        issue_identifier: str,
        issue_description: str,
        breadcrumbs: List[Breadcrumb],
        files: FileService,
    ) -> AsyncGenerator[LinearAttachmentEntity, None]:
        """Extract and download attachments from markdown links in issue descriptions."""
        if not issue_description:
            return

        markdown_link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        matches = re.findall(markdown_link_pattern, issue_description)

        self.logger.debug(
            f"Found {len(matches)} potential attachments in description "
            f"for issue {issue_identifier}"
        )

        for file_name, url in matches:
            if "uploads.linear.app" not in url:
                continue

            self.logger.debug(f"Processing attachment from description: {file_name} - URL: {url}")

            attachment_id = str(uuid4())
            mime_type = mimetypes.guess_type(file_name)[0]
            if mime_type and "/" in mime_type:
                file_type = mime_type.split("/")[0]
            else:
                ext = os.path.splitext(file_name)[1].lower().lstrip(".")
                file_type = ext if ext else "file"

            attachment_entity = LinearAttachmentEntity(
                entity_id=attachment_id,
                breadcrumbs=breadcrumbs.copy(),
                name=file_name,
                created_at=None,
                updated_at=None,
                url=url,
                size=0,
                file_type=file_type,
                mime_type=mime_type or "application/octet-stream",
                local_path=None,
                attachment_id=attachment_id,
                issue_id=issue_id,
                issue_identifier=issue_identifier,
                title=file_name,
                subtitle="Extracted from issue description",
                source={"type": "description_link"},
                web_url_value=url,
            )

            downloaded = await self._download_description_attachment(attachment_entity, files)
            if downloaded:
                yield downloaded

    async def _generate_issue_entities(
        self,
        since: Optional[str] = None,
        files: FileService | None = None,
    ) -> AsyncGenerator[
        Union[LinearIssueEntity, LinearCommentEntity, LinearAttachmentEntity], None
    ]:
        """Generate entities for all issues, their comments, and their attachments."""
        updated_filter = f', updatedAt: {{{{ gte: "{since}" }}}}' if since else ""
        query_template = (
            """
        {{
          issues(filter: {{ archivedAt: {{ null: true }}"""
            + updated_filter
            + """ }}, {pagination}) {{
            nodes {{
              id
              identifier
              title
              description
              priority
              completedAt
              createdAt
              updatedAt
              dueDate
              archivedAt
              state {{
                name
              }}
              team {{
                id
                name
              }}
              project {{
                id
                name
              }}
              assignee {{
                name
              }}
              comments {{
                nodes {{
                  id
                  body
                  createdAt
                  updatedAt
                  user {{
                    id
                    name
                  }}
                }}
              }}
            }}
            pageInfo {{
              hasNextPage
              endCursor
            }}
          }}
        }}
        """
        )

        async def process_issue(data):
            if data.get("archivedAt"):
                self.logger.warning(
                    f"Archived issue {data.get('identifier')} passed GraphQL filter — skipping"
                )
                return

            self.logger.debug(f"Processing issue: {data.get('identifier')} — '{data.get('title')}'")

            issue = LinearIssueEntity.from_api(data)
            yield issue

            issue_breadcrumbs = issue.breadcrumbs + [
                Breadcrumb(
                    entity_id=issue.issue_id,
                    name=issue.title,
                    entity_type=LinearIssueEntity.__name__,
                )
            ]

            comments = data.get("comments", {}).get("nodes", [])
            self.logger.debug(f"Processing {len(comments)} comments for issue {issue.identifier}")
            async for comment in self._process_issue_comments(comments, issue, issue_breadcrumbs):
                yield comment

            if issue.description and files:
                async for attachment in self._generate_attachment_entities_from_description(
                    issue.issue_id,
                    issue.identifier,
                    issue.description,
                    issue_breadcrumbs,
                    files,
                ):
                    yield attachment

        async for entity in self._paginated_query(
            query_template, process_issue, entity_type="issues"
        ):
            yield entity

    # ------------------------------------------------------------------
    # Error isolation
    # ------------------------------------------------------------------

    async def _generate_entities_safe(
        self,
        generator: AsyncGenerator,
        entity_type: str,
    ) -> AsyncGenerator:
        """Yield entities with error isolation per entity type.

        SourceAuthError propagates (abort sync — credentials dead).
        Other exceptions are logged and stop that entity type only.
        """
        try:
            self.logger.debug(f"Starting {entity_type} entity generation")
            async for entity in generator:
                yield entity
        except SourceAuthError:
            raise
        except SourceError as exc:
            self.logger.warning(f"Failed to generate {entity_type} entities: {exc}")
        except Exception as exc:
            self.logger.warning(f"Unexpected error generating {entity_type} entities: {exc}")

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
        """Generate all entities from Linear.

        On first sync (no cursor), all entities are fetched. On subsequent syncs,
        only entities updated since the last sync are fetched.
        """
        cursor_data = cursor.data if cursor else {}
        last_synced_at = cursor_data.get("last_synced_at") or None
        sync_start = datetime.now(tz=timezone.utc).isoformat()

        if last_synced_at:
            self.logger.info(f"Incremental sync from {last_synced_at}")
        else:
            self.logger.info("Full sync (first run)")

        async for entity in self._generate_entities_safe(
            self._generate_team_entities(since=last_synced_at), "team"
        ):
            yield entity

        async for entity in self._generate_entities_safe(
            self._generate_project_entities(since=last_synced_at), "project"
        ):
            yield entity

        async for entity in self._generate_entities_safe(
            self._generate_user_entities(since=last_synced_at), "user"
        ):
            yield entity

        async for entity in self._generate_entities_safe(
            self._generate_issue_entities(since=last_synced_at, files=files),
            "issue, comment, and attachment",
        ):
            yield entity

        if cursor:
            cursor.update(last_synced_at=sync_start)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def validate(self) -> None:
        """Verify Linear OAuth2 token by POSTing a minimal GraphQL query."""
        await self._post("query { viewer { id } }")
