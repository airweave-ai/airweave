"""Jira source implementation.

Simplified connector that retrieves Projects and Issues from a Jira Cloud instance.

References:
    https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/
    https://developer.atlassian.com/cloud/jira/platform/rest/v3/overview
"""

from typing import Any, AsyncGenerator

import httpx
import tenacity
from tenacity import stop_after_attempt, wait_exponential

from airweave.core.logging import logger
from airweave.platform.auth.schemas import AuthType
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.jira import (
    JiraIssueEntity,
    JiraProjectEntity,
)
from airweave.platform.sources._base import BaseSource


@source(
    "Jira", "jira", AuthType.oauth2_with_refresh, labels=["Project Management", "Issue Tracking"]
)
class JiraSource(BaseSource):
    """Simplified Jira source implementation (read-only).

    This connector retrieves hierarchical data from Jira's REST API:
      - Projects
      - Issues (within each project)
    """

    @staticmethod
    async def _get_accessible_resources(access_token: str) -> list[dict]:
        """Get the list of accessible Atlassian resources for this token."""
        logger.info("Retrieving accessible Atlassian resources")
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            try:
                logger.debug(
                    "Making request to https://api.atlassian.com/oauth/token/accessible-resources"
                )
                response = await client.get(
                    "https://api.atlassian.com/oauth/token/accessible-resources", headers=headers
                )
                response.raise_for_status()
                resources = response.json()
                logger.info(f"Found {len(resources)} accessible Atlassian resources")
                logger.debug(f"Resources: {resources}")
                return resources
            except Exception as e:
                logger.error(f"Error getting accessible resources: {str(e)}")
                return []

    @staticmethod
    async def _extract_cloud_id(access_token: str) -> str:
        """Extract the Atlassian Cloud ID from OAuth 2.0 accessible-resources."""
        logger.info("Extracting Atlassian Cloud ID")
        try:
            resources = await JiraSource._get_accessible_resources(access_token)

            if not resources:
                logger.warning("No accessible resources found")
                return ""

            # Use the first available resource
            resource = resources[0]
            cloud_id = resource.get("id", "")

            if not cloud_id:
                logger.warning("Missing ID in accessible resources")
            else:
                logger.info(f"Successfully extracted cloud ID: {cloud_id}")
            return cloud_id

        except Exception as e:
            logger.error(f"Error extracting cloud ID: {str(e)}")
            return ""

    @classmethod
    async def create(cls, access_token: str) -> "JiraSource":
        """Create a new Jira source instance."""
        logger.info("Creating new Jira source instance")
        instance = cls()
        instance.access_token = access_token
        instance.cloud_id = await cls._extract_cloud_id(access_token)
        instance.base_url = f"https://api.atlassian.com/ex/jira/{instance.cloud_id}"
        logger.info(f"Initialized Jira source with base URL: {instance.base_url}")
        return instance

    @tenacity.retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get_with_auth(self, client: httpx.AsyncClient, url: str) -> Any:
        """Make an authenticated GET request to the Jira REST API."""
        logger.debug(f"Making authenticated request to {url}")
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "X-Atlassian-Token": "no-check",  # Required for CSRF protection
        }

        # Add cloud instance ID if available
        if self.cloud_id:
            headers["X-Cloud-ID"] = self.cloud_id

        logger.debug(f"Request headers: {headers}")
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response size: {len(response.content)} bytes")
            return data
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            if isinstance(e, httpx.HTTPStatusError):
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response body: {e.response.text}")
            raise

    # Entity Creation Functions
    def _create_project_entity(self, project_data):
        """Transform raw project data into a JiraProjectEntity."""
        logger.debug(
            f"Creating project entity for: {project_data.get('key')} - {project_data.get('name')}"
        )
        # Use a composite ID format that includes the entity type for uniqueness
        entity_id = f"project-{project_data['id']}"

        return JiraProjectEntity(
            entity_id=entity_id,  # Modified to use unique ID
            breadcrumbs=[],  # top-level object, no parent
            project_key=project_data["key"],
            name=project_data.get("name"),
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
                logger.debug(f"Converting ADF description to text for issue {issue_key}")
                description_text = self._extract_text_from_adf(description)
            else:
                description_text = description

        logger.debug(
            f"Creating issue entity: {issue_key} - Type: {issue_type_name}, Status: {status_name}"
        )

        # Use a composite ID format that includes the entity type for uniqueness
        entity_id = f"issue-{issue_data['id']}"

        return JiraIssueEntity(
            entity_id=entity_id,  # Modified to use unique ID
            breadcrumbs=[
                Breadcrumb(entity_id=project.entity_id, name=project.name or "", type="project")
            ],
            issue_key=issue_key,
            summary=fields.get("summary"),
            description=description_text,
            status=status_name,
            issue_type=issue_type_name,
            created_at=fields.get("created"),
            updated_at=fields.get("updated"),
        )

    async def _generate_project_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[JiraProjectEntity, None]:
        """Generate JiraProjectEntity objects."""
        logger.info("Starting project entity generation")
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
            logger.info(f"Fetching project page {page} from {project_search_url}")

            # Get project data
            data = await self._get_with_auth(client, project_search_url)
            projects = data.get("values", [])
            logger.info(f"Retrieved {len(projects)} projects on page {page}")

            # Process each project
            for project in projects:
                total_projects += 1
                project_entity = self._create_project_entity(project)
                yield project_entity

            # Handle pagination
            if data.get("isLast", True):
                logger.info(
                    f"Reached last page of projects, total projects found: {total_projects}"
                )
                break

            start_at = data.get("startAt", 0) + max_results
            page += 1
            logger.debug(f"Moving to next page, startAt={start_at}")

    async def _generate_issue_entities(
        self, client: httpx.AsyncClient, project: JiraProjectEntity
    ) -> AsyncGenerator[JiraIssueEntity, None]:
        """Generate JiraIssueEntity for each issue in the given project using JQL search."""
        project_key = project.project_key
        logger.info(f"Starting issue entity generation for project: {project_key} ({project.name})")

        # Setup for pagination
        search_url = f"{self.base_url}/rest/api/3/search"
        start_at = 0
        max_results = 50
        page = 1
        total_issues = 0

        while True:
            # Construct parameters with JQL query for the project
            params = {
                "jql": f"project = {project_key}",
                "startAt": start_at,
                "maxResults": max_results,
                "fields": "summary,description,status,issuetype,created,updated",
            }

            # Convert params to URL query string
            query_string = "&".join([f"{k}={v}" for k, v in params.items()])
            full_url = f"{search_url}?{query_string}"

            logger.info(f"Fetching issues page {page} for project {project_key}")
            data = await self._get_with_auth(client, full_url)

            # Log response overview
            total = data.get("total", 0)
            issues = data.get("issues", [])
            logger.info(f"Found {len(issues)} issues on page {page} (total available: {total})")

            # Process each issue
            for issue_data in issues:
                total_issues += 1
                issue_entity = self._create_issue_entity(issue_data, project)
                yield issue_entity

            # Check if we've processed all issues
            start_at += max_results
            page += 1

            if start_at >= total:
                logger.info(
                    f"Completed fetching all {total_issues} issues for project {project_key}"
                )
                break

            logger.debug(f"Moving to next page, startAt={start_at}")

    async def generate_entities(self) -> AsyncGenerator[BaseEntity, None]:
        """Generate all entities from Jira."""
        logger.info("Starting Jira entity generation process")
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
                    logger.warning(
                        f"Skipping duplicate project: {project_entity.project_key} "
                        f"(ID: {project_entity.entity_id})"
                    )
                    continue

                processed_entities.add(project_identifier)
                logger.info(
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
                        logger.warning(
                            f"Skipping duplicate issue: {issue_entity.issue_key} "
                            f"(ID: {issue_entity.entity_id})"
                        )
                        continue

                    processed_entities.add(issue_identifier)
                    issue_count += 1
                    project_issue_count += 1
                    logger.info(f"Yielding issue entity: {issue_entity.issue_key}")
                    yield issue_entity

                logger.info(
                    f"Completed {project_issue_count} issues for project "
                    f"{project_entity.project_key}"
                )

            logger.info(
                f"Completed Jira entity generation: {project_count} projects, "
                f"{issue_count} issues total"
            )
