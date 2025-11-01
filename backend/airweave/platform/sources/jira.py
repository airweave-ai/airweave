"""Jira source implementation.

Simplified connector that retrieves Projects and Issues from a Jira Cloud instance.

References:
    https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/
    https://developer.atlassian.com/cloud/jira/platform/rest/v3/overview
"""

from typing import Any, AsyncGenerator, Dict, Optional

import httpx
import tenacity
from tenacity import stop_after_attempt, wait_exponential

from airweave.core.exceptions import TokenRefreshError
from airweave.core.logging import logger
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.jira import (
    JiraIssueEntity,
    JiraProjectEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType


@source(
    name="Jira",
    short_name="jira",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=None,
    config_class="JiraConfig",
    labels=["Project Management", "Issue Tracking"],
    supports_continuous=False,
)
class JiraSource(BaseSource):
    """Jira source connector integrates with the Jira REST API to extract project management data.

    Connects to your Jira Cloud instance.

    It provides comprehensive access to projects, issues, and their
    relationships for agile development and issue tracking workflows.
    """

    async def _get_accessible_resources(self) -> list[dict]:
        """Get the list of accessible Atlassian resources for this token.

        Uses token manager to ensure fresh access token.
        """
        self.logger.info("Retrieving accessible Atlassian resources")

        # Get fresh access token (will refresh if needed)
        access_token = await self.get_access_token()

        if not access_token:
            self.logger.error("Cannot get accessible resources: access token is None")
            return []

        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            try:
                self.logger.debug(
                    "Making request to https://api.atlassian.com/oauth/token/accessible-resources"
                )
                response = await client.get(
                    "https://api.atlassian.com/oauth/token/accessible-resources", headers=headers
                )
                response.raise_for_status()
                resources = response.json()
                self.logger.info(f"Found {len(resources)} accessible Atlassian resources")
                self.logger.debug(f"Resources: {resources}")
                return resources
            except httpx.HTTPStatusError as e:
                self.logger.error(
                    f"HTTP error getting accessible resources: {e.response.status_code} - {e.response.text}"
                )
                return []
            except Exception as e:
                self.logger.error(f"Error getting accessible resources: {str(e)}", exc_info=True)
                return []

    @classmethod
    async def create(
        cls, access_token: str, config: Optional[Dict[str, Any]] = None
    ) -> "JiraSource":
        """Create a new Jira source instance."""
        instance = cls()
        instance.access_token = access_token
        return instance

    @tenacity.retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
    )
    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Any:
        """Make an authenticated GET request to the Jira REST API."""
        self.logger.debug(f"Making authenticated request to {url}")
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check",  # Required for CSRF protection
        }

        self.logger.debug(f"Request headers: {headers}")
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            self.logger.debug(f"Response status: {response.status_code}")
            self.logger.debug(f"Response size: {len(response.content)} bytes")
            return data
        except httpx.HTTPStatusError as e:
            # Handle 401 Unauthorized - try refreshing token
            if e.response.status_code == 401 and self._token_manager:
                self.logger.warning(
                    "🔐 Received 401 Unauthorized from Jira - attempting token refresh"
                )
                try:
                    refreshed = await self._token_manager.refresh_on_unauthorized()

                    if refreshed:
                        # Retry with new token (the retry decorator will handle this)
                        self.logger.info("✅ Token refreshed successfully, retrying request")
                        raise  # Let tenacity retry with the refreshed token
                except TokenRefreshError as refresh_error:
                    # Token refresh failed - provide clear error message
                    self.logger.error(
                        f"❌ Token refresh failed: {str(refresh_error)}. "
                        f"User may need to reconnect their Jira account."
                    )
                    # Re-raise with clearer context
                    raise TokenRefreshError(
                        f"Failed to refresh Jira access token: {str(refresh_error)}. "
                        f"Please reconnect your Jira account."
                    ) from refresh_error

            # Log the error details
            self.logger.error(f"Request failed: {str(e)}")
            self.logger.error(f"Response status: {e.response.status_code}")
            self.logger.error(f"Response body: {e.response.text}")
            raise
        except Exception as e:
            self.logger.error(f"Request failed: {str(e)}")
            raise

    @tenacity.retry(
        stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10), reraise=True
    )
    async def _post_with_auth(
        self, client: httpx.AsyncClient, url: str, json_data: Dict[str, Any]
    ) -> Any:
        """Make an authenticated POST request to the Jira REST API."""
        access_token = await self.get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Atlassian-Token": "no-check",
        }

        try:
            response = await client.post(url, headers=headers, json=json_data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401 and self._token_manager:
                self.logger.info("Received 401 error, attempting to refresh token")
                refreshed = await self._token_manager.refresh_on_unauthorized()
                if refreshed:
                    self.logger.info("Token refreshed, retrying request")
                    raise
            self.logger.error(f"Request failed: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Request failed: {str(e)}")
            raise

    # Entity Creation Functions
    def _create_project_entity(self, project_data):
        """Transform raw project data into a JiraProjectEntity."""
        self.logger.debug(
            f"Creating project entity for: {project_data.get('key')} - {project_data.get('name')}"
        )
        # Use a composite ID format that includes the entity type for uniqueness
        entity_id = f"project-{project_data['id']}"

        return JiraProjectEntity(
            # Base fields
            entity_id=entity_id,
            breadcrumbs=[],
            name=project_data.get("name") or project_data["key"],
            created_at=None,  # Projects don't have creation timestamp in API
            updated_at=None,  # Projects don't have update timestamp in API
            # API fields
            project_key=project_data["key"],
            description=project_data.get("description"),
        )

    def _extract_text_from_adf(self, adf_data):
        """Extract plain text from Atlassian Document Format (ADF)."""
        text_parts = []

        def extract_recursive(node):
            if isinstance(node, dict):
                # Extract text directly from text nodes
                if node.get("type") == "text":
                    text_parts.append(node.get("text", ""))

                # Extract text from emoji nodes
                elif node.get("type") == "emoji" and "text" in node.get("attrs", {}):
                    text_parts.append(node.get("attrs", {}).get("text", ""))

                # Process child content recursively
                if "content" in node and isinstance(node["content"], list):
                    for child in node["content"]:
                        extract_recursive(child)

            elif isinstance(node, list):
                for item in node:
                    extract_recursive(item)

        # Start recursion from the root
        extract_recursive(adf_data)
        return " ".join(text_parts)

    def _create_issue_entity(self, issue_data, project):
        """Transform raw issue data into a JiraIssueEntity."""
        fields = issue_data.get("fields", {})
        issue_key = issue_data.get("key", "unknown")

        # Safely get issue type name
        issue_type = fields.get("issuetype", {})
        issue_type_name = issue_type.get("name") if issue_type else None

        # Safely get status name
        status = fields.get("status", {})
        status_name = status.get("name") if status else None

        # Handle Atlassian Document Format (ADF) for description
        description = fields.get("description")
        description_text = None
        if description:
            if isinstance(description, dict):
                # Extract plain text from the ADF structure
                self.logger.debug(f"Converting ADF description to text for issue {issue_key}")
                description_text = self._extract_text_from_adf(description)
            else:
                description_text = description

        self.logger.debug(
            f"Creating issue entity: {issue_key} - Type: {issue_type_name}, Status: {status_name}"
        )

        # Use a composite ID format that includes the entity type for uniqueness
        entity_id = f"issue-{issue_data['id']}"

        return JiraIssueEntity(
            # Base fields
            entity_id=entity_id,
            breadcrumbs=[Breadcrumb(entity_id=project.entity_id)],
            name=fields.get("summary") or issue_key,
            created_at=fields.get("created"),
            updated_at=fields.get("updated"),
            # API fields
            issue_key=issue_key,
            summary=fields.get("summary"),
            description=description_text,
            status=status_name,
            issue_type=issue_type_name,
        )

    async def _generate_project_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[JiraProjectEntity, None]:
        """Generate JiraProjectEntity objects."""
        self.logger.info("Starting project entity generation")
        search_api_path = "/rest/api/3/project/search"
        max_results = 50
        start_at = 0
        page = 1
        total_projects = 0

        while True:
            # Construct URL with pagination parameters
            project_search_url = (
                f"{self.base_url}{search_api_path}?startAt={start_at}&maxResults={max_results}"
            )
            self.logger.info(f"Fetching project page {page} from {project_search_url}")

            # Get project data
            data = await self._get_with_auth(client, project_search_url)
            projects = data.get("values", [])
            self.logger.info(f"Retrieved {len(projects)} projects on page {page}")

            # Process each project
            for project in projects:
                total_projects += 1
                project_entity = self._create_project_entity(project)
                yield project_entity

            # Handle pagination
            if data.get("isLast", True):
                self.logger.info(
                    f"Reached last page of projects, total projects found: {total_projects}"
                )
                break

            start_at = data.get("startAt", 0) + max_results
            page += 1
            self.logger.debug(f"Moving to next page, startAt={start_at}")

    async def _generate_issue_entities(
        self, client: httpx.AsyncClient, project: JiraProjectEntity
    ) -> AsyncGenerator[JiraIssueEntity, None]:
        """Generate JiraIssueEntity for each issue in the given project using JQL search."""
        project_key = project.project_key
        self.logger.info(
            f"Starting issue entity generation for project: {project_key} ({project.name})"
        )

        # Setup for pagination - using new /rest/api/3/search/jql endpoint
        search_url = f"{self.base_url}/rest/api/3/search/jql"
        max_results = 50
        next_page_token = None

        while True:
            # Construct JSON body for POST request with JQL query
            search_body = {
                "jql": f"project = {project_key}",
                "maxResults": max_results,
                "fields": ["summary", "description", "status", "issuetype", "created", "updated"],
            }

            # Add nextPageToken if we have one (for pagination)
            if next_page_token:
                search_body["nextPageToken"] = next_page_token

            self.logger.info(f"Fetching issues for project {project_key}")
            data = await self._post_with_auth(client, search_url, search_body)

            # Log response overview
            total = data.get("total", 0)
            issues = data.get("issues", [])
            self.logger.info(f"Found {len(issues)} issues (total available: {total})")

            # Process each issue
            for issue_data in issues:
                issue_entity = self._create_issue_entity(issue_data, project)
                yield issue_entity

            # Check if we've processed all issues using isLast flag
            is_last = data.get("isLast", True)
            next_page_token = data.get("nextPageToken")

            if is_last or not next_page_token:
                self.logger.info(f"Completed fetching all issues for project {project_key}")
                break

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Jira."""
        self.logger.info("Starting Jira entity generation process")

        resources = await self._get_accessible_resources()
        if not resources:
            raise ValueError("No accessible resources found")
        cloud_id = resources[0]["id"]

        self.base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"
        self.logger.debug(f"Base URL set to: {self.base_url}")
        async with httpx.AsyncClient() as client:
            project_count = 0
            issue_count = 0
            # Track already processed entity IDs with their type to avoid duplicates
            processed_entities = set()  # Will store tuples of (entity_id, key)

            # 1) Generate (and yield) all Projects
            async for project_entity in self._generate_project_entities(client):
                project_count += 1
                # Create a unique identifier for this project
                project_identifier = (project_entity.entity_id, project_entity.project_key)

                # Skip if already processed
                if project_identifier in processed_entities:
                    self.logger.warning(
                        f"Skipping duplicate project: {project_entity.project_key} "
                        f"(ID: {project_entity.entity_id})"
                    )
                    continue

                processed_entities.add(project_identifier)
                self.logger.info(
                    f"Yielding project entity: {project_entity.project_key} ({project_entity.name})"
                )
                yield project_entity

                # 2) Generate (and yield) all Issues for each Project
                project_issue_count = 0
                async for issue_entity in self._generate_issue_entities(client, project_entity):
                    # Create a unique identifier for this issue
                    issue_identifier = (issue_entity.entity_id, issue_entity.issue_key)

                    # Skip if already processed
                    if issue_identifier in processed_entities:
                        self.logger.warning(
                            f"Skipping duplicate issue: {issue_entity.issue_key} "
                            f"(ID: {issue_entity.entity_id})"
                        )
                        continue

                    processed_entities.add(issue_identifier)
                    issue_count += 1
                    project_issue_count += 1
                    self.logger.info(f"Yielding issue entity: {issue_entity.issue_key}")
                    yield issue_entity

                self.logger.info(
                    f"Completed {project_issue_count} issues for project "
                    f"{project_entity.project_key}"
                )

            self.logger.info(
                f"Completed Jira entity generation: {project_count} projects, "
                f"{issue_count} issues total"
            )

    async def validate(self) -> bool:
        """Verify Jira OAuth2 token by calling accessible-resources endpoint.

        A successful call proves the token is valid and has necessary scopes.
        Cloud ID extraction happens lazily during sync.
        """
        try:
            resources = await self._get_accessible_resources()

            if not resources:
                self.logger.error("Jira validation failed: no accessible resources found")
                return False

            self.logger.info("✅ Jira validation successful")
            return True

        except Exception as e:
            self.logger.error(f"Jira validation failed: {str(e)}")
            return False
