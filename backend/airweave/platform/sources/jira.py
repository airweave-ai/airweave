"""Jira source implementation.

Connector that retrieves Projects and Issues from a Jira Cloud instance,
with optional Zephyr Scale test management integration.

References:
    Jira REST API: https://developer.atlassian.com/cloud/jira/platform/rest/v3/intro/
    Zephyr Scale API: https://support.smartbear.com/zephyr-scale-cloud/api-docs/
"""

from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from tenacity import retry, stop_after_attempt

from airweave.core.exceptions import TokenRefreshError
from airweave.core.shared_models import RateLimitLevel
from airweave.platform.configs.auth import JiraAuthConfig
from airweave.platform.configs.config import JiraConfig
from airweave.platform.decorators import source
from airweave.platform.entities._base import BaseEntity, Breadcrumb
from airweave.platform.entities.jira import (
    JiraIssueEntity,
    JiraProjectEntity,
    ZephyrTestCaseEntity,
    ZephyrTestCycleEntity,
    ZephyrTestPlanEntity,
)
from airweave.platform.sources._base import BaseSource
from airweave.platform.sources.retry_helpers import (
    retry_if_rate_limit_or_timeout,
    wait_rate_limit_with_backoff,
)
from airweave.schemas.source_connection import AuthenticationMethod, OAuthType

# Zephyr Scale API base URL for Cloud
ZEPHYR_SCALE_BASE_URL = "https://api.zephyrscale.smartbear.com/v2"


