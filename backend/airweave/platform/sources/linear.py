"""Linear source implementation for Airweave platform."""

import asyncio
import re
from typing import AsyncGenerator, Dict, List, Union
from uuid import uuid4

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import Breadcrumb
from airweave.platform.entities.linear import (
    LinearAttachmentEntity,
    LinearIssueEntity,
    LinearProjectEntity,
    LinearTeamEntity,
    LinearUserEntity,
)
from airweave.platform.sources._base import BaseSource


@source("Linear", "linear", AuthType.oauth2, labels=["Project Management"])
class LinearSource(BaseSource):
    """Linear source implementation for syncing data from Linear into Airweave.

    This source connects to Linear's GraphQL API and extracts teams, projects,
    users, issues, and attachments with proper rate limiting and error handling.
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
    async def create(cls, access_token: str) -> "LinearSource":
        """Create instance of the Linear source with authentication token.

        Args:
            access_token: OAuth access token for Linear API

        Returns:
            Configured LinearSource instance
        """
        instance = cls()
        instance.access_token = access_token
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
                    logger.debug(
                        f"Rate limit throttling ({hourly_count}/1200 requests). "
                        f"Waiting {sleep_time:.2f}s"
                    )
                    self._stats["rate_limit_waits"] += 1
                    await asyncio.sleep(sleep_time)

            # Record this request
            self._request_times.append(current_time)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
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
                logger.debug(f"Rate limit remaining: {remaining}")

            return response.json()
        except httpx.HTTPStatusError as e:
            # Log error details
            try:
                error_content = e.response.json()
                logger.error(f"GraphQL API error: {error_content}")
            except Exception:
                logger.error(f"HTTP Error content: {e.response.text}")
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

        logger.info(
            f"Found {len(matches)} potential attachments in description "
            f"for issue {issue_identifier}"
        )

        for file_name, url in matches:
            # Only process Linear upload URLs
            if "uploads.linear.app" in url:
                logger.info(f"Processing attachment from description: {file_name} - URL: {url}")

                # Generate a unique ID for this attachment
                attachment_id = str(uuid4())

                # Create the attachment entity
                attachment_entity = LinearAttachmentEntity(
                    entity_id=attachment_id,
                    file_id=attachment_id,
                    breadcrumbs=breadcrumbs.copy(),
                    # FileEntity required fields
                    name=file_name,
                    download_url=url,
                    # LinearAttachmentEntity specific fields
                    issue_id=issue_id,
                    issue_identifier=issue_identifier,
                    title=file_name,
                    subtitle="Extracted from issue description",
                    source={"type": "description_link"},
                    created_at=None,
                    updated_at=None,
                    metadata={"extracted_from": "description"},
                )

                try:
                    processed_entity = await self.process_file_entity(
                        file_entity=attachment_entity,
                        headers={"Authorization": f"Bearer {self.access_token}"},
                    )
                    yield processed_entity
                except Exception as e:
                    logger.error(
                        f"Error processing attachment {attachment_id} from description: {str(e)}"
                    )

    async def _generate_issue_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[Union[LinearIssueEntity, LinearAttachmentEntity], None]:
        """Generate entities for all issues and their attachments in the workspace.

        Args:
            client: HTTP client to use for requests

        Yields:
            Issue entities and attachment entities
        """
        # Define query template with pagination placeholder
        query_template = """
        {{
          issues({pagination}) {{
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
            issue_title = issue.get("title")
            issue_description = issue.get("description", "")

            logger.info(f"Processing issue: {issue_identifier} - '{issue_title}'")

            # Build breadcrumbs list
            breadcrumbs = []

            # Add team breadcrumb if available
            team_id = None
            team_name = None
            if issue.get("team"):
                team_id = issue["team"].get("id")
                team_name = issue["team"].get("name")
                team_breadcrumb = Breadcrumb(entity_id=team_id, name=team_name, type="team")
                breadcrumbs.append(team_breadcrumb)

            # Add project breadcrumb if available
            project_id = None
            project_name = None
            if issue.get("project"):
                project_id = issue["project"].get("id")
                project_name = issue["project"].get("name")
                project_breadcrumb = Breadcrumb(
                    entity_id=project_id, name=project_name, type="project"
                )
                breadcrumbs.append(project_breadcrumb)

            # Create issue URL
            issue_url = f"https://linear.app/issue/{issue.get('identifier')}"
            issue_id = issue.get("id")

            # Create and yield LinearIssueEntity
            issue_entity = LinearIssueEntity(
                entity_id=issue_id,
                title=issue.get("title", ""),
                breadcrumbs=breadcrumbs,
                url=issue_url,
                # LinearIssueEntity specific fields
                identifier=issue_identifier,
                description=issue_description,
                priority=issue.get("priority"),
                state=issue.get("state", {}).get("name"),
                team_id=team_id,
                team_name=team_name,
                project_id=project_id,
                project_name=project_name,
                assignee=issue.get("assignee", {}).get("name") if issue.get("assignee") else None,
                created_at=issue.get("createdAt"),
                updated_at=issue.get("updatedAt"),
                completed_at=issue.get("completedAt"),
                due_date=issue.get("dueDate"),
            )

            # First yield the issue entity
            yield issue_entity

            # Create issue breadcrumb for attachments
            issue_breadcrumb = Breadcrumb(
                entity_id=issue_entity.entity_id, name=issue_entity.title, type="issue"
            )

            # Combine breadcrumbs with issue breadcrumb
            issue_breadcrumbs = breadcrumbs + [issue_breadcrumb]

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

            logger.info(f"Processing project: {project_name}")

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
            for i, team_id in enumerate(team_ids):
                team_name = team_names[i]
                team_breadcrumb = Breadcrumb(entity_id=team_id, name=team_name, type="team")
                breadcrumbs.append(team_breadcrumb)

            # Create project URL
            project_url = f"https://linear.app/project/{project.get('slugId')}"

            # Create and yield LinearProjectEntity
            yield LinearProjectEntity(
                entity_id=project_id,
                name=project.get("name", ""),
                breadcrumbs=breadcrumbs,
                url=project_url,
                # LinearProjectEntity specific fields
                slug_id=project.get("slugId"),
                description=project.get("description"),
                priority=project.get("priority"),
                state=project.get("state"),
                team_ids=team_ids if team_ids else None,
                team_names=team_names if team_names else None,
                created_at=project.get("createdAt"),
                updated_at=project.get("updatedAt"),
                completed_at=project.get("completedAt"),
                started_at=project.get("startedAt"),
                target_date=project.get("targetDate"),
                start_date=project.get("startDate"),
                progress=project.get("progress"),
                lead=project.get("lead", {}).get("name") if project.get("lead") else None,
            )

        # Use the paginated query helper
        try:
            async for entity in self._paginated_query(
                client, query_template, process_project, entity_type="projects"
            ):
                yield entity
        except Exception as e:
            logger.error(f"Error in project entity generation: {str(e)}")

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

            logger.info(f"Processing team: {team_name} ({team_key})")

            # Create team URL
            team_url = f"https://linear.app/team/{team.get('key')}"

            # Build breadcrumbs list
            breadcrumbs = [Breadcrumb(entity_id=team_id, name=team_name, type="team")]

            # Create and yield LinearTeamEntity
            yield LinearTeamEntity(
                entity_id=team_id,
                name=team_name,
                breadcrumbs=breadcrumbs,
                url=team_url,
                # LinearTeamEntity specific fields
                key=team_key,
                description=team.get("description", ""),
                color=team.get("color", ""),
                icon=team.get("icon", ""),
                private=team.get("private", False),
                timezone=team.get("timezone", ""),
                created_at=team.get("createdAt", ""),
                updated_at=team.get("updatedAt", ""),
                parent_id=team_parent_id,
                parent_name=team_parent_name,
                issue_count=team.get("issueCount", 0),
            )

        try:
            # Use the paginated query helper with our team processor
            async for entity in self._paginated_query(
                client, query_template, process_team, entity_type="teams"
            ):
                yield entity
        except Exception as e:
            logger.error(f"Error in team entity generation: {str(e)}")

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

            logger.info(f"Processing user: {user_name} ({display_name})")

            # Extract team data
            team_ids = []
            team_names = []
            teams = user.get("teams", {}).get("nodes", [])

            for team in teams:
                team_ids.append(team.get("id"))
                team_names.append(team.get("name"))

            # Build breadcrumbs list - add team breadcrumbs
            breadcrumbs = []
            for i, team_id in enumerate(team_ids):
                team_name = team_names[i]
                team_breadcrumb = Breadcrumb(entity_id=team_id, name=team_name, type="team")
                breadcrumbs.append(team_breadcrumb)

            # Create user URL
            user_url = f"https://linear.app/u/{user.get('id')}"

            # Create and yield LinearUserEntity
            yield LinearUserEntity(
                entity_id=user_id,
                name=user_name,
                breadcrumbs=breadcrumbs,
                url=user_url,
                # LinearUserEntity specific fields
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
                created_at=user.get("createdAt"),
                updated_at=user.get("updatedAt"),
            )

        # Use the paginated query helper
        try:
            async for entity in self._paginated_query(
                client, query_template, process_user, entity_type="users"
            ):
                yield entity
        except Exception as e:
            logger.error(f"Error in user entity generation: {str(e)}")

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
                    logger.error(f"Unexpected response structure: {response}")
                    break

                collection_data = data[collection_key]
                nodes = collection_data.get("nodes", [])

                # Log the batch
                batch_count = len(nodes)
                items_processed += batch_count
                logger.info(
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
                logger.error(f"Error processing {entity_type} batch: {str(e)}")
                break

    async def generate_entities(
        self,
    ) -> AsyncGenerator[
        Union[
            LinearTeamEntity,
            LinearProjectEntity,
            LinearUserEntity,
            LinearIssueEntity,
            LinearAttachmentEntity,
        ],
        None,
    ]:
        """Main entry point to generate all entities from Linear.

        This method coordinates the extraction of all entity types from Linear,
        handling each entity type separately with proper error isolation.

        Yields:
            All Linear entities (teams, projects, users, issues, attachments)
        """
        async with httpx.AsyncClient() as client:
            # Generate team entities
            try:
                logger.info("Starting team entity generation")
                async for team_entity in self._generate_team_entities(client):
                    yield team_entity
            except Exception as e:
                logger.error(f"Failed to generate team entities: {str(e)}")
                logger.info("Continuing with other entity types")

            # Generate project entities
            try:
                logger.info("Starting project entity generation")
                async for project_entity in self._generate_project_entities(client):
                    yield project_entity
            except Exception as e:
                logger.error(f"Failed to generate project entities: {str(e)}")

            # Generate user entities
            try:
                logger.info("Starting user entity generation")
                async for user_entity in self._generate_user_entities(client):
                    yield user_entity
            except Exception as e:
                logger.error(f"Failed to generate user entities: {str(e)}")

            # Generate issue and attachment entities
            try:
                logger.info("Starting issue and attachment entity generation")
                async for entity in self._generate_issue_entities(client):
                    yield entity
            except Exception as e:
                logger.error(f"Failed to generate issue/attachment entities: {str(e)}")
