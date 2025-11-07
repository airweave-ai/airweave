"""Linear source implementation for Airweave platform."""

import asyncio
import re
from typing import Any, AsyncGenerator, Dict, List, Optional, Union
from uuid import uuid4

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.shared_models import RateLimitLevel
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.linear import (
    LinearAttachmentEntity,
    LinearCommentEntity,
    LinearIssueEntity,
    LinearProjectEntity,
    LinearTeamEntity,
    LinearUserEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


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
    config_class="LinearConfig",
    labels=["Project Management"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class LinearSource(BaseSource):
    """Linear source connector integrates with the Linear GraphQL API to extract project data.

    Connects to your Linear workspace.

    It provides comprehensive access to teams, projects, issues, and
    users with advanced rate limiting and error handling for optimal performance.
    """

    # Rate limiting constants
    REQUESTS_PER_HOUR = 1200  # OAuth limit (vs 1500 for API keys)
    REQUESTS_PER_SECOND = REQUESTS_PER_HOUR / 3600
    RATE_LIMIT_PERIOD = 1.0
    MAX_RETRIES = 3

    def __init__(self):
        """Initialize the LinearSource with rate limiting state."""
        super().__init__()
        self._request_times = []
        self._lock = asyncio.Lock()
        self._stats = {
            "api_calls": 0,
            "rate_limit_waits": 0,
        }

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "LinearSource":
        """Create instance of the Linear source with authentication token and config.

        Args:
            access_token: OAuth access token for Linear API
            config: Optional configuration parameters, like exclude_path

        Returns:
            Configured LinearSource instance
        """
        instance = cls()
        instance.access_token = access_token

        # Store config values as instance attributes
        if config:
            instance.exclude_path = config.get("exclude_path", "")
        else:
            instance.exclude_path = ""

        return instance

    async def _wait_for_rate_limit(self):
        """Implement adaptive rate limiting for Linear API requests.

        Manages request timing to stay within API limits by dynamically
        adjusting wait times based on current usage patterns.
        """
        async with self._lock:
            current_time = asyncio.get_event_loop().time()

            # Track hourly request count
            hour_ago = current_time - 3600
            self._request_times = [t for t in self._request_times if t > hour_ago]
            hourly_count = len(self._request_times)

            # Adaptive throttling based on usage
            wait_time = 0
            if hourly_count >= 1000:  # >83% of quota - heavy throttling
                wait_time = 3.0
            elif hourly_count >= 900:  # 75-83% of quota - medium throttling
                wait_time = 2.0
            elif hourly_count >= 600:  # 50-75% of quota - light throttling
                wait_time = 1.0

            # Apply throttling if needed
            if wait_time > 0 and self._request_times:
                last_request = max(self._request_times)
                sleep_time = last_request + wait_time - current_time
                if sleep_time > 0:
                    self.logger.debug(
                        f"Rate limit throttling ({hourly_count}/1200 requests). "
                        f"Waiting {sleep_time:.2f}s"
                    )
                    self._stats["rate_limit_waits"] += 1
                    await asyncio.sleep(sleep_time)

            # Record this request
            self._request_times.append(current_time)

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _post_with_auth(self, client: httpx.AsyncClient, query: str) -> Dict:
        """Send authenticated GraphQL query to Linear API with rate limiting.

        Args:
            client: HTTP client to use for the request
            query: GraphQL query string

        Returns:
            JSON response from the API

        Raises:
            httpx.HTTPStatusError: On API errors
        """
        await self._wait_for_rate_limit()
        self._stats["api_calls"] += 1

        try:
            response = await client.post(
                "https://api.linear.app/graphql",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.access_token}",
                },
                json={"query": query},
            )
            response.raise_for_status()

            # Monitor rate limit status
            if "X-RateLimit-Requests-Remaining" in response.headers:
                remaining = int(response.headers.get("X-RateLimit-Requests-Remaining", "0"))
                self.logger.debug(f"Rate limit remaining: {remaining}")

            return response.json()
        except httpx.HTTPStatusError as e:
            # Log error details
            try:
                error_content = e.response.json()
                self.logger.error(f"GraphQL API error: {error_content}")
            except Exception:
                self.logger.error(f"HTTP Error content: {e.response.text}")
            raise

    async def _generate_attachment_entities_from_description(
        self,
        client: httpx.AsyncClient,
        issue_id: str,
        issue_identifier: str,
        issue_description: str,
        breadcrumbs: List[Breadcrumb],
    ) -> AsyncGenerator[Union[LinearAttachmentEntity, None], None]:
        """Extract and process attachments from markdown links in issue descriptions.

        Args:
            client: HTTP client to use for requests
            issue_id: Linear issue ID
            issue_identifier: Human-readable issue identifier
            issue_description: Markdown text of issue description
            breadcrumbs: List of parent breadcrumbs for navigation context

        Yields:
            Processed attachment entities from description links
        """
        if not issue_description:
            return

        # Regular expression to find markdown links [filename](url)
        markdown_link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        matches = re.findall(markdown_link_pattern, issue_description)

        self.logger.info(
            f"Found {len(matches)} potential attachments in description "
            f"for issue {issue_identifier}"
        )

        for file_name, url in matches:
            # Only process Linear upload URLs
            if "uploads.linear.app" in url:
                self.logger.info(
                    f"Processing attachment from description: {file_name} - URL: {url}"
                )

                # Generate a unique ID for this attachment
                attachment_id = str(uuid4())

                # Determine file type from URL/filename
                import mimetypes

                mime_type = mimetypes.guess_type(file_name)[0]
                if mime_type and "/" in mime_type:
                    file_type = mime_type.split("/")[0]
                else:
                    import os

                    ext = os.path.splitext(file_name)[1].lower().lstrip(".")
                    file_type = ext if ext else "file"

                # Create the attachment entity
                attachment_entity = LinearAttachmentEntity(
                    # Base fields
                    entity_id=attachment_id,
                    breadcrumbs=breadcrumbs.copy(),
                    name=file_name,
                    created_at=None,  # Description links don't have timestamps
                    updated_at=None,  # Description links don't have timestamps
                    # File fields
                    url=url,
                    size=0,  # Size unknown from description link
                    file_type=file_type,
                    mime_type=mime_type or "application/octet-stream",
                    local_path=None,  # Will be set after download
                    # API fields
                    issue_id=issue_id,
                    issue_identifier=issue_identifier,
                    title=file_name,
                    subtitle="Extracted from issue description",
                    source={"type": "description_link"},
                )

                try:
                    # Download file using file downloader
                    await self.file_downloader.download_from_url(
                        entity=attachment_entity,
                        http_client_factory=self.http_client,
                        access_token_provider=self.get_access_token,
                        logger=self.logger,
                    )

                    # Verify download succeeded
                    if not attachment_entity.local_path:
                        raise ValueError(
                            f"Download failed - no local path set for {attachment_entity.name}"
                        )

                    self.logger.debug(
                        f"Successfully downloaded attachment: {attachment_entity.name}"
                    )
                    yield attachment_entity

                except Exception as e:
                    self.logger.error(
                        f"Error downloading attachment {attachment_id} from description: {str(e)}"
                    )

    async def _process_issue_comments(
        self,
        comments: List[Dict],
        issue_id: str,
        issue_identifier: str,
        issue_breadcrumbs: List[Breadcrumb],
        team_id: Optional[str],
        team_name: Optional[str],
        project_id: Optional[str],
        project_name: Optional[str],
    ) -> AsyncGenerator[LinearCommentEntity, None]:
        """Process and yield comment entities for a given issue.

        Args:
            comments: List of comment data from Linear API
            issue_id: ID of the parent issue
            issue_identifier: Human-readable identifier of the parent issue
            issue_breadcrumbs: Breadcrumbs including the issue context
            team_id: ID of the team this issue belongs to
            team_name: Name of the team this issue belongs to
            project_id: ID of the project this issue belongs to, if any
            project_name: Name of the project this issue belongs to, if any

        Yields:
            LinearCommentEntity instances for each valid comment
        """
        for comment in comments:
            comment_id = comment.get("id")
            comment_body = comment.get("body", "")

            if not comment_body.strip():
                continue  # Skip empty comments

            # Extract user information
            user = comment.get("user", {})
            user_id = user.get("id") if user else None
            user_name = user.get("name") if user else None

            # Create comment URL
            comment_url = f"https://linear.app/issue/{issue_identifier}#comment-{comment_id}"

            # Create comment name from body preview
            comment_name = comment_body[:50] + "..." if len(comment_body) > 50 else comment_body

            # Create and yield LinearCommentEntity
            comment_entity = LinearCommentEntity(
                # Base fields
                entity_id=comment_id,
                breadcrumbs=issue_breadcrumbs.copy(),
                name=comment_name,
                created_at=comment.get("createdAt"),
                updated_at=comment.get("updatedAt"),
                # API fields
                issue_id=issue_id,
                issue_identifier=issue_identifier,
                body=comment_body,
                user_id=user_id,
                user_name=user_name,
                team_id=team_id,
                team_name=team_name,
                project_id=project_id,
                project_name=project_name,
                url=comment_url,
            )

            yield comment_entity

    async def _generate_issue_entities(  # noqa: C901
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[
        Union[LinearIssueEntity, LinearCommentEntity, LinearAttachmentEntity], None
    ]:
        """Generate entities for all issues, their comments, and their attachments in the workspace.

        Args:
            client: HTTP client to use for requests

        Yields:
            Issue entities, comment entities, and attachment entities
        """
        # Define query template with pagination placeholder
        # Filter to exclude archived issues using GraphQL filter
        query_template = """
        {{
          issues(filter: {{ archivedAt: {{ null: true }} }}, {pagination}) {{
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

        # Define processor function for issue nodes
        async def process_issue(issue):
            issue_identifier = issue.get("identifier")

            # Skip issues matching exclude_path
            if self.exclude_path and issue_identifier and self.exclude_path in issue_identifier:
                self.logger.info(f"Skipping excluded issue: {issue_identifier}")
                return

            # Defensive check: skip archived issues (should already be filtered by GraphQL query)
            if issue.get("archivedAt"):
                self.logger.warning(
                    f"Archived issue {issue_identifier} passed GraphQL filter - skipping"
                )
                return

            issue_title = issue.get("title")
            issue_description = issue.get("description", "")

            self.logger.info(f"Processing issue: {issue_identifier} - '{issue_title}'")

            # Build breadcrumbs list
            breadcrumbs = []

            # Add team breadcrumb if available
            team_id = None
            team_name = None
            if issue.get("team"):
                team_id = issue["team"].get("id")
                team_name = issue["team"].get("name")
                team_breadcrumb = Breadcrumb(entity_id=team_id)
                breadcrumbs.append(team_breadcrumb)

            # Add project breadcrumb if available
            project_id = None
            project_name = None
            if issue.get("project"):
                project_id = issue["project"].get("id")
                project_name = issue["project"].get("name")
                project_breadcrumb = Breadcrumb(entity_id=project_id)
                breadcrumbs.append(project_breadcrumb)

            # Create issue URL
            issue_url = f"https://linear.app/issue/{issue.get('identifier')}"
            issue_id = issue.get("id")

            # Create and yield LinearIssueEntity
            issue_entity = LinearIssueEntity(
                # Base fields
                entity_id=issue_id,
                breadcrumbs=breadcrumbs,
                name=issue.get("title", ""),
                created_at=issue.get("createdAt"),
                updated_at=issue.get("updatedAt"),
                # API fields
                identifier=issue_identifier,
                title=issue.get("title", ""),
                description=issue_description,
                priority=issue.get("priority"),
                state=issue.get("state", {}).get("name"),
                completed_at=issue.get("completedAt"),
                due_date=issue.get("dueDate"),
                team_id=team_id,
                team_name=team_name,
                project_id=project_id,
                project_name=project_name,
                assignee=issue.get("assignee", {}).get("name") if issue.get("assignee") else None,
                url=issue_url,
            )

            # First yield the issue entity
            yield issue_entity

            # Create issue breadcrumb for comments and attachments
            issue_breadcrumb = Breadcrumb(entity_id=issue_entity.entity_id)

            # Combine breadcrumbs with issue breadcrumb
            issue_breadcrumbs = breadcrumbs + [issue_breadcrumb]

            # Process and yield comment entities
            comments = issue.get("comments", {}).get("nodes", [])
            self.logger.info(f"Processing {len(comments)} comments for issue {issue_identifier}")

            async for comment_entity in self._process_issue_comments(
                comments,
                issue_id,
                issue_identifier,
                issue_breadcrumbs,
                team_id,
                team_name,
                project_id,
                project_name,
            ):
                yield comment_entity

            # Extract attachments from description
            if issue_description:
                async for attachment in self._generate_attachment_entities_from_description(
                    client, issue_id, issue_identifier, issue_description, issue_breadcrumbs
                ):
                    if attachment:
                        yield attachment

        # Use the paginated query helper
        async for entity in self._paginated_query(
            client, query_template, process_issue, entity_type="issues"
        ):
            yield entity

    async def _generate_project_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[LinearProjectEntity, None]:
        """Generate entities for all projects in the workspace.

        Args:
            client: HTTP client to use for requests

        Yields:
            Project entities
        """
        # Define query template with pagination placeholder
        query_template = """
        {{
          projects({pagination}) {{
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

        # Define processor function for project nodes
        async def process_project(project):
            project_id = project.get("id")
            project_name = project.get("name")

            self.logger.info(f"Processing project: {project_name}")

            # Extract team data
            team_ids = []
            team_names = []
            teams = project.get("teams", {}).get("nodes", [])

            for team in teams:
                team_ids.append(team.get("id"))
                team_names.append(team.get("name"))

            # Build breadcrumbs list
            breadcrumbs = []

            # Add team breadcrumbs if available
            for team_id in team_ids:
                team_breadcrumb = Breadcrumb(entity_id=team_id)
                breadcrumbs.append(team_breadcrumb)

            # Create project URL
            project_url = f"https://linear.app/project/{project.get('slugId')}"

            # Create and yield LinearProjectEntity
            yield LinearProjectEntity(
                # Base fields
                entity_id=project_id,
                breadcrumbs=breadcrumbs,
                name=project.get("name", ""),
                created_at=project.get("createdAt"),
                updated_at=project.get("updatedAt"),
                # API fields
                slug_id=project.get("slugId"),
                description=project.get("description"),
                priority=project.get("priority"),
                state=project.get("state"),
                completed_at=project.get("completedAt"),
                started_at=project.get("startedAt"),
                target_date=project.get("targetDate"),
                start_date=project.get("startDate"),
                team_ids=team_ids if team_ids else None,
                team_names=team_names if team_names else None,
                progress=project.get("progress"),
                lead=project.get("lead", {}).get("name") if project.get("lead") else None,
                url=project_url,
            )

        # Use the paginated query helper
        try:
            async for entity in self._paginated_query(
                client, query_template, process_project, entity_type="projects"
            ):
                yield entity
        except Exception as e:
            self.logger.error(f"Error in project entity generation: {str(e)}")

    async def _generate_team_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[LinearTeamEntity, None]:
        """Generate entities for all teams in the workspace.

        Args:
            client: HTTP client to use for requests

        Yields:
            Team entities
        """
        # Define the GraphQL query template with {pagination} placeholder
        query_template = """
        {{
          teams({pagination}) {{
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

        # Define a processor function for team nodes
        async def process_team(team):
            team_id = team.get("id")
            team_name = team.get("name")
            team_key = team.get("key")
            parent = team.get("parent")
            team_parent_id = parent.get("id", "") if parent else ""
            team_parent_name = parent.get("name", "") if parent else ""

            self.logger.info(f"Processing team: {team_name} ({team_key})")

            # Create team URL
            team_url = f"https://linear.app/team/{team.get('key')}"

            # Build breadcrumbs list (self-reference for consistency)
            breadcrumbs = [Breadcrumb(entity_id=team_id)]

            # Create and yield LinearTeamEntity
            yield LinearTeamEntity(
                # Base fields
                entity_id=team_id,
                breadcrumbs=breadcrumbs,
                name=team_name,
                created_at=team.get("createdAt"),
                updated_at=team.get("updatedAt"),
                # API fields
                key=team_key,
                description=team.get("description", ""),
                color=team.get("color", ""),
                icon=team.get("icon", ""),
                private=team.get("private", False),
                timezone=team.get("timezone", ""),
                parent_id=team_parent_id,
                parent_name=team_parent_name,
                issue_count=team.get("issueCount", 0),
                url=team_url,
            )

        try:
            # Use the paginated query helper with our team processor
            async for entity in self._paginated_query(
                client, query_template, process_team, entity_type="teams"
            ):
                yield entity
        except Exception as e:
            self.logger.error(f"Error in team entity generation: {str(e)}")

    async def _generate_user_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[LinearUserEntity, None]:
        """Generate entities for all users in the workspace.

        Args:
            client: HTTP client to use for requests

        Yields:
            User entities
        """
        # Define query template with pagination placeholder
        query_template = """
        {{
          users({pagination}) {{
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

        # Define processor function for user nodes
        async def process_user(user):
            user_id = user.get("id")
            user_name = user.get("name")
            display_name = user.get("displayName")

            self.logger.info(f"Processing user: {user_name} ({display_name})")

            # Extract team data
            team_ids = []
            team_names = []
            teams = user.get("teams", {}).get("nodes", [])

            for team in teams:
                team_ids.append(team.get("id"))
                team_names.append(team.get("name"))

            # Build breadcrumbs list - add team breadcrumbs
            breadcrumbs = []
            for team_id in team_ids:
                team_breadcrumb = Breadcrumb(entity_id=team_id)
                breadcrumbs.append(team_breadcrumb)

            # Create user URL
            user_url = f"https://linear.app/u/{user.get('id')}"

            # Create and yield LinearUserEntity
            yield LinearUserEntity(
                # Base fields
                entity_id=user_id,
                breadcrumbs=breadcrumbs,
                name=user_name,
                created_at=user.get("createdAt"),
                updated_at=user.get("updatedAt"),
                # API fields
                display_name=display_name,
                email=user.get("email"),
                avatar_url=user.get("avatarUrl"),
                description=user.get("description"),
                timezone=user.get("timezone"),
                active=user.get("active"),
                admin=user.get("admin"),
                guest=user.get("guest"),
                last_seen=user.get("lastSeen"),
                status_emoji=user.get("statusEmoji"),
                status_label=user.get("statusLabel"),
                status_until_at=user.get("statusUntilAt"),
                created_issue_count=user.get("createdIssueCount"),
                team_ids=team_ids if team_ids else None,
                team_names=team_names if team_names else None,
                url=user_url,
            )

        # Use the paginated query helper
        try:
            async for entity in self._paginated_query(
                client, query_template, process_user, entity_type="users"
            ):
                yield entity
        except Exception as e:
            self.logger.error(f"Error in user entity generation: {str(e)}")

    async def _paginated_query(
        self,
        client: httpx.AsyncClient,
        query_template: str,
        process_node_func,
        page_size: int = 50,
        entity_type: str = "items",
    ) -> AsyncGenerator:
        """Execute a paginated GraphQL query against the Linear API.

        Args:
            client: HTTP client to use for requests
            query_template: GraphQL query template with {pagination} placeholder
            process_node_func: Function to process each node from the results
            page_size: Number of items to request per page
            entity_type: Type of entity being queried (for logging)

        Yields:
            Processed entities from the query results
        """
        has_next_page = True
        cursor = None
        items_processed = 0

        while has_next_page:
            # Build pagination parameters
            pagination = f"first: {page_size}"
            if cursor:
                pagination += f', after: "{cursor}"'

            # Insert pagination into query template
            query = query_template.format(pagination=pagination)

            try:
                # Execute the query
                response = await self._post_with_auth(client, query)

                # Extract data - assumes response structure with nodes and pageInfo
                data = response.get("data", {})
                # The first key in data should be the entity collection (issues, teams, etc.)
                collection_key = next(iter(data.keys()), None)

                if not collection_key:
                    self.logger.error(f"Unexpected response structure: {response}")
                    break

                collection_data = data[collection_key]
                nodes = collection_data.get("nodes", [])

                # Log the batch
                batch_count = len(nodes)
                items_processed += batch_count
                self.logger.info(
                    f"Processing batch of {batch_count} {entity_type} (total: {items_processed})"
                )

                # Process each node
                for node in nodes:
                    # Use the provided function to process each node
                    async for entity in process_node_func(node):
                        if entity:  # Only yield non-None results
                            yield entity

                # Update pagination info for next iteration
                page_info = collection_data.get("pageInfo", {})
                has_next_page = page_info.get("hasNextPage", False)
                cursor = page_info.get("endCursor")

                # If no more results or empty response, exit
                if not nodes or not has_next_page:
                    break

            except Exception as e:
                self.logger.error(f"Error processing {entity_type} batch: {str(e)}")
                break

    async def generate_entities(
        self,
    ) -> AsyncGenerator[
        Union[
            LinearTeamEntity,
            LinearProjectEntity,
            LinearUserEntity,
            LinearIssueEntity,
            LinearCommentEntity,
            LinearAttachmentEntity,
        ],
        None,
    ]:
        """Main entry point to generate all entities from Linear.

        This method coordinates the extraction of all entity types from Linear,
        handling each entity type separately with proper error isolation.

        Yields:
            All Linear entities (teams, projects, users, issues, comments, attachments)
        """
        async with self.http_client() as client:
            # Generate team entities
            try:
                self.logger.info("Starting team entity generation")
                async for team_entity in self._generate_team_entities(client):
                    yield team_entity
            except Exception as e:
                self.logger.error(f"Failed to generate team entities: {str(e)}")
                self.logger.info("Continuing with other entity types")

            # Generate project entities
            try:
                self.logger.info("Starting project entity generation")
                async for project_entity in self._generate_project_entities(client):
                    yield project_entity
            except Exception as e:
                self.logger.error(f"Failed to generate project entities: {str(e)}")

            # Generate user entities
            try:
                self.logger.info("Starting user entity generation")
                async for user_entity in self._generate_user_entities(client):
                    yield user_entity
            except Exception as e:
                self.logger.error(f"Failed to generate user entities: {str(e)}")

            # Generate issue, comment, and attachment entities
            try:
                self.logger.info("Starting issue, comment, and attachment entity generation")
                async for entity in self._generate_issue_entities(client):
                    yield entity
            except Exception as e:
                self.logger.error(f"Failed to generate issue/attachment entities: {str(e)}")

    async def validate(self) -> bool:
        """Verify Linear OAuth2 token by POSTing a minimal GraphQL query to /graphql."""
        try:
            token = await self.get_access_token()
            if not token:
                self.logger.error("Linear validation failed: no access token available.")
                return False

            query = {"query": "query { viewer { id } }"}

            async with self.http_client(timeout=10.0) as client:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
                resp = await client.post(
                    "https://api.linear.app/graphql", headers=headers, json=query
                )

                # Handle 401 by attempting a one-time refresh
                if resp.status_code == 401:
                    self.logger.info("Linear validate: 401 Unauthorized; attempting token refresh.")
                    new_token = await self.refresh_on_unauthorized()
                    if new_token:
                        headers["Authorization"] = f"Bearer {new_token}"
                        resp = await client.post(
                            "https://api.linear.app/graphql", headers=headers, json=query
                        )

                if not (200 <= resp.status_code < 300):
                    self.logger.warning(
                        f"Linear validate failed: HTTP {resp.status_code} - {resp.text[:200]}"
                    )
                    return False

                body = resp.json()
                if body.get("errors"):
                    self.logger.warning(f"Linear validate GraphQL errors: {body['errors']}")
                    return False

                viewer = (body.get("data") or {}).get("viewer") or {}
                return bool(viewer.get("id"))

        except httpx.RequestError as e:
            self.logger.error(f"Linear validation request error: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during Linear validation: {e}")
            return False