@source(
    name="Jira",
    short_name="jira",
    auth_methods=[
        AuthenticationMethod.OAUTH_BROWSER,
        AuthenticationMethod.OAUTH_TOKEN,
        AuthenticationMethod.AUTH_PROVIDER,
    ],
    oauth_type=OAuthType.WITH_ROTATING_REFRESH,
    auth_config_class=JiraAuthConfig,
    config_class=JiraConfig,
    labels=["Project Management", "Issue Tracking", "Test Management"],
    supports_continuous=False,
    rate_limit_level=RateLimitLevel.ORG,
)
class JiraSource(BaseSource):
    """Jira source connector integrates with the Jira REST API to extract project management data.

    Connects to your Jira Cloud instance. Optionally integrates with Zephyr Scale
    for test management entities (test cases, test cycles, test plans) when a
    Zephyr Scale API token is provided.

    It provides comprehensive access to projects, issues, and their
    relationships for agile development and issue tracking workflows.
    """

    def __init__(self) -> None:
        """Initialize Jira source with placeholders for site metadata."""
        super().__init__()
        self.site_url: Optional[str] = None
        self.zephyr_api_token: Optional[str] = None

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
                    f"HTTP error getting accessible resources: "
                    f"{e.response.status_code} - {e.response.text}"
                )
                return []
            except Exception as e:
                self.logger.error(f"Error getting accessible resources: {str(e)}", exc_info=True)
                return []

    @classmethod
    async def create(
        cls, access_token: Any, config: Optional[Dict[str, Any]] = None
    ) -> "JiraSource":
        """Create a new Jira source instance.

        Args:
            access_token: Either a string (OAuth access token) or a dict containing
                credentials including access_token.
            config: Configuration options for the source, may include zephyr_scale_api_token.
        """
        instance = cls()
        instance.config = config or {}

        # Handle credentials being either a string or dict
        if isinstance(access_token, dict):
            # Credentials dict from JiraAuthConfig
            instance.access_token = access_token.get("access_token", "")
        else:
            # Simple string token (legacy OAuth flow)
            instance.access_token = access_token

        # Zephyr Scale token comes from config (not auth credentials)
        # This allows it to be provided alongside OAuth authentication
        instance.zephyr_api_token = instance.config.get("zephyr_scale_api_token")

        return instance

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
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

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
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
        project_id = str(project_data["id"])
        project_name = project_data.get("name") or project_data["key"]

        return JiraProjectEntity(
            entity_id=project_id,
            breadcrumbs=[],
            name=project_name,
            created_at=None,
            updated_at=None,
            project_id=project_id,
            project_name=project_name,
            project_key=project_data["key"],
            description=project_data.get("description"),
            web_url_value=self._build_project_url(project_data["key"]),
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

        issue_id = str(issue_data["id"])
        summary = fields.get("summary") or issue_key
        created_time = self._parse_datetime(fields.get("created")) or datetime.utcnow()
        updated_time = self._parse_datetime(fields.get("updated")) or created_time

        return JiraIssueEntity(
            entity_id=issue_id,
            breadcrumbs=[
                Breadcrumb(
                    entity_id=project.project_id,
                    name=project.project_name,
                    entity_type=JiraProjectEntity.__name__,
                )
            ],
            name=summary,
            created_at=created_time,
            updated_at=updated_time,
            issue_id=issue_id,
            issue_key=issue_key,
            summary=summary,
            description=description_text,
            status=status_name,
            issue_type=issue_type_name,
            project_key=project.project_key,
            created_time=created_time,
            updated_time=updated_time,
            web_url_value=self._build_issue_url(issue_key),
        )

    async def _generate_project_entities(
        self, client: httpx.AsyncClient
    ) -> AsyncGenerator[JiraProjectEntity, None]:
        """Generate JiraProjectEntity objects."""
        self.logger.info("Starting project entity generation")

        # Get project filter from config (required field)
        project_keys_filter = self.config.get("project_keys", []) if hasattr(self, "config") else []

        if not project_keys_filter:
            raise ValueError(
                "Project keys configuration is required. Please specify which Jira projects "
                "to sync by editing the source connection details."
            )

        # Convert to uppercase for case-insensitive matching (Jira keys are uppercase)
        project_keys_filter = [key.upper() for key in project_keys_filter]
        project_keys_filter_set = set(project_keys_filter)

        self.logger.info(f"Project filter: will sync only projects with keys {project_keys_filter}")

        search_api_path = "/rest/api/3/project/search"
        max_results = 50
        start_at = 0
        page = 1
        total_projects = 0
        filtered_projects = 0
        found_project_keys = set()

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
                project_key = project.get("key")

                # Apply filter if configured
                if project_keys_filter and project_key not in project_keys_filter_set:
                    filtered_projects += 1
                    self.logger.debug(f"Skipping project {project_key} - not in filter list")
                    continue

                # Track which projects we actually found
                found_project_keys.add(project_key)

                project_entity = self._create_project_entity(project)
                yield project_entity

            # Handle pagination
            if data.get("isLast", True):
                matched_count = total_projects - filtered_projects

                # Check for projects that were requested but not found
                missing_keys = project_keys_filter_set - found_project_keys
                if missing_keys:
                    self.logger.warning(
                        f"⚠️ Some requested projects were not found or not accessible: "
                        f"{sorted(missing_keys)}"
                    )

                if matched_count == 0:
                    self.logger.error(
                        f"❌ No projects matched the filter! Requested: {project_keys_filter}, "
                        f"but none were found. Please check that the project keys are correct "
                        f"and accessible."
                    )
                    # Don't raise - let sync continue with 0 projects (user can see in logs/UI)
                else:
                    self.logger.info(
                        f"✅ Completed project sync: {matched_count} project(s) included "
                        f"({filtered_projects} filtered out). "
                        f"Found: {sorted(found_project_keys)}"
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
        """Generate all entities from Jira and optionally Zephyr Scale."""
        self.logger.info("Starting Jira entity generation process")

        resources = await self._get_accessible_resources()
        if not resources:
            raise ValueError("No accessible resources found")
        cloud_id = resources[0]["id"]
        self.site_url = resources[0].get("url")
        if self.site_url:
            self.site_url = self.site_url.rstrip("/")
        else:
            self.logger.warning("Accessible Jira resource missing site URL; web links disabled.")

        self.base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"
        self.logger.debug(f"Base URL set to: {self.base_url}")

        # Check if Zephyr Scale integration is enabled
        # Token will only be present if:
        # 1. The ZEPHYR_SCALE feature flag is enabled for the organization
        # 2. The user provided the API token in the config
        zephyr_enabled = self._is_zephyr_enabled()
        if zephyr_enabled:
            self.logger.info(
                "🧪 Zephyr Scale integration ENABLED - "
                "API token configured, will sync test entities"
            )
        else:
            self.logger.info(
                "ℹ️ Zephyr Scale integration DISABLED - "
                "no API token in config (feature flag may be off or token not provided)"
            )

        async with httpx.AsyncClient() as client:
            project_count = 0
            issue_count = 0
            zephyr_test_case_count = 0
            zephyr_test_cycle_count = 0
            zephyr_test_plan_count = 0

            # Track already processed entity IDs with their type to avoid duplicates
            processed_entities = set()  # Will store tuples of (entity_id, key)

            # Store projects for Zephyr integration (need to iterate twice)
            projects: List[JiraProjectEntity] = []

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
                projects.append(project_entity)
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

            # 3) Zephyr Scale Integration (if configured)
            if zephyr_enabled:
                self.logger.info("🧪 Starting Zephyr Scale entity generation")

                for project in projects:
                    # Generate Test Cases
                    async for test_case in self._generate_zephyr_test_case_entities(
                        client, project
                    ):
                        tc_identifier = (test_case.entity_id, test_case.test_case_key)
                        if tc_identifier not in processed_entities:
                            processed_entities.add(tc_identifier)
                            zephyr_test_case_count += 1
                            self.logger.debug(
                                f"Yielding test case entity: {test_case.test_case_key}"
                            )
                            yield test_case

                    # Generate Test Cycles
                    async for test_cycle in self._generate_zephyr_test_cycle_entities(
                        client, project
                    ):
                        tcyc_identifier = (test_cycle.entity_id, test_cycle.test_cycle_key)
                        if tcyc_identifier not in processed_entities:
                            processed_entities.add(tcyc_identifier)
                            zephyr_test_cycle_count += 1
                            self.logger.debug(
                                f"Yielding test cycle entity: {test_cycle.test_cycle_key}"
                            )
                            yield test_cycle

                    # Generate Test Plans
                    async for test_plan in self._generate_zephyr_test_plan_entities(
                        client, project
                    ):
                        tp_identifier = (test_plan.entity_id, test_plan.test_plan_key)
                        if tp_identifier not in processed_entities:
                            processed_entities.add(tp_identifier)
                            zephyr_test_plan_count += 1
                            self.logger.debug(
                                f"Yielding test plan entity: {test_plan.test_plan_key}"
                            )
                            yield test_plan

                self.logger.info(
                    f"✅ Completed Zephyr Scale entity generation: "
                    f"{zephyr_test_case_count} test cases, "
                    f"{zephyr_test_cycle_count} test cycles, "
                    f"{zephyr_test_plan_count} test plans"
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

            self.logger.info("✅ Jira OAuth validation successful")
            return True

        except Exception as e:
            self.logger.error(f"Jira validation failed: {str(e)}")
            return False

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        """Parse Jira timestamp strings into aware datetimes."""
        if not value:
            return None
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None

    def _build_project_url(self, project_key: str) -> Optional[str]:
        """Construct a human-friendly Jira URL for a project."""
        if not self.site_url:
            return None
        return f"{self.site_url}/projects/{project_key}"

    def _build_issue_url(self, issue_key: str) -> Optional[str]:
        """Construct a human-friendly Jira URL for an issue."""
        if not self.site_url:
            return None
        return f"{self.site_url}/browse/{issue_key}"

    # =========================================================================
    # Zephyr Scale Integration
    # =========================================================================
    # These methods integrate with the Zephyr Scale test management API.
    # Requires:
    # 1. ZEPHYR_SCALE feature flag enabled for the organization
    # 2. Zephyr Scale API token configured in credentials

    def _is_zephyr_enabled(self) -> bool:
        """Check if Zephyr Scale integration is enabled and configured.

        Returns True if a Zephyr Scale API token is present in config.
        The token will only be present if the ZEPHYR_SCALE feature flag is enabled
        for the organization - config fields with feature flags are stripped
        during validation if the flag is not enabled.
        """
        return bool(self.zephyr_api_token)

    @retry(
        stop=stop_after_attempt(5),
        retry=retry_if_rate_limit_or_timeout,
        wait=wait_rate_limit_with_backoff,
        reraise=True,
    )
    async def _get_zephyr_with_auth(self, client: httpx.AsyncClient, url: str) -> Any:
        """Make an authenticated GET request to the Zephyr Scale API.

        Note: Zephyr Scale uses a separate API token, not the Jira OAuth token.
        """
        if not self.zephyr_api_token:
            raise ValueError("Zephyr Scale API token not configured")

        headers = {
            "Authorization": f"Bearer {self.zephyr_api_token}",
            "Accept": "application/json",
        }

        self.logger.debug(f"Making Zephyr Scale request to {url}")
        try:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            self.logger.debug(f"Zephyr response status: {response.status_code}")
            return data
        except httpx.HTTPStatusError as e:
            self.logger.error(
                f"Zephyr Scale HTTP error: {e.response.status_code} - {e.response.text}"
            )
            raise
        except httpx.TimeoutException as e:
            self.logger.warning(f"Zephyr Scale request timeout ({type(e).__name__}): {url}")
            raise
        except httpx.RequestError as e:
            # Catches ConnectError, PoolTimeout, etc.
            self.logger.warning(f"Zephyr Scale request error ({type(e).__name__}): {e}")
            raise
        except Exception as e:
            # Fallback for unexpected exceptions
            self.logger.error(f"Zephyr Scale unexpected error ({type(e).__name__}): {e!r}")
            raise

    def _build_zephyr_test_case_url(self, test_case_key: str) -> Optional[str]:
        """Construct a URL for a Zephyr Scale test case."""
        if not self.site_url:
            return None
        # Zephyr Scale test cases are accessed via the Jira plugin servlet
        return (
            f"{self.site_url}/plugins/servlet/ac/com.kanoah.test-manager/"
            f"testcase-details?testCaseKey={test_case_key}"
        )

    def _build_zephyr_test_cycle_url(self, test_cycle_key: str) -> Optional[str]:
        """Construct a URL for a Zephyr Scale test cycle."""
        if not self.site_url:
            return None
        return (
            f"{self.site_url}/plugins/servlet/ac/com.kanoah.test-manager/"
            f"testcycle-details?testCycleKey={test_cycle_key}"
        )

    def _build_zephyr_test_plan_url(self, test_plan_key: str) -> Optional[str]:
        """Construct a URL for a Zephyr Scale test plan."""
        if not self.site_url:
            return None
        return (
            f"{self.site_url}/plugins/servlet/ac/com.kanoah.test-manager/"
            f"testplan-details?testPlanKey={test_plan_key}"
        )

    def _create_zephyr_test_case_entity(
        self, test_case_data: Dict[str, Any], project: JiraProjectEntity
    ) -> ZephyrTestCaseEntity:
        """Transform raw Zephyr Scale test case data into a ZephyrTestCaseEntity."""
        test_case_key = test_case_data.get("key", "unknown")
        test_case_id = str(test_case_data.get("id", test_case_key))

        # Parse timestamps
        created_time = self._parse_datetime(test_case_data.get("createdOn")) or datetime.utcnow()
        updated_time = self._parse_datetime(test_case_data.get("updatedOn")) or created_time

        # Extract nested fields safely
        status = test_case_data.get("status", {})
        status_name = status.get("name") if isinstance(status, dict) else None

        priority = test_case_data.get("priority", {})
        priority_name = priority.get("name") if isinstance(priority, dict) else None

        folder = test_case_data.get("folder", {})
        folder_path = folder.get("name") if isinstance(folder, dict) else None

        self.logger.debug(f"Creating Zephyr test case entity: {test_case_key}")

        return ZephyrTestCaseEntity(
            entity_id=test_case_id,
            breadcrumbs=[
                Breadcrumb(
                    entity_id=project.project_id,
                    name=project.project_name,
                    entity_type=JiraProjectEntity.__name__,
                )
            ],
            name=test_case_data.get("name", test_case_key),
            created_at=created_time,
            updated_at=updated_time,
            test_case_id=test_case_id,
            test_case_key=test_case_key,
            objective=test_case_data.get("objective"),
            precondition=test_case_data.get("precondition"),
            status_name=status_name,
            priority_name=priority_name,
            folder_path=folder_path,
            project_key=project.project_key,
            created_time=created_time,
            updated_time=updated_time,
            web_url_value=self._build_zephyr_test_case_url(test_case_key),
        )

    def _create_zephyr_test_cycle_entity(
        self, test_cycle_data: Dict[str, Any], project: JiraProjectEntity
    ) -> ZephyrTestCycleEntity:
        """Transform raw Zephyr Scale test cycle data into a ZephyrTestCycleEntity."""
        test_cycle_key = test_cycle_data.get("key", "unknown")
        test_cycle_id = str(test_cycle_data.get("id", test_cycle_key))

        # Parse timestamps
        created_time = self._parse_datetime(test_cycle_data.get("createdOn")) or datetime.utcnow()
        updated_time = self._parse_datetime(test_cycle_data.get("updatedOn")) or created_time

        # Extract nested fields safely
        status = test_cycle_data.get("status", {})
        status_name = status.get("name") if isinstance(status, dict) else None

        folder = test_cycle_data.get("folder", {})
        folder_path = folder.get("name") if isinstance(folder, dict) else None

        self.logger.debug(f"Creating Zephyr test cycle entity: {test_cycle_key}")

        return ZephyrTestCycleEntity(
            entity_id=test_cycle_id,
            breadcrumbs=[
                Breadcrumb(
                    entity_id=project.project_id,
                    name=project.project_name,
                    entity_type=JiraProjectEntity.__name__,
                )
            ],
            name=test_cycle_data.get("name", test_cycle_key),
            created_at=created_time,
            updated_at=updated_time,
            test_cycle_id=test_cycle_id,
            test_cycle_key=test_cycle_key,
            description=test_cycle_data.get("description"),
            status_name=status_name,
            folder_path=folder_path,
            project_key=project.project_key,
            created_time=created_time,
            updated_time=updated_time,
            web_url_value=self._build_zephyr_test_cycle_url(test_cycle_key),
        )

    def _create_zephyr_test_plan_entity(
        self, test_plan_data: Dict[str, Any], project: JiraProjectEntity
    ) -> ZephyrTestPlanEntity:
        """Transform raw Zephyr Scale test plan data into a ZephyrTestPlanEntity."""
        test_plan_key = test_plan_data.get("key", "unknown")
        test_plan_id = str(test_plan_data.get("id", test_plan_key))

        # Parse timestamps
        created_time = self._parse_datetime(test_plan_data.get("createdOn")) or datetime.utcnow()
        updated_time = self._parse_datetime(test_plan_data.get("updatedOn")) or created_time

        # Extract nested fields safely
        status = test_plan_data.get("status", {})
        status_name = status.get("name") if isinstance(status, dict) else None

        folder = test_plan_data.get("folder", {})
        folder_path = folder.get("name") if isinstance(folder, dict) else None

        self.logger.debug(f"Creating Zephyr test plan entity: {test_plan_key}")

        return ZephyrTestPlanEntity(
            entity_id=test_plan_id,
            breadcrumbs=[
                Breadcrumb(
                    entity_id=project.project_id,
                    name=project.project_name,
                    entity_type=JiraProjectEntity.__name__,
                )
            ],
            name=test_plan_data.get("name", test_plan_key),
            created_at=created_time,
            updated_at=updated_time,
            test_plan_id=test_plan_id,
            test_plan_key=test_plan_key,
            objective=test_plan_data.get("objective"),
            status_name=status_name,
            folder_path=folder_path,
            project_key=project.project_key,
            created_time=created_time,
            updated_time=updated_time,
            web_url_value=self._build_zephyr_test_plan_url(test_plan_key),
        )

    async def _generate_zephyr_test_case_entities(
        self, client: httpx.AsyncClient, project: JiraProjectEntity
    ) -> AsyncGenerator[ZephyrTestCaseEntity, None]:
        """Generate ZephyrTestCaseEntity objects for a project."""
        project_key = project.project_key
        self.logger.info(f"Fetching Zephyr Scale test cases for project: {project_key}")

        max_results = 100
        start_at = 0
        total_fetched = 0

        while True:
            url = (
                f"{ZEPHYR_SCALE_BASE_URL}/testcases"
                f"?projectKey={project_key}&maxResults={max_results}&startAt={start_at}"
            )

            try:
                data = await self._get_zephyr_with_auth(client, url)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    self.logger.warning(
                        f"Zephyr Scale not found for project {project_key} - "
                        "may not have Zephyr Scale enabled"
                    )
                    return
                raise

            values = data.get("values", [])
            self.logger.info(f"Retrieved {len(values)} test cases for project {project_key}")

            for test_case_data in values:
                total_fetched += 1
                yield self._create_zephyr_test_case_entity(test_case_data, project)

            # Handle pagination
            if data.get("isLast", True) or not values:
                self.logger.info(
                    f"✅ Completed fetching {total_fetched} test cases for project {project_key}"
                )
                break

            start_at += max_results

    async def _generate_zephyr_test_cycle_entities(
        self, client: httpx.AsyncClient, project: JiraProjectEntity
    ) -> AsyncGenerator[ZephyrTestCycleEntity, None]:
        """Generate ZephyrTestCycleEntity objects for a project."""
        project_key = project.project_key
        self.logger.info(f"Fetching Zephyr Scale test cycles for project: {project_key}")

        max_results = 100
        start_at = 0
        total_fetched = 0

        while True:
            url = (
                f"{ZEPHYR_SCALE_BASE_URL}/testcycles"
                f"?projectKey={project_key}&maxResults={max_results}&startAt={start_at}"
            )

            try:
                data = await self._get_zephyr_with_auth(client, url)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    self.logger.warning(
                        f"Zephyr Scale test cycles not found for project {project_key}"
                    )
                    return
                raise

            values = data.get("values", [])
            self.logger.info(f"Retrieved {len(values)} test cycles for project {project_key}")

            for test_cycle_data in values:
                total_fetched += 1
                yield self._create_zephyr_test_cycle_entity(test_cycle_data, project)

            # Handle pagination
            if data.get("isLast", True) or not values:
                self.logger.info(
                    f"✅ Completed fetching {total_fetched} test cycles for project {project_key}"
                )
                break

            start_at += max_results

    async def _generate_zephyr_test_plan_entities(
        self, client: httpx.AsyncClient, project: JiraProjectEntity
    ) -> AsyncGenerator[ZephyrTestPlanEntity, None]:
        """Generate ZephyrTestPlanEntity objects for a project."""
        project_key = project.project_key
        self.logger.info(f"Fetching Zephyr Scale test plans for project: {project_key}")

        max_results = 100
        start_at = 0
        total_fetched = 0

        while True:
            url = (
                f"{ZEPHYR_SCALE_BASE_URL}/testplans"
                f"?projectKey={project_key}&maxResults={max_results}&startAt={start_at}"
            )

            try:
                data = await self._get_zephyr_with_auth(client, url)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    self.logger.warning(
                        f"Zephyr Scale test plans not found for project {project_key}"
                    )
                    return
                raise

            values = data.get("values", [])
            self.logger.info(f"Retrieved {len(values)} test plans for project {project_key}")

            for test_plan_data in values:
                total_fetched += 1
                yield self._create_zephyr_test_plan_entity(test_plan_data, project)

            # Handle pagination
            if data.get("isLast", True) or not values:
                self.logger.info(
                    f"✅ Completed fetching {total_fetched} test plans for project {project_key}"
                )
                break

            start_at += max_results
